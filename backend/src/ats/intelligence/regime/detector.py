"""Pure completed-feature regime classification."""

from __future__ import annotations

import math
from uuid import UUID, uuid5

from ats.contracts.domain import FeatureBundle
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.models import MarketContext, RegimeEvidence
from ats.contracts.intelligence.types import (
    LiquidityState,
    RegimeDirection,
    RegimeStructure,
    VolatilityState,
)

from .errors import RegimeInputError
from .models import RegimeDetectorConfiguration

_REGIME_NAMESPACE = UUID("938f1a98-5420-5dd7-9e6f-78c5051ad202")
_RETURN = "roc_3_fraction"
_VOLATILITY = "realized_volatility_3_population"
_POSITION = "rolling_price_position_3"
_REQUIRED = frozenset((_RETURN, _VOLATILITY, _POSITION))


def detect_regime(
    *,
    market_context: MarketContext,
    feature_history: tuple[FeatureBundle, ...],
    configuration: RegimeDetectorConfiguration,
) -> RegimeEvidence:
    """Produce frozen evidence from an as-of bounded feature history."""

    _validate_history(market_context, feature_history)
    current = feature_history[-1]
    familiarity = min(1.0, len(feature_history) / configuration.full_familiarity_bars)
    if (
        market_context.data_quality_state in (DataQualityState.INVALID, DataQualityState.UNKNOWN)
        or current.quality_flags
        or not _REQUIRED.issubset(current.features)
    ):
        return _evidence(
            market_context=market_context,
            current=current,
            configuration=configuration,
            support_window_bars=len(feature_history),
            direction=RegimeDirection.UNKNOWN,
            structure=RegimeStructure.UNKNOWN,
            volatility=VolatilityState.UNKNOWN,
            liquidity=LiquidityState.UNKNOWN,
            change_score=0.0,
            familiarity=familiarity,
            reasons=("INSUFFICIENT_QUALITY_OR_WARMUP",),
            quality=DataQualityState.UNKNOWN,
        )

    direction = _direction(current.features[_RETURN], configuration)
    structure = _structure(
        direction,
        current.features[_RETURN],
        current.features[_POSITION],
        configuration,
    )
    previous = feature_history[-2] if len(feature_history) > 1 else None
    volatility = _volatility(current.features[_VOLATILITY], previous, configuration)
    change_score = _change_score(current, previous, configuration)
    liquidity = market_context.liquidity_state
    quality = market_context.data_quality_state
    if liquidity is LiquidityState.UNKNOWN and quality is DataQualityState.GOOD:
        quality = DataQualityState.DEGRADED
    reasons = (
        f"DIRECTION_{direction.value}",
        f"STRUCTURE_{structure.value}",
        f"VOLATILITY_{volatility.value}",
        f"LIQUIDITY_{liquidity.value}",
    )
    return _evidence(
        market_context=market_context,
        current=current,
        configuration=configuration,
        support_window_bars=len(feature_history),
        direction=direction,
        structure=structure,
        volatility=volatility,
        liquidity=liquidity,
        change_score=change_score,
        familiarity=familiarity,
        reasons=reasons,
        quality=quality,
    )


def _validate_history(context: MarketContext, history: tuple[FeatureBundle, ...]) -> None:
    if not history:
        raise RegimeInputError("feature_history must be non-empty")
    current = history[-1]
    if current.feature_bundle_id != context.feature_bundle_id:
        raise RegimeInputError("current feature bundle does not match MarketContext")
    if current.snapshot_id != context.snapshot_id:
        raise RegimeInputError("current snapshot does not match MarketContext")
    seen: set[UUID] = set()
    for index, bundle in enumerate(history):
        if bundle.feature_bundle_id in seen:
            raise RegimeInputError("duplicate feature bundle")
        seen.add(bundle.feature_bundle_id)
        if bundle.feature_version != current.feature_version:
            raise RegimeInputError("mixed feature versions")
        if bundle.computed_at > context.as_of_time:
            raise RegimeInputError("future feature evidence is forbidden")
        if index and bundle.computed_at <= history[index - 1].computed_at:
            raise RegimeInputError("feature history must be strictly chronological")


def _direction(value: float, config: RegimeDetectorConfiguration) -> RegimeDirection:
    if value >= config.direction_threshold:
        return RegimeDirection.UP
    if value <= -config.direction_threshold:
        return RegimeDirection.DOWN
    return RegimeDirection.FLAT


def _structure(
    direction: RegimeDirection,
    momentum: float,
    price_position: float,
    config: RegimeDetectorConfiguration,
) -> RegimeStructure:
    if direction is RegimeDirection.UP and price_position >= config.breakout_high:
        return RegimeStructure.BREAKOUT
    if direction is RegimeDirection.DOWN and price_position <= config.breakout_low:
        return RegimeStructure.BREAKOUT
    if abs(momentum) >= config.trend_threshold:
        return RegimeStructure.TREND
    if direction is RegimeDirection.FLAT:
        return RegimeStructure.RANGE
    return RegimeStructure.TRANSITION


def _volatility(
    value: float,
    previous: FeatureBundle | None,
    config: RegimeDetectorConfiguration,
) -> VolatilityState:
    if previous is not None and _VOLATILITY in previous.features:
        prior = previous.features[_VOLATILITY]
        if prior > 0:
            ratio = value / prior
            if ratio >= config.expansion_ratio:
                return VolatilityState.EXPANDING
            if ratio <= config.contraction_ratio:
                return VolatilityState.CONTRACTING
    if value <= config.low_volatility_threshold:
        return VolatilityState.LOW
    if value >= config.high_volatility_threshold:
        return VolatilityState.HIGH
    return VolatilityState.NORMAL


def _change_score(
    current: FeatureBundle,
    previous: FeatureBundle | None,
    config: RegimeDetectorConfiguration,
) -> float:
    if previous is None or not _REQUIRED.issubset(previous.features):
        return 0.0
    return_change = abs(current.features[_RETURN] - previous.features[_RETURN])
    volatility_change = abs(current.features[_VOLATILITY] - previous.features[_VOLATILITY])
    score = (
        return_change / config.change_return_scale
        + volatility_change / config.change_volatility_scale
    ) / 2.0
    return float(min(1.0, score)) if math.isfinite(score) else 1.0


def _evidence(
    *,
    market_context: MarketContext,
    current: FeatureBundle,
    configuration: RegimeDetectorConfiguration,
    support_window_bars: int,
    direction: RegimeDirection,
    structure: RegimeStructure,
    volatility: VolatilityState,
    liquidity: LiquidityState,
    change_score: float,
    familiarity: float,
    reasons: tuple[str, ...],
    quality: DataQualityState,
) -> RegimeEvidence:
    identity = (
        f"{market_context.market_context_id}:{configuration.detector_id}:"
        f"{configuration.detector_version}:{current.input_hash}"
    )
    evidence = RegimeEvidence(
        schema_version="1.0",
        regime_evidence_id=uuid5(_REGIME_NAMESPACE, identity),
        market_context_id=market_context.market_context_id,
        instrument_id=market_context.instrument_id,
        timeframe=market_context.timeframe,
        as_of_time=market_context.as_of_time,
        data_cutoff=market_context.data_cutoff,
        detector_id=configuration.detector_id,
        detector_version=configuration.detector_version,
        direction=direction,
        structure=structure,
        volatility=volatility,
        liquidity=liquidity,
        change_score=float(change_score),
        regime_familiarity=float(familiarity),
        support_window_bars=support_window_bars,
        reason_codes=reasons,
        quality_state=quality,
        payload_hash="0" * 64,
    )
    return evidence.model_copy(update={"payload_hash": compute_payload_hash(evidence)})


__all__ = ["detect_regime"]
