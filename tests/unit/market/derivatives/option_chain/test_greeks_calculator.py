from __future__ import annotations

import math

import pytest
from ats.market.derivatives.contract_master import OptionType
from ats.market.derivatives.option_chain import (
    CALCULATOR_VERSION,
    DeterministicGreeksRequest,
    GreeksMethod,
    compute_deterministic_greeks,
)

ATM = DeterministicGreeksRequest(
    underlying_price=25000.0,
    strike=25000.0,
    time_to_expiry_days=7.0,
    implied_volatility=0.15,
    risk_free_rate=0.065,
    option_type=OptionType.CE,
)


class TestProvenanceLabels:
    def test_method_label_is_deterministic_calculator(self) -> None:
        result = compute_deterministic_greeks(ATM)
        assert result.greeks_method is GreeksMethod.DETERMINISTIC_CALCULATOR
        assert result.greeks_method is not GreeksMethod.SOURCE_PROVIDED
        assert result.greeks_method_version == CALCULATOR_VERSION == "ATS-BLACK-SCHOLES-1.0"

    def test_result_carries_full_input_evidence(self) -> None:
        result = compute_deterministic_greeks(ATM)
        assert result.request == ATM


class TestMathematics:
    def test_call_put_delta_parity(self) -> None:
        call = compute_deterministic_greeks(ATM)
        put_request = ATM.model_copy(update={"option_type": OptionType.PE})
        put = compute_deterministic_greeks(put_request)
        assert math.isclose(call.delta - put.delta, 1.0, rel_tol=0, abs_tol=1e-12)

    def test_gamma_is_identical_for_calls_and_puts(self) -> None:
        call = compute_deterministic_greeks(ATM)
        put = compute_deterministic_greeks(ATM.model_copy(update={"option_type": OptionType.PE}))
        assert call.gamma == put.gamma

    def test_theta_is_negative_for_long_options(self) -> None:
        for option_type in (OptionType.CE, OptionType.PE):
            request = ATM.model_copy(update={"option_type": option_type})
            result = compute_deterministic_greeks(request)
            assert result.theta_per_year < 0
            assert result.theta_per_calendar_day < 0
            assert math.isclose(
                result.theta_per_calendar_day * 365.0,
                result.theta_per_year,
                rel_tol=1e-9,
            )

    def test_vega_positive_for_both_sides(self) -> None:
        for option_type in (OptionType.CE, OptionType.PE):
            request = ATM.model_copy(update={"option_type": option_type})
            result = compute_deterministic_greeks(request)
            assert result.vega_per_iv_point > 0

    def test_deep_itm_call_delta_approaches_one(self) -> None:
        deep = ATM.model_copy(update={"strike": 10000.0})
        assert compute_deterministic_greeks(deep).delta > 0.999

    def test_deep_otm_call_delta_approaches_zero(self) -> None:
        deep = ATM.model_copy(update={"strike": 90000.0})
        assert compute_deterministic_greeks(deep).delta < 0.001


class TestDeterminismAndRejection:
    def test_repeated_computation_is_bit_identical(self) -> None:
        assert compute_deterministic_greeks(ATM) == compute_deterministic_greeks(ATM)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("underlying_price", 0.0),
            ("strike", -1.0),
            ("time_to_expiry_days", 0.0),
            ("implied_volatility", 0.0),
        ],
    )
    def test_non_positive_inputs_are_refused(self, field: str, value: float) -> None:
        base = dict(
            underlying_price=25000.0,
            strike=25000.0,
            time_to_expiry_days=7.0,
            implied_volatility=0.15,
            risk_free_rate=0.065,
            option_type=OptionType.CE,
        )
        base[field] = value
        with pytest.raises(ValueError):
            DeterministicGreeksRequest(**base)

    def test_nan_and_inf_inputs_are_refused(self) -> None:
        with pytest.raises(ValueError):
            DeterministicGreeksRequest(
                underlying_price=float("inf"),
                strike=25000.0,
                time_to_expiry_days=7.0,
                implied_volatility=0.15,
                risk_free_rate=0.065,
                option_type=OptionType.CE,
            )
