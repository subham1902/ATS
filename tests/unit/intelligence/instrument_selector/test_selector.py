from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.types import ThesisStance
from ats.intelligence.instrument_selector import (
    InstrumentSelectionError,
    InstrumentSelectionStatus,
    select_derivative_instruments,
)

from tests.unit.market.derivatives.option_chain.helpers import (
    AS_OF,
    master,
)

from .helpers import chain, configuration, distribution, evaluation_time, thesis


def select(**overrides: object):
    arguments = {
        "contract_master": master(),
        "option_chain": chain(),
        "thesis": thesis(),
        "distribution": distribution(),
        "evaluation_time": evaluation_time(),
        "configuration": configuration(),
    }
    arguments.update(overrides)
    return select_derivative_instruments(**arguments)  # type: ignore[arg-type]


def test_bullish_thesis_selects_one_long_call() -> None:
    result = select()
    assert result.status is InstrumentSelectionStatus.CANDIDATES_AVAILABLE
    assert len(result.candidates) == 1
    assert result.candidates[0].option_type.value == "CE"
    assert result.candidates[0].lot_count == 1


def test_bearish_thesis_selects_one_long_put() -> None:
    result = select(
        thesis=thesis(stance=ThesisStance.BEARISH),
        distribution=distribution(expected_return=-0.01),
    )
    assert result.candidates[0].option_type.value == "PE"


@pytest.mark.parametrize("stance", [ThesisStance.NEUTRAL, ThesisStance.MIXED, ThesisStance.UNKNOWN])
def test_non_directional_thesis_creates_no_candidate(stance: ThesisStance) -> None:
    result = select(thesis=thesis(stance=stance))
    assert result.status is InstrumentSelectionStatus.NO_ELIGIBLE_INSTRUMENT
    assert result.candidates == ()


def test_wrong_expected_return_sign_creates_no_candidate() -> None:
    assert select(distribution=distribution(expected_return=-0.01)).candidates == ()


def test_candidate_economics_use_exact_decimal_arithmetic() -> None:
    candidate = select().candidates[0]
    costs = (
        candidate.estimated_spread_cost
        + candidate.estimated_slippage
        + candidate.estimated_transaction_cost
        + candidate.estimated_theta_cost
        + candidate.estimated_iv_penalty
        + candidate.estimated_liquidity_penalty
        + candidate.estimated_expiry_penalty
    )
    assert candidate.expected_net_pnl == candidate.expected_gross_pnl - costs
    assert candidate.premium_required == candidate.entry_ask * candidate.quantity
    assert candidate.payload_hash == compute_payload_hash(candidate)


def test_adjacent_equivalent_strikes_are_suppressed() -> None:
    result = select()
    assert len(result.candidates) == 1
    assert any(
        rejection.reason_codes == ("ECONOMIC_DUPLICATE_SUPPRESSED",)
        for rejection in result.rejections
    )


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"bid": Decimal("0")}, "ZERO_OR_MISSING_BID"),
        ({"bid": Decimal("50"), "ask": Decimal("101")}, "SPREAD_TOO_WIDE"),
        ({"ask_qty": 1}, "INSUFFICIENT_ASK_DEPTH"),
        ({"volume": 0}, "INSUFFICIENT_VOLUME"),
        ({"open_interest": 0}, "INSUFFICIENT_OPEN_INTEREST"),
        ({"implied_volatility": None}, "IMPLIED_VOLATILITY_UNAVAILABLE"),
    ],
)
def test_bad_quote_is_rejected_without_poisoning_other_quotes(
    updates: dict[str, object], reason: str
) -> None:
    result = select(option_chain=chain(**updates))
    rejected = next(item for item in result.rejections if item.instrument_id == "C1")
    assert reason in rejected.reason_codes
    assert len(result.candidates) == 1


def test_missing_greeks_are_rejected() -> None:
    from ats.market.derivatives.option_chain import GreeksMethod

    bad_chain = chain(
        implied_volatility=0.2,
        delta=None,
        gamma=None,
        theta=None,
        vega=None,
        greeks_method=GreeksMethod.UNAVAILABLE,
        greeks_method_version=None,
    )
    result = select(option_chain=bad_chain)
    rejected = next(item for item in result.rejections if item.instrument_id == "C1")
    assert "REQUIRED_GREEKS_UNAVAILABLE" in rejected.reason_codes


def test_stale_chain_fails_closed() -> None:
    strict = configuration().model_copy(update={"maximum_chain_age_ms": 1_000})
    with pytest.raises(InstrumentSelectionError, match="chain is stale"):
        select(configuration=strict)


def test_expired_distribution_fails_closed() -> None:
    expired = distribution().model_copy(update={"valid_until": AS_OF + timedelta(seconds=1)})
    expired = expired.model_copy(update={"payload_hash": compute_payload_hash(expired)})
    with pytest.raises(InstrumentSelectionError, match="distribution is expired"):
        select(distribution=expired, evaluation_time=AS_OF + timedelta(seconds=2))


def test_tampered_chain_fails_closed() -> None:
    changed = chain().model_copy(update={"source_version": "TAMPERED"})
    with pytest.raises(InstrumentSelectionError, match="payload hash"):
        select(option_chain=changed)


def test_invalid_chain_quality_fails_closed() -> None:
    changed = chain().model_copy(update={"quality_state": DataQualityState.UNKNOWN})
    changed = changed.model_copy(update={"payload_hash": compute_payload_hash(changed)})
    with pytest.raises(InstrumentSelectionError, match="quality"):
        select(option_chain=changed)


def test_premium_budget_is_not_a_risk_authorization() -> None:
    strict = configuration().model_copy(update={"maximum_premium_per_candidate": Decimal("1")})
    result = select(configuration=strict)
    assert result.candidates == ()
    assert not hasattr(result, "authorize")


def test_near_expiry_penalty_uses_explicit_hours_conversion() -> None:
    strict = configuration().model_copy(update={"near_expiry_threshold_hours": Decimal("1000")})
    candidate = select(configuration=strict).candidates[0]
    assert candidate.estimated_expiry_penalty > 0


def test_selector_output_has_no_opportunity_or_order_contract() -> None:
    candidate = select().candidates[0]
    fields = type(candidate).model_fields
    assert "risk_decision_id" not in fields
    assert "autonomy_token_id" not in fields
    assert "order_intent" not in fields
