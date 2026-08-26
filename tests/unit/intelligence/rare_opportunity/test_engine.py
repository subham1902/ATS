from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.domain.hashing import compute_payload_hash
from ats.intelligence.rare_opportunity import (
    AnalogueSupport,
    HistoricalAnalogue,
    OpportunityClass,
    OptionConvexityInput,
    PatternState,
    RareOpportunityPolicy,
    assess_rare_opportunity,
    encode_pattern_state,
    find_historical_analogues,
    material_wake_for,
)
from ats.market.derivatives.active_window import MarketStateFreshness

NOW = datetime(2026, 8, 27, 5, 0, tzinfo=UTC)


def state(*, anomaly: bool = False, spread: float = 0.01) -> PatternState:
    boost = 1.5 if anomaly else 0.01
    return PatternState(
        state_id=uuid4(),
        as_of=NOW,
        data_cutoff=NOW,
        regime="TRENDING",
        returns_1s=boost,
        returns_5s=boost,
        returns_15s=boost,
        returns_1m=boost,
        returns_5m=boost,
        acceleration=boost,
        realized_volatility=0.02,
        range_compression=0.1 if anomaly else 0.9,
        breakout_magnitude=boost,
        spread_fraction=spread,
        volume_rate=3.0 if anomaly else 1.0,
        oi_change=0.5 if anomaly else None,
        iv_change=0.5 if anomaly else None,
        premium_acceleration=boost,
        liquidity_score=0.9,
    )


def history(current: PatternState, count: int = 25) -> tuple[HistoricalAnalogue, ...]:
    vector = encode_pattern_state(current)
    return tuple(
        HistoricalAnalogue(
            analogue_id=uuid4(),
            state_time=NOW - timedelta(days=count - index + 2),
            available_to_strategy_time=NOW - timedelta(days=count - index + 1),
            regime=current.regime,
            vector=vector,
            favorable_excursion=0.04,
            adverse_excursion=-0.01,
            forward_return=0.02,
            forward_volatility=0.03,
        )
        for index in range(count)
    )


def option(**changes: object) -> OptionConvexityInput:
    values: dict[str, object] = {
        "instrument_key": "NSE_FO|actual-contract",
        "premium": Decimal("10"),
        "delta": 0.5,
        "gamma": 0.02,
        "theta_per_day": -0.5,
        "iv": 0.2,
        "spread_cost": Decimal("0.25"),
        "slippage_cost": Decimal("0.25"),
        "fee_cost": Decimal("0.10"),
        "liquidity_score": 0.9,
        "time_to_expiry_days": Decimal("2"),
        "median_underlying_move": 20.0,
        "tail_underlying_move": 100.0,
        "execution_uncertainty": Decimal("0.25"),
        "calibration_uncertainty": Decimal("0.25"),
        "freshness": MarketStateFreshness.FRESH,
        "reference_valid": True,
    }
    values.update(changes)
    return OptionConvexityInput.model_validate(values)


def assess(current: PatternState, selected: OptionConvexityInput | None = None):
    policy = RareOpportunityPolicy()
    analogues = find_historical_analogues(current, history(current), policy)
    return assess_rare_opportunity(
        state=current, option=selected or option(), analogues=analogues, policy=policy
    )


def test_normal_state_is_not_misclassified_as_rare() -> None:
    result = assess(state(), option(tail_underlying_move=20.0))
    assert result.opportunity_class is OpportunityClass.STANDARD


def test_compression_expansion_and_convex_option_can_be_rare() -> None:
    result = assess(state(anomaly=True))
    assert result.eligible
    assert result.opportunity_class is OpportunityClass.RARE_EVENT
    assert result.payload_hash == compute_payload_hash(result)
    assert "CONVEX_OPPORTUNITY_DETECTED" in result.reason_codes


def test_low_liquidity_and_wide_spread_reject() -> None:
    current = state(anomaly=True, spread=0.20)
    result = assess(current, option(liquidity_score=0.1))
    assert not result.eligible
    assert {"LIQUIDITY_TOO_LOW", "SPREAD_TOO_WIDE"}.issubset(result.reason_codes)


def test_insufficient_analogue_support_fails_closed() -> None:
    current = state(anomaly=True)
    policy = RareOpportunityPolicy()
    analogues = find_historical_analogues(current, history(current, 3), policy)
    assert analogues.support is AnalogueSupport.INSUFFICIENT
    result = assess_rare_opportunity(state=current, option=option(), analogues=analogues)
    assert not result.eligible


def test_future_available_analogue_is_not_visible() -> None:
    current = state()
    future = history(current)[0].model_copy(
        update={"available_to_strategy_time": NOW + timedelta(1)}
    )
    result = find_historical_analogues(current, (future,), RareOpportunityPolicy())
    assert result.analogue_count == 0


def test_stale_or_invalid_reference_rejects_new_risk() -> None:
    result = assess(
        state(anomaly=True),
        option(freshness=MarketStateFreshness.STALE, reference_valid=False),
    )
    assert not result.eligible
    assert "STALE_OR_UNKNOWN_DATA" in result.reason_codes
    assert "INSTRUMENT_REFERENCE_INVALID" in result.reason_codes


def test_negative_net_economics_reject() -> None:
    result = assess(
        state(anomaly=True),
        option(
            median_underlying_move=0.1,
            tail_underlying_move=0.2,
            execution_uncertainty=Decimal("5"),
            calibration_uncertainty=Decimal("5"),
        ),
    )
    assert not result.eligible
    assert "EXPECTED_NET_VALUE_NOT_POSITIVE" in result.reason_codes


def test_r10x_has_no_financial_authority_and_budget_is_only_an_envelope() -> None:
    result = assess(state(anomaly=True))
    assert result.convexity_budget_fraction == Decimal("0.05")
    for forbidden in ("place_order", "reserve_capital", "authorize", "mint_token"):
        assert not hasattr(result, forbidden)


def test_convex_detection_maps_to_existing_material_wake_taxonomy() -> None:
    assessment = assess(state(anomaly=True))
    wake = material_wake_for(assessment, occurred_at=NOW)
    assert wake is not None
    assert wake.kind.value == "NEW_HIGH_QUALITY_OPPORTUNITY"
    assert wake.scope.startswith("CONVEX_OPPORTUNITY_DETECTED:")
