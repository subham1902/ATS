from __future__ import annotations

import math

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market.derivatives.option_chain import (
    GreeksMethod,
    build_option_chain,
    compute_option_chain_evidence,
)

from .helpers import context, master, quote


def test_bounded_feature_evidence_is_deterministic_and_finite() -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("C2"), quote("P2", implied_volatility=0.22)),
    )
    first = compute_option_chain_evidence(chain)
    second = compute_option_chain_evidence(chain)
    assert first == second
    assert first.payload_hash == compute_payload_hash(first)
    assert first.atm_iv == pytest.approx(0.21)
    assert first.put_call_iv_difference == pytest.approx(0.02)
    assert first.atm_straddle_premium == 200
    assert first.implied_expected_move is not None and first.implied_expected_move > 0
    for value in (
        first.atm_iv,
        first.put_call_iv_difference,
        first.put_call_open_interest_ratio,
        first.put_call_volume_ratio,
        first.call_put_volume_imbalance,
        first.mean_spread_fraction,
        first.gamma_concentration,
        first.theta_decay_intensity,
    ):
        assert value is None or math.isfinite(value)


def test_missing_greeks_and_iv_produce_none_with_reasons() -> None:
    unavailable = {
        "implied_volatility": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "greeks_method": GreeksMethod.UNAVAILABLE,
        "greeks_method_version": None,
    }
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("C2", **unavailable), quote("P2", **unavailable)),
    )
    evidence = compute_option_chain_evidence(chain)
    assert evidence.atm_iv is None
    assert evidence.implied_expected_move is None
    assert "ATM_IV_UNAVAILABLE" in evidence.reason_codes
    assert "GAMMA_CONCENTRATION_UNAVAILABLE" in evidence.reason_codes


def test_zero_call_denominators_do_not_create_infinity() -> None:
    chain = build_option_chain(
        contract_master=master(),
        context=context(),
        inputs=(quote("P2"),),
    )
    evidence = compute_option_chain_evidence(chain)
    assert evidence.put_call_open_interest_ratio is None
    assert evidence.put_call_volume_ratio is None
