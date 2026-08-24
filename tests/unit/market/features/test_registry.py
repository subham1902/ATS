from __future__ import annotations

import pytest
from ats.market.features import (
    V1_FEATURE_CODES,
    V1_FEATURE_REGISTRY,
    FeatureConfiguration,
    FeatureOutputSemantic,
)
from pydantic import ValidationError


def test_v1_registry_is_closed_ordered_and_complete() -> None:
    assert V1_FEATURE_CODES == (
        "simple_return",
        "log_return",
        "candle_body",
        "candle_range",
        "upper_wick",
        "lower_wick",
        "atr_3_sma",
        "realized_volatility_3_population",
        "roc_3_fraction",
        "rolling_volume_mean_3",
        "relative_volume_3",
        "rolling_price_position_3",
    )
    assert len(V1_FEATURE_CODES) == len(set(V1_FEATURE_CODES)) == 12


def test_every_definition_has_explicit_non_executable_semantics() -> None:
    for definition in V1_FEATURE_REGISTRY:
        assert definition.feature_version == "1.0.0"
        assert definition.lookback_bars >= 1
        assert definition.warmup_bars == definition.lookback_bars
        assert definition.output_semantic is FeatureOutputSemantic.FINITE_FLOAT
        assert definition.formula.strip()
        assert "eval(" not in definition.formula


def test_configuration_is_strict_frozen_and_closed() -> None:
    configuration = FeatureConfiguration()
    with pytest.raises(ValidationError):
        FeatureConfiguration(registry_version="2.0.0")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        FeatureConfiguration(registry_version="1.0.0", arbitrary=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        configuration.registry_version = "1.0.0"  # type: ignore[misc]
