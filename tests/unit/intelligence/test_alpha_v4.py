from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ats.intelligence.alpha_v4 import (
    AlphaAction,
    AlphaBar,
    AlphaOptionQuote,
    AlphaRegime,
    build_feature_bundle,
    decide_alpha_v4,
    estimate_net_value,
)


def bars(*, drift: float = 0.0, alternating: bool = False) -> tuple[AlphaBar, ...]:
    start = datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    result = []
    price = 24000.0
    for index in range(40):
        direction = -1.0 if alternating and index % 2 else 1.0
        price *= 1.0 + direction * drift
        timestamp = start + timedelta(minutes=index)
        result.append(
            AlphaBar(
                timestamp,
                timestamp,
                timestamp,
                timestamp,
                price,
                price + 1,
                price - 1,
                price,
                1000 + index,
            )
        )
    return tuple(result)


def quote(
    option_type: str, observed_at: datetime, *, bid: float = 99.9, ask: float = 100.0
) -> AlphaOptionQuote:
    return AlphaOptionQuote(
        "NSE_FO|TEST", option_type, "2026-09-03", 24000.0, bid, ask, observed_at
    )


def test_feature_factory_is_cutoff_bounded_and_deterministic() -> None:
    source = bars(drift=0.0002)
    cutoff = source[35].event_time
    first = build_feature_bundle(source, decision_time=cutoff)
    future_mutation = source + (
        AlphaBar(
            cutoff + timedelta(minutes=10),
            cutoff + timedelta(minutes=10),
            cutoff + timedelta(minutes=10),
            cutoff + timedelta(minutes=10),
            1,
            1,
            1,
            1,
            1,
        ),
    )
    second = build_feature_bundle(future_mutation, decision_time=cutoff)
    assert first == second
    assert set(first.returns) == {1, 3, 5, 10, 15, 30}


def test_slow_range_without_economic_edge_holds() -> None:
    features = build_feature_bundle(
        bars(drift=0.00001, alternating=True), decision_time=bars()[-1].event_time
    )
    decision = decide_alpha_v4(
        features,
        ce_quote=quote("CE", features.decision_time),
        pe_quote=quote("PE", features.decision_time),
        provider_lot_size=65,
    )
    assert decision.regime in {AlphaRegime.RANGE, AlphaRegime.UNCERTAIN}
    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason in {"NO_EDGE_AFTER_COSTS", "UNCERTAIN_REGIME"}


def test_missing_option_evidence_fails_closed() -> None:
    features = build_feature_bundle(bars(drift=0.0003), decision_time=bars()[-1].event_time)
    decision = decide_alpha_v4(features, ce_quote=None, pe_quote=None, provider_lot_size=65)
    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason in {"OPTION_EVIDENCE_UNAVAILABLE", "UNCERTAIN_REGIME"}


def test_expected_value_exact_decomposition_and_cost_stress() -> None:
    observed = datetime(2026, 8, 28, 4, 39, tzinfo=UTC)
    base = estimate_net_value(
        quote=quote("CE", observed), expected_option_payoff=2.0, uncertainty=0.1, lot_size=65
    )
    stressed = estimate_net_value(
        quote=quote("CE", observed),
        expected_option_payoff=2.0,
        uncertainty=0.1,
        lot_size=65,
        slippage_fraction=0.0015,
        brokerage=120.0,
        statutory_rate=0.001875,
    )
    assert base.net_expected_value == pytest.approx(
        base.expected_option_payoff
        - base.expected_spread_cost
        - base.expected_slippage
        - base.brokerage
        - base.statutory_costs
        - base.uncertainty_penalty
        - base.liquidity_penalty
    )
    assert stressed.net_expected_value < base.net_expected_value


def test_future_quote_is_rejected() -> None:
    source = bars(drift=0.0003)
    features = build_feature_bundle(source, decision_time=source[-1].event_time)
    future = features.decision_time + timedelta(seconds=1)
    decision = decide_alpha_v4(
        features, ce_quote=quote("CE", future), pe_quote=quote("PE", future), provider_lot_size=65
    )
    assert decision.recommended_action is AlphaAction.HOLD
    assert decision.reason in {"OPTION_EVIDENCE_UNAVAILABLE", "UNCERTAIN_REGIME"}


def test_provider_lot_size_is_mandatory() -> None:
    source = bars(drift=0.0003)
    features = build_feature_bundle(source, decision_time=source[-1].event_time)
    decision = decide_alpha_v4(
        features,
        ce_quote=quote("CE", features.decision_time),
        pe_quote=quote("PE", features.decision_time),
        provider_lot_size=None,
    )
    assert decision.recommended_action is AlphaAction.HOLD
