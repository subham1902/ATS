"""Deterministic Alpha V4 shadow research decision layer.

This module has no execution dependencies. It consumes immutable, cutoff-bounded
bar and option-quote evidence and returns an economic HOLD/LONG_CE/LONG_PE
recommendation for research recording only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from statistics import fmean, pstdev
from typing import TypeGuard

from ats.market.derivatives.option_universe import DEFAULT_MAXIMUM_QUOTE_AGE_MS

HORIZONS_MINUTES = (1, 3, 5, 10, 15, 30)


class AlphaRegime(StrEnum):
    RANGE = "RANGE"
    TREND = "TREND"
    VOL_EXPANSION = "VOL_EXPANSION"
    RARE_EVENT = "RARE_EVENT"
    UNCERTAIN = "UNCERTAIN"


class AlphaAction(StrEnum):
    HOLD = "HOLD"
    LONG_CE = "LONG_CE"
    LONG_PE = "LONG_PE"


class EconomicEvidenceProvenance(StrEnum):
    REAL_OPTION_PAYOFF_MODEL = "REAL_OPTION_PAYOFF_MODEL"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class EdgeEvaluationState(StrEnum):
    EDGE_EVALUATED = "EDGE_EVALUATED"
    EDGE_NOT_EVALUABLE = "EDGE_NOT_EVALUABLE"


@dataclass(frozen=True)
class AlphaBar:
    event_time: datetime | None
    source_time: datetime | None
    ingest_time: datetime | None
    available_to_strategy_time: datetime | None
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class AlphaOptionQuote:
    instrument_key: str
    option_type: str
    expiry: str
    strike: float
    bid: float
    ask: float
    observed_at: datetime | None
    open_interest: float | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None


@dataclass(frozen=True)
class AlphaFeatureBundle:
    decision_time: datetime
    latest_available_to_strategy_time: datetime
    returns: dict[int, float]
    velocity: float
    acceleration: float
    realized_volatility: float
    volatility_change: float
    range_position: float
    range_compression: float
    vwap_deviation: float
    volume_zscore: float
    trend_persistence: float
    missing_features: tuple[str, ...]


@dataclass(frozen=True)
class ExpectedValueBreakdown:
    expected_option_payoff: float
    expected_spread_cost: float
    expected_slippage: float
    brokerage: float
    statutory_costs: float
    uncertainty_penalty: float
    liquidity_penalty: float
    net_expected_value: float


@dataclass(frozen=True)
class ExpectedOptionPayoffEvidence:
    value_per_unit: float
    provenance: EconomicEvidenceProvenance
    model_id: str
    model_version: str
    as_of: datetime


@dataclass(frozen=True)
class AlphaV4Decision:
    p_up: float
    p_down: float
    p_range: float
    expected_move: float
    expected_volatility: float
    uncertainty: float
    regime: AlphaRegime
    active_specialist: str
    expected_value: ExpectedValueBreakdown | None
    preferred_expression: AlphaAction
    recommended_action: AlphaAction
    reason: str
    edge_evaluation_state: EdgeEvaluationState
    payoff_provenance: EconomicEvidenceProvenance | None = None
    shadow_status: str = "SHADOW_ONLY"


def _finite(values: tuple[float, ...]) -> bool:
    return all(math.isfinite(value) for value in values)


def _is_aware_utc(value: object) -> TypeGuard[datetime]:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return False
    offset = value.utcoffset()
    return offset is not None and offset.total_seconds() == 0


def _validate_decision_time(decision_time: datetime) -> None:
    if not _is_aware_utc(decision_time):
        raise ValueError("INVALID_TEMPORAL_EVIDENCE")


def _validate_bar_clocks(bar: AlphaBar, decision_time: datetime) -> None:
    clocks = (
        bar.event_time,
        bar.source_time,
        bar.ingest_time,
        bar.available_to_strategy_time,
    )
    if not all(_is_aware_utc(value) for value in clocks):
        raise ValueError("INVALID_TEMPORAL_EVIDENCE")
    event_time, source_time, ingest_time, available_time = clocks
    assert isinstance(event_time, datetime)
    assert isinstance(source_time, datetime)
    assert isinstance(ingest_time, datetime)
    assert isinstance(available_time, datetime)
    if not event_time <= source_time <= ingest_time <= available_time <= decision_time:
        raise ValueError("INVALID_TEMPORAL_EVIDENCE")


def build_feature_bundle(
    bars: tuple[AlphaBar, ...],
    *,
    decision_time: datetime,
    maximum_underlying_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
) -> AlphaFeatureBundle:
    """Build V4 features without reading information unavailable at cutoff."""

    _validate_decision_time(decision_time)
    for bar in bars:
        _validate_bar_clocks(bar, decision_time)
    latest_available = bars[-1].available_to_strategy_time if bars else None
    if (
        not isinstance(latest_available, datetime)
        or (decision_time - latest_available).total_seconds() * 1000 > maximum_underlying_age_ms
    ):
        raise ValueError("STALE_UNDERLYING_EVIDENCE")

    eligible = bars
    if len(eligible) < 31:
        raise ValueError("INSUFFICIENT_WARMUP: 31 completed one-minute bars required")
    if any(
        not _finite((b.open, b.high, b.low, b.close, b.volume))
        or min(b.open, b.high, b.low, b.close) <= 0
        or b.volume < 0
        for b in eligible
    ):
        raise ValueError("INVALID_NONFINITE_OR_NONPOSITIVE_BAR")
    if any(
        a.event_time is None or b.event_time is None or a.event_time >= b.event_time
        for a, b in zip(eligible, eligible[1:], strict=False)
    ):
        raise ValueError("NON_CHRONOLOGICAL_BARS")

    window = eligible[-31:]
    closes = [b.close for b in window]
    returns = {h: closes[-1] / closes[-1 - h] - 1.0 for h in HORIZONS_MINUTES}
    one_minute_returns = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    recent_vol = pstdev(one_minute_returns[-10:])
    prior_vol = pstdev(one_minute_returns[-20:-10])
    highs = [b.high for b in window[-15:]]
    lows = [b.low for b in window[-15:]]
    local_high, local_low = max(highs), min(lows)
    local_range = local_high - local_low
    prior_ranges = [b.high - b.low for b in window[-30:-15]]
    recent_ranges = [b.high - b.low for b in window[-15:]]
    prior_range_mean = fmean(prior_ranges)
    typical_volume = fmean(b.volume for b in window[-20:])
    volume_sigma = pstdev([b.volume for b in window[-20:]])
    cumulative_pv = sum(((b.high + b.low + b.close) / 3.0) * b.volume for b in window)
    cumulative_volume = sum(b.volume for b in window)
    vwap = cumulative_pv / cumulative_volume if cumulative_volume else closes[-1]
    signs = [1.0 if r > 0 else (-1.0 if r < 0 else 0.0) for r in one_minute_returns[-10:]]

    return AlphaFeatureBundle(
        decision_time=decision_time,
        latest_available_to_strategy_time=latest_available,
        returns=returns,
        velocity=returns[3] / 3.0,
        acceleration=returns[1] - (returns[3] / 3.0),
        realized_volatility=recent_vol,
        volatility_change=recent_vol - prior_vol,
        range_position=0.5 if local_range == 0 else (closes[-1] - local_low) / local_range,
        range_compression=(fmean(recent_ranges) / prior_range_mean) if prior_range_mean else 1.0,
        vwap_deviation=closes[-1] / vwap - 1.0,
        volume_zscore=0.0
        if volume_sigma == 0
        else (window[-1].volume - typical_volume) / volume_sigma,
        trend_persistence=abs(sum(signs)) / len(signs),
        missing_features=(),
    )


def classify_regime(features: AlphaFeatureBundle) -> AlphaRegime:
    vol = features.realized_volatility
    if not _finite(
        (
            vol,
            features.volatility_change,
            features.acceleration,
            features.trend_persistence,
            features.range_compression,
        )
    ):
        return AlphaRegime.UNCERTAIN
    if vol > 0.004 and abs(features.acceleration) > 0.002:
        return AlphaRegime.RARE_EVENT
    if features.volatility_change > max(0.0005, vol * 0.35):
        return AlphaRegime.VOL_EXPANSION
    if features.trend_persistence >= 0.6 and abs(features.returns[10]) >= 0.0015:
        return AlphaRegime.TREND
    if features.range_compression <= 1.05 and features.trend_persistence <= 0.5:
        return AlphaRegime.RANGE
    return AlphaRegime.UNCERTAIN


def _logistic(score: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-8.0, min(8.0, score))))


def specialist_probabilities(
    features: AlphaFeatureBundle, regime: AlphaRegime
) -> tuple[dict[str, float], str]:
    trend = _logistic(
        120.0
        * (0.45 * features.returns[3] + 0.35 * features.returns[10] + 0.20 * features.returns[30])
    )
    mean_reversion = _logistic(
        -5.0 * features.vwap_deviation - 1.8 * (features.range_position - 0.5)
    )
    breakout = _logistic(100.0 * features.returns[3] + 45.0 * features.acceleration)
    vol_expansion = _logistic(70.0 * features.returns[3] + 30.0 * features.acceleration)
    convexity = _logistic(100.0 * features.acceleration + 35.0 * features.returns[5])
    values = {
        "TREND": trend,
        "MEAN_REVERSION": mean_reversion,
        "BREAKOUT": breakout,
        "VOL_EXPANSION": vol_expansion,
        "R10_X": convexity,
    }
    active = {
        AlphaRegime.RANGE: "MEAN_REVERSION",
        AlphaRegime.TREND: "TREND",
        AlphaRegime.VOL_EXPANSION: "VOL_EXPANSION",
        AlphaRegime.RARE_EVENT: "R10_X",
        AlphaRegime.UNCERTAIN: "NONE",
    }[regime]
    return values, active


def estimate_net_value(
    *,
    quote: AlphaOptionQuote,
    expected_option_payoff: float,
    uncertainty: float,
    lot_size: int,
    slippage_fraction: float = 0.0005,
    brokerage: float = 40.0,
    statutory_rate: float = 0.000625,
) -> ExpectedValueBreakdown:
    if type(lot_size) is not int or lot_size <= 0:
        raise ValueError("INVALID_PROVIDER_LOT_SIZE")
    if quote.option_type not in {"CE", "PE"} or quote.ask < quote.bid or quote.bid <= 0:
        raise ValueError("INVALID_OPTION_QUOTE")
    spread = (quote.ask - quote.bid) * lot_size
    slippage = quote.ask * slippage_fraction * 2.0 * lot_size
    statutory = quote.ask * statutory_rate * lot_size
    uncertainty_penalty = max(0.0, uncertainty) * quote.ask * 0.02 * lot_size
    spread_fraction = (quote.ask - quote.bid) / quote.ask
    liquidity_penalty = max(0.0, spread_fraction - 0.01) * quote.ask * lot_size
    gross = expected_option_payoff * lot_size
    net = (
        gross - spread - slippage - brokerage - statutory - uncertainty_penalty - liquidity_penalty
    )
    return ExpectedValueBreakdown(
        gross,
        spread,
        slippage,
        brokerage,
        statutory,
        uncertainty_penalty,
        liquidity_penalty,
        net,
    )


def decide_alpha_v4(
    features: AlphaFeatureBundle,
    *,
    ce_quote: AlphaOptionQuote | None,
    pe_quote: AlphaOptionQuote | None,
    provider_lot_size: int | None,
    expected_payoff_evidence: ExpectedOptionPayoffEvidence | None = None,
    maximum_option_quote_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
    maximum_underlying_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
    allow_synthetic_test_economics: bool = False,
    safety_buffer: float = 10.0,
) -> AlphaV4Decision:
    underlying_evidence_valid = (
        _is_aware_utc(features.decision_time)
        and _is_aware_utc(features.latest_available_to_strategy_time)
        and features.latest_available_to_strategy_time <= features.decision_time
        and (features.decision_time - features.latest_available_to_strategy_time).total_seconds()
        * 1000
        <= maximum_underlying_age_ms
    )
    regime = classify_regime(features)
    specialists, active = specialist_probabilities(features, regime)
    probabilities = list(specialists.values())
    disagreement = pstdev(probabilities)
    uncertainty = min(1.0, disagreement + (0.35 if regime is AlphaRegime.UNCERTAIN else 0.0))
    p_up = 0.5 if active == "NONE" else specialists[active]
    p_range = max(0.0, min(1.0, 1.0 - abs(p_up - 0.5) * 2.0))
    expected_move = abs(features.returns[5])

    expression = AlphaAction.LONG_CE if p_up >= 0.5 else AlphaAction.LONG_PE
    quote = ce_quote if expression is AlphaAction.LONG_CE else pe_quote
    if not underlying_evidence_valid:
        reason = "STALE_UNDERLYING_EVIDENCE"
        ev = None
    elif regime is AlphaRegime.UNCERTAIN:
        reason = "UNCERTAIN_REGIME"
        ev = None
    elif quote is None or provider_lot_size is None:
        reason = "MISSING_OPTION_EVIDENCE"
        ev = None
    elif not _is_aware_utc(quote.observed_at):
        reason = "INVALID_TEMPORAL_EVIDENCE"
        ev = None
    elif quote.observed_at > features.decision_time:
        reason = "FUTURE_OPTION_EVIDENCE"
        ev = None
    elif (
        features.decision_time - quote.observed_at
    ).total_seconds() * 1000 > maximum_option_quote_age_ms:
        reason = "STALE_OPTION_EVIDENCE"
        ev = None
    elif expected_payoff_evidence is None:
        reason = "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"
        ev = None
    elif (
        not _is_aware_utc(expected_payoff_evidence.as_of)
        or expected_payoff_evidence.as_of > features.decision_time
        or not math.isfinite(expected_payoff_evidence.value_per_unit)
    ):
        reason = "INVALID_ECONOMIC_PAYOFF_EVIDENCE"
        ev = None
    elif (
        expected_payoff_evidence.provenance is EconomicEvidenceProvenance.SYNTHETIC_TEST_ONLY
        and not allow_synthetic_test_economics
    ):
        reason = "ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE"
        ev = None
    else:
        assert expected_payoff_evidence is not None
        ev = estimate_net_value(
            quote=quote,
            expected_option_payoff=expected_payoff_evidence.value_per_unit,
            uncertainty=uncertainty,
            lot_size=provider_lot_size,
        )
        reason = (
            "POSITIVE_NET_EDGE" if ev.net_expected_value > safety_buffer else "NO_EDGE_AFTER_COSTS"
        )

    action = (
        expression if ev is not None and ev.net_expected_value > safety_buffer else AlphaAction.HOLD
    )
    return AlphaV4Decision(
        p_up=p_up,
        p_down=1.0 - p_up,
        p_range=p_range,
        expected_move=expected_move,
        expected_volatility=features.realized_volatility,
        uncertainty=uncertainty,
        regime=regime,
        active_specialist=active,
        expected_value=ev,
        preferred_expression=expression,
        recommended_action=action,
        reason=reason,
        edge_evaluation_state=(
            EdgeEvaluationState.EDGE_EVALUATED
            if ev is not None
            else EdgeEvaluationState.EDGE_NOT_EVALUABLE
        ),
        payoff_provenance=(
            expected_payoff_evidence.provenance
            if ev is not None and expected_payoff_evidence is not None
            else None
        ),
    )


def evaluate_alpha_v4(
    bars: tuple[AlphaBar, ...],
    *,
    decision_time: datetime,
    ce_quote: AlphaOptionQuote | None,
    pe_quote: AlphaOptionQuote | None,
    provider_lot_size: int | None,
    expected_payoff_evidence: ExpectedOptionPayoffEvidence | None = None,
    maximum_option_quote_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
    maximum_underlying_age_ms: int = DEFAULT_MAXIMUM_QUOTE_AGE_MS,
    allow_synthetic_test_economics: bool = False,
    safety_buffer: float = 10.0,
) -> AlphaV4Decision:
    """Fail-closed ingress for decision-critical temporal evidence."""

    try:
        features = build_feature_bundle(
            bars,
            decision_time=decision_time,
            maximum_underlying_age_ms=maximum_underlying_age_ms,
        )
    except (TypeError, ValueError) as exc:
        reason = (
            "STALE_UNDERLYING_EVIDENCE"
            if str(exc) == "STALE_UNDERLYING_EVIDENCE"
            else "INVALID_TEMPORAL_EVIDENCE"
        )
        return AlphaV4Decision(
            p_up=0.5,
            p_down=0.5,
            p_range=1.0,
            expected_move=0.0,
            expected_volatility=0.0,
            uncertainty=1.0,
            regime=AlphaRegime.UNCERTAIN,
            active_specialist="NONE",
            expected_value=None,
            preferred_expression=AlphaAction.HOLD,
            recommended_action=AlphaAction.HOLD,
            reason=reason,
            edge_evaluation_state=EdgeEvaluationState.EDGE_NOT_EVALUABLE,
        )
    return decide_alpha_v4(
        features,
        ce_quote=ce_quote,
        pe_quote=pe_quote,
        provider_lot_size=provider_lot_size,
        expected_payoff_evidence=expected_payoff_evidence,
        maximum_option_quote_age_ms=maximum_option_quote_age_ms,
        maximum_underlying_age_ms=maximum_underlying_age_ms,
        allow_synthetic_test_economics=allow_synthetic_test_economics,
        safety_buffer=safety_buffer,
    )


__all__ = [
    "AlphaAction",
    "AlphaBar",
    "AlphaFeatureBundle",
    "AlphaOptionQuote",
    "AlphaRegime",
    "AlphaV4Decision",
    "EconomicEvidenceProvenance",
    "EdgeEvaluationState",
    "ExpectedValueBreakdown",
    "ExpectedOptionPayoffEvidence",
    "HORIZONS_MINUTES",
    "build_feature_bundle",
    "classify_regime",
    "decide_alpha_v4",
    "estimate_net_value",
    "evaluate_alpha_v4",
    "specialist_probabilities",
]
