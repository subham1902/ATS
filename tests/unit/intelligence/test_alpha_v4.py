from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from ats.intelligence.alpha_v4 import (
    AlphaAction,
    AlphaBar,
    AlphaOptionQuote,
    AlphaRegime,
    EconomicEvidenceProvenance,
    EdgeEvaluationState,
    ExpectedOptionPayoffEvidence,
    build_feature_bundle,
    decide_alpha_v4,
    estimate_net_value,
    evaluate_alpha_v4,
)
from ats.market.derivatives.option_universe import DEFAULT_MAXIMUM_QUOTE_AGE_MS
from ats.trading_runtime.shadow_championship import MarketObservationContext, ShadowC0


def bars(*, drift: float = 0.0, alternating: bool = False) -> tuple[AlphaBar, ...]:
    start = datetime(2026, 8, 28, 4, 0, tzinfo=UTC)
    result = []
    price = 24000.0
    for index in range(40):
        direction = -1.0 if alternating and index % 2 else 1.0
        price *= 1.0 + direction * drift
        event_time = start + timedelta(minutes=index)
        source_time = event_time + timedelta(milliseconds=10)
        ingest_time = source_time + timedelta(milliseconds=10)
        available_time = ingest_time + timedelta(milliseconds=10)
        result.append(
            AlphaBar(
                event_time,
                source_time,
                ingest_time,
                available_time,
                price,
                price + 1,
                price - 1,
                price,
                1000 + index,
            )
        )
    return tuple(result)


def decision_time(source: tuple[AlphaBar, ...]) -> datetime:
    value = source[-1].available_to_strategy_time
    assert value is not None
    return value


def quote(
    option_type: str,
    observed_at: datetime | None,
    *,
    bid: float = 99.9,
    ask: float = 100.0,
) -> AlphaOptionQuote:
    return AlphaOptionQuote(
        "NSE_FO|TEST", option_type, "2026-09-03", 24000.0, bid, ask, observed_at
    )


def payoff(
    as_of: datetime,
    value: float,
    provenance: EconomicEvidenceProvenance = EconomicEvidenceProvenance.SYNTHETIC_TEST_ONLY,
) -> ExpectedOptionPayoffEvidence:
    return ExpectedOptionPayoffEvidence(value, provenance, "TEST_PAYOFF", "1.0.0", as_of)


def decide(
    source: tuple[AlphaBar, ...],
    *,
    option_quote: AlphaOptionQuote | None,
    payoff_evidence: ExpectedOptionPayoffEvidence | None = None,
    maximum_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
    allow_test: bool = False,
):
    cutoff = decision_time(source)
    features = build_feature_bundle(source, decision_time=cutoff)
    return decide_alpha_v4(
        features,
        ce_quote=option_quote,
        pe_quote=option_quote,
        provider_lot_size=65,
        expected_payoff_evidence=payoff_evidence,
        maximum_option_quote_age_ms=maximum_age_ms,
        allow_synthetic_test_economics=allow_test,
    )


def test_feature_factory_is_deterministic_and_has_all_horizons() -> None:
    source = bars(drift=0.0002)
    cutoff = decision_time(source)
    assert build_feature_bundle(source, decision_time=cutoff) == build_feature_bundle(
        source, decision_time=cutoff
    )
    assert set(build_feature_bundle(source, decision_time=cutoff).returns) == {
        1,
        3,
        5,
        10,
        15,
        30,
    }


@pytest.mark.parametrize(
    ("index", "changes"),
    [
        (0, {"event_time": datetime(2026, 8, 28, 4, 1, tzinfo=UTC)}),
        (0, {"source_time": datetime(2026, 8, 28, 4, 1, tzinfo=UTC)}),
        (0, {"ingest_time": datetime(2026, 8, 28, 4, 1, tzinfo=UTC)}),
        (0, {"available_to_strategy_time": datetime(2026, 8, 28, 5, 0, tzinfo=UTC)}),
        (-1, {"event_time": datetime(2026, 8, 28, 5, 0, tzinfo=UTC)}),
        (0, {"source_time": None}),
        (0, {"source_time": datetime(2026, 8, 28, 4, 0)}),
    ],
)
def test_invalid_or_missing_four_clock_input_fails_closed(
    index: int, changes: dict[str, datetime | None]
) -> None:
    source = list(bars(drift=0.0003))
    source[index] = replace(source[index], **changes)
    result = evaluate_alpha_v4(
        tuple(source),
        decision_time=decision_time(bars()),
        ce_quote=None,
        pe_quote=None,
        provider_lot_size=None,
    )
    assert result.recommended_action is AlphaAction.HOLD
    assert result.reason == "INVALID_TEMPORAL_EVIDENCE"
    assert result.edge_evaluation_state is EdgeEvaluationState.EDGE_NOT_EVALUABLE


def test_equal_four_clocks_are_valid_and_non_utc_offset_fails_closed() -> None:
    source = bars()
    stamp = source[0].event_time
    assert stamp is not None
    equal = replace(
        source[0], source_time=stamp, ingest_time=stamp, available_to_strategy_time=stamp
    )
    offset = timezone(timedelta(hours=5, minutes=30))
    equivalent = replace(equal, source_time=stamp.astimezone(offset))
    first = (equal,) + source[1:]
    second = (equivalent,) + source[1:]
    build_feature_bundle(first, decision_time=decision_time(first))
    result = evaluate_alpha_v4(
        second,
        decision_time=decision_time(second),
        ce_quote=None,
        pe_quote=None,
        provider_lot_size=None,
    )
    assert result.reason == "INVALID_TEMPORAL_EVIDENCE"
    assert result.recommended_action is AlphaAction.HOLD


def test_real_quote_without_payoff_model_is_directional_research_only() -> None:
    source = bars(drift=0.0003)
    result = decide(source, option_quote=quote("CE", decision_time(source)))
    assert result.p_up != 0.5
    assert result.expected_value is None
    assert result.recommended_action is AlphaAction.HOLD
    assert result.reason == "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("age_ms", "reason"),
    [
        (DEFAULT_MAXIMUM_QUOTE_AGE_MS, "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"),
        (DEFAULT_MAXIMUM_QUOTE_AGE_MS + 1, "STALE_OPTION_EVIDENCE"),
        (60_000, "STALE_OPTION_EVIDENCE"),
        (-1, "FUTURE_OPTION_EVIDENCE"),
    ],
)
def test_option_quote_freshness_boundaries(age_ms: int, reason: str) -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source)
    result = decide(source, option_quote=quote("CE", cutoff - timedelta(milliseconds=age_ms)))
    assert result.recommended_action is AlphaAction.HOLD
    assert result.reason == reason


def test_missing_and_invalid_option_timestamps_fail_closed() -> None:
    source = bars(drift=0.0003)
    assert decide(source, option_quote=None).reason == "MISSING_OPTION_EVIDENCE"
    assert decide(source, option_quote=quote("CE", None)).reason == "INVALID_TEMPORAL_EVIDENCE"


def test_stale_underlying_blocks_fresh_option_evidence() -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source) + timedelta(milliseconds=DEFAULT_MAXIMUM_QUOTE_AGE_MS + 1)
    result = evaluate_alpha_v4(
        source,
        decision_time=cutoff,
        ce_quote=quote("CE", cutoff),
        pe_quote=quote("PE", cutoff),
        provider_lot_size=65,
        expected_payoff_evidence=payoff(cutoff, 5.0),
        allow_synthetic_test_economics=True,
    )
    assert result.recommended_action is AlphaAction.HOLD
    assert result.reason == "STALE_UNDERLYING_EVIDENCE"


def test_stale_selected_contract_blocks_mixed_ce_pe_evidence() -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source)
    features = build_feature_bundle(source, decision_time=cutoff)
    result = decide_alpha_v4(
        features,
        ce_quote=quote("CE", cutoff - timedelta(seconds=3)),
        pe_quote=quote("PE", cutoff),
        provider_lot_size=65,
        expected_payoff_evidence=payoff(cutoff, 5.0),
        allow_synthetic_test_economics=True,
    )
    assert result.preferred_expression is AlphaAction.LONG_CE
    assert result.recommended_action is AlphaAction.HOLD
    assert result.reason == "STALE_OPTION_EVIDENCE"


def test_synthetic_payoff_fixture_is_rejected_without_explicit_test_gate() -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source)
    result = decide(
        source,
        option_quote=quote("CE", cutoff),
        payoff_evidence=payoff(cutoff, 5.0),
    )
    assert result.expected_value is None
    assert result.reason == "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"


def test_explicit_test_payoff_can_exercise_positive_shadow_math_only() -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source)
    result = decide(
        source,
        option_quote=quote("CE", cutoff),
        payoff_evidence=payoff(cutoff, 5.0),
        allow_test=True,
    )
    assert result.expected_value is not None
    assert result.expected_value.net_expected_value > 0
    assert result.recommended_action is AlphaAction.LONG_CE
    assert result.shadow_status == "SHADOW_ONLY"
    assert result.payoff_provenance is EconomicEvidenceProvenance.SYNTHETIC_TEST_ONLY


def test_legitimate_negative_payoff_and_cost_dominated_payoff_hold() -> None:
    source = bars(drift=0.0003)
    cutoff = decision_time(source)
    for value in (-1.0, 0.1):
        result = decide(
            source,
            option_quote=quote("CE", cutoff),
            payoff_evidence=payoff(
                cutoff,
                value,
                EconomicEvidenceProvenance.REAL_OPTION_PAYOFF_MODEL,
            ),
        )
        assert result.expected_value is not None
        assert result.expected_value.net_expected_value <= 10.0
        assert result.recommended_action is AlphaAction.HOLD
        assert result.reason == "NO_EDGE_AFTER_COSTS"


def test_costs_or_uncertainty_can_only_reduce_expected_value() -> None:
    observed = datetime(2026, 8, 28, 4, 39, tzinfo=UTC)
    base = estimate_net_value(
        quote=quote("CE", observed), expected_option_payoff=2.0, uncertainty=0.1, lot_size=65
    )
    high_uncertainty = estimate_net_value(
        quote=quote("CE", observed), expected_option_payoff=2.0, uncertainty=1.0, lot_size=65
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
    exact = (
        base.expected_option_payoff
        - base.expected_spread_cost
        - base.expected_slippage
        - base.brokerage
        - base.statutory_costs
        - base.uncertainty_penalty
        - base.liquidity_penalty
    )
    assert base.net_expected_value == pytest.approx(exact)
    assert high_uncertainty.net_expected_value < base.net_expected_value
    assert stressed.net_expected_value < base.net_expected_value


def test_quiet_market_does_not_force_trade() -> None:
    source = bars(drift=0.00001, alternating=True)
    cutoff = decision_time(source)
    result = decide_alpha_v4(
        build_feature_bundle(source, decision_time=cutoff),
        ce_quote=quote("CE", cutoff),
        pe_quote=quote("PE", cutoff),
        provider_lot_size=65,
        expected_payoff_evidence=payoff(cutoff, 0.1),
        allow_synthetic_test_economics=True,
    )
    assert result.regime in {AlphaRegime.RANGE, AlphaRegime.UNCERTAIN}
    assert result.recommended_action is AlphaAction.HOLD


def test_no_execution_authority_is_exposed() -> None:
    source = bars(drift=0.0003)
    result = evaluate_alpha_v4(
        source,
        decision_time=decision_time(source),
        ce_quote=None,
        pe_quote=None,
        provider_lot_size=None,
    )
    assert result.shadow_status == "SHADOW_ONLY"
    assert not hasattr(result, "issue_token")
    assert not hasattr(result, "create_order_intent")
    assert not hasattr(result, "submit_order")


@pytest.mark.parametrize("roc_3", [-0.2, -0.01, 0.0, 0.01, 0.2])
def test_c0_formula_and_threshold_are_unchanged(roc_3: float) -> None:
    model = ShadowC0()
    now = datetime(2026, 8, 28, 4, 39, tzinfo=UTC)
    prediction = model.predict(
        MarketObservationContext(
            market_state_id="c0-isolation",
            feature_bundle_id="c0-features",
            decision_time=now,
            session="TEST",
            underlying="NIFTY",
            spot_price=24000.0,
            vwap=24000.0,
            features={"roc_3": roc_3},
        )
    )
    expected = round(max(0.05, min(0.95, 0.50 + 5.0 * roc_3)), 4)
    assert prediction.bullish_probability == expected
    assert prediction.activation_threshold == 0.55
