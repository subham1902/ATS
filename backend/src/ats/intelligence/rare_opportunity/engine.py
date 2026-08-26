"""Deterministic analogue, anomaly, and long-option convexity scoring."""

from __future__ import annotations

from decimal import Decimal
from statistics import fmean
from uuid import NAMESPACE_URL, uuid4, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_governance import MaterialWakeEvent, MaterialWakeKind
from ats.market.derivatives.active_window import MarketStateFreshness

from .models import (
    AnalogueDistribution,
    AnalogueSupport,
    HistoricalAnalogue,
    OpportunityClass,
    OptionConvexityInput,
    PatternState,
    RareOpportunityAssessment,
    RareOpportunityPolicy,
)


def encode_pattern_state(state: PatternState) -> tuple[float, ...]:
    return (
        state.returns_1s,
        state.returns_5s,
        state.returns_15s,
        state.returns_1m,
        state.returns_5m,
        state.acceleration,
        state.realized_volatility,
        state.range_compression,
        state.breakout_magnitude,
        state.spread_fraction,
        state.volume_rate,
        state.oi_change or 0.0,
        state.iv_change or 0.0,
        state.premium_acceleration,
        state.liquidity_score,
    )


def find_historical_analogues(
    state: PatternState,
    history: tuple[HistoricalAnalogue, ...],
    policy: RareOpportunityPolicy,
) -> AnalogueDistribution:
    current = encode_pattern_state(state)
    eligible = tuple(
        item
        for item in history
        if item.regime == state.regime
        and item.state_time < state.as_of
        and item.available_to_strategy_time <= state.data_cutoff
        and len(item.vector) == len(current)
    )
    ranked = sorted(
        ((_distance(current, item.vector), item) for item in eligible),
        key=lambda pair: (pair[0], pair[1].state_time, pair[1].analogue_id),
    )[: policy.nearest_analogue_count]
    if len(ranked) < policy.minimum_analogue_support:
        return AnalogueDistribution(
            support=AnalogueSupport.INSUFFICIENT,
            analogue_count=len(ranked),
            mean_similarity=None,
            favorable_excursions=(),
            adverse_excursions=(),
            forward_returns=(),
            forward_volatilities=(),
            reason_codes=("INSUFFICIENT_ANALOGUE_SUPPORT",),
        )
    return AnalogueDistribution(
        support=AnalogueSupport.SUFFICIENT,
        analogue_count=len(ranked),
        mean_similarity=fmean(1.0 / (1.0 + distance) for distance, _ in ranked),
        favorable_excursions=tuple(item.favorable_excursion for _, item in ranked),
        adverse_excursions=tuple(item.adverse_excursion for _, item in ranked),
        forward_returns=tuple(item.forward_return for _, item in ranked),
        forward_volatilities=tuple(item.forward_volatility for _, item in ranked),
        reason_codes=("TIME_ORDERED_ANALOGUES_AVAILABLE",),
    )


def assess_rare_opportunity(
    *,
    state: PatternState,
    option: OptionConvexityInput,
    analogues: AnalogueDistribution,
    policy: RareOpportunityPolicy | None = None,
) -> RareOpportunityAssessment:
    policy = policy or RareOpportunityPolicy()
    anomaly = _anomaly_score(state)
    costs = option.spread_cost + option.slippage_cost + option.fee_cost
    theta_cost = Decimal(str(abs(option.theta_per_day))) * min(
        option.time_to_expiry_days, Decimal("1")
    )
    uncertainty = option.execution_uncertainty + option.calibration_uncertainty
    credible_downside = option.premium + costs + uncertainty
    median_upside = _option_move(option, option.median_underlying_move, theta_cost, costs)
    tail_upside = _option_move(option, option.tail_underlying_move, theta_cost, costs)
    expected_net = (
        median_upside * Decimal("0.50")
        + tail_upside * Decimal("0.15")
        - credible_downside * Decimal("0.35")
        - uncertainty
    )
    asymmetry = tail_upside / credible_downside if credible_downside else Decimal(0)
    reasons: list[str] = []
    if option.freshness is not MarketStateFreshness.FRESH:
        reasons.append("STALE_OR_UNKNOWN_DATA")
    if not option.reference_valid:
        reasons.append("INSTRUMENT_REFERENCE_INVALID")
    if state.spread_fraction > float(policy.maximum_spread_fraction):
        reasons.append("SPREAD_TOO_WIDE")
    if option.liquidity_score < float(policy.minimum_liquidity):
        reasons.append("LIQUIDITY_TOO_LOW")
    if analogues.support is AnalogueSupport.INSUFFICIENT:
        reasons.append("INSUFFICIENT_ANALOGUE_SUPPORT")
    if expected_net <= policy.minimum_expected_net_value:
        reasons.append("EXPECTED_NET_VALUE_NOT_POSITIVE")
    eligible = not reasons
    classification = OpportunityClass.STANDARD
    if (
        eligible
        and asymmetry >= policy.rare_asymmetry_ratio
        and Decimal(str(anomaly)) >= policy.rare_anomaly_score
    ):
        classification = OpportunityClass.RARE_EVENT
    elif eligible and asymmetry >= policy.convex_asymmetry_ratio:
        classification = OpportunityClass.CONVEX
    elif eligible and Decimal(str(anomaly)) >= policy.high_anomaly_score:
        classification = OpportunityClass.HIGH_CONVICTION
    if eligible:
        reasons.append(
            "CONVEX_OPPORTUNITY_DETECTED"
            if classification in (OpportunityClass.CONVEX, OpportunityClass.RARE_EVENT)
            else "POSITIVE_NET_ECONOMICS"
        )
    identity = canonical_sha256(
        {
            "state": state.model_dump(mode="json"),
            "option": option.model_dump(mode="json"),
            "analogues": analogues.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
        }
    )
    draft = RareOpportunityAssessment(
        assessment_id=uuid5(NAMESPACE_URL, identity),
        instrument_key=option.instrument_key,
        opportunity_class=classification,
        eligible=eligible,
        anomaly_score=anomaly,
        analogue_count=analogues.analogue_count,
        credible_downside=credible_downside,
        median_upside=median_upside,
        tail_upside=tail_upside,
        expected_net_value=expected_net,
        payoff_asymmetry_ratio=asymmetry,
        convexity_budget_fraction=policy.convexity_budget_fraction,
        reason_codes=tuple(reasons),
        input_hash=identity,
        payload_hash="0" * 64,
    )
    return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def material_wake_for(
    assessment: RareOpportunityAssessment, *, occurred_at: UTCDateTime
) -> MaterialWakeEvent | None:
    """Map convex evidence onto the frozen high-quality-opportunity wake kind."""

    if not assessment.eligible or assessment.opportunity_class not in (
        OpportunityClass.CONVEX,
        OpportunityClass.RARE_EVENT,
    ):
        return None
    return MaterialWakeEvent(
        event_id=uuid4(),
        kind=MaterialWakeKind.NEW_HIGH_QUALITY_OPPORTUNITY,
        scope=f"CONVEX_OPPORTUNITY_DETECTED:{assessment.instrument_key}",
        occurred_at=occurred_at,
        evidence_refs=(assessment.assessment_id,),
        context_hash=assessment.payload_hash,
    )


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return fmean(abs(a - b) / (1.0 + abs(a) + abs(b)) for a, b in zip(left, right, strict=True))


def _anomaly_score(state: PatternState) -> float:
    expansion = max(0.0, state.breakout_magnitude) + max(0.0, 1.0 - state.range_compression)
    participation = max(0.0, state.volume_rate - 1.0) + max(0.0, state.premium_acceleration)
    derivatives = max(0.0, state.iv_change or 0.0) + max(0.0, state.oi_change or 0.0)
    return state.acceleration + expansion + participation + derivatives


def _option_move(
    option: OptionConvexityInput, underlying_move: float, theta_cost: Decimal, costs: Decimal
) -> Decimal:
    move = Decimal(str(abs(underlying_move)))
    gross = (
        Decimal(str(abs(option.delta))) * move
        + Decimal("0.5") * Decimal(str(max(0.0, option.gamma))) * move * move
    )
    return max(Decimal(0), gross - theta_cost - costs)


__all__ = [
    "assess_rare_opportunity",
    "encode_pattern_state",
    "find_historical_analogues",
    "material_wake_for",
]
