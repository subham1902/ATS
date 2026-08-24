"""Frozen metadata for the compact deterministic R01 feature registry."""

from __future__ import annotations

from typing import Literal

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, PositiveInt
from ats.contracts.enums import ATSStringEnum
from ats.contracts.intelligence.types import RegisteredCode


class FeatureOutputSemantic(ATSStringEnum):
    """Closed output semantics supported by the A02 FeatureBundle boundary."""

    FINITE_FLOAT = "FINITE_FLOAT"


class FeatureDefinition(ATSBaseModel):
    """Data-only feature metadata; formula text is explanatory, not executable."""

    feature_code: RegisteredCode
    feature_version: Literal["1.0.0"]
    lookback_bars: PositiveInt
    warmup_bars: PositiveInt
    output_semantic: FeatureOutputSemantic
    formula: NonEmptyStr


class FeatureConfiguration(ATSBaseModel):
    """Closed v1 configuration; rolling periods are part of registry semantics."""

    registry_version: Literal["1.0.0"] = "1.0.0"


_FINITE = FeatureOutputSemantic.FINITE_FLOAT

V1_FEATURE_REGISTRY: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        feature_code="simple_return",
        feature_version="1.0.0",
        lookback_bars=2,
        warmup_bars=2,
        output_semantic=_FINITE,
        formula="close[t] / close[t-1] - 1 (fraction)",
    ),
    FeatureDefinition(
        feature_code="log_return",
        feature_version="1.0.0",
        lookback_bars=2,
        warmup_bars=2,
        output_semantic=_FINITE,
        formula="ln(close[t] / close[t-1])",
    ),
    FeatureDefinition(
        feature_code="candle_body",
        feature_version="1.0.0",
        lookback_bars=1,
        warmup_bars=1,
        output_semantic=_FINITE,
        formula="close[t] - open[t]",
    ),
    FeatureDefinition(
        feature_code="candle_range",
        feature_version="1.0.0",
        lookback_bars=1,
        warmup_bars=1,
        output_semantic=_FINITE,
        formula="high[t] - low[t]",
    ),
    FeatureDefinition(
        feature_code="upper_wick",
        feature_version="1.0.0",
        lookback_bars=1,
        warmup_bars=1,
        output_semantic=_FINITE,
        formula="high[t] - max(open[t], close[t])",
    ),
    FeatureDefinition(
        feature_code="lower_wick",
        feature_version="1.0.0",
        lookback_bars=1,
        warmup_bars=1,
        output_semantic=_FINITE,
        formula="min(open[t], close[t]) - low[t]",
    ),
    FeatureDefinition(
        feature_code="atr_3_sma",
        feature_version="1.0.0",
        lookback_bars=4,
        warmup_bars=4,
        output_semantic=_FINITE,
        formula="mean(last 3 true ranges); TR uses prior completed close",
    ),
    FeatureDefinition(
        feature_code="realized_volatility_3_population",
        feature_version="1.0.0",
        lookback_bars=4,
        warmup_bars=4,
        output_semantic=_FINITE,
        formula="population standard deviation of last 3 simple returns",
    ),
    FeatureDefinition(
        feature_code="roc_3_fraction",
        feature_version="1.0.0",
        lookback_bars=4,
        warmup_bars=4,
        output_semantic=_FINITE,
        formula="close[t] / close[t-3] - 1 (fraction)",
    ),
    FeatureDefinition(
        feature_code="rolling_volume_mean_3",
        feature_version="1.0.0",
        lookback_bars=3,
        warmup_bars=3,
        output_semantic=_FINITE,
        formula="arithmetic mean of volume[t-2:t], inclusive",
    ),
    FeatureDefinition(
        feature_code="relative_volume_3",
        feature_version="1.0.0",
        lookback_bars=3,
        warmup_bars=3,
        output_semantic=_FINITE,
        formula="volume[t] / rolling_volume_mean_3; zero baseline => 0",
    ),
    FeatureDefinition(
        feature_code="rolling_price_position_3",
        feature_version="1.0.0",
        lookback_bars=3,
        warmup_bars=3,
        output_semantic=_FINITE,
        formula="(close[t]-trailing low)/(trailing high-trailing low); zero range => 0.5",
    ),
)

V1_FEATURE_CODES = tuple(item.feature_code for item in V1_FEATURE_REGISTRY)


__all__ = [
    "FeatureConfiguration",
    "FeatureDefinition",
    "FeatureOutputSemantic",
    "V1_FEATURE_CODES",
    "V1_FEATURE_REGISTRY",
]
