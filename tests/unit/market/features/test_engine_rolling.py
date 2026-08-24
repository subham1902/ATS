from __future__ import annotations

import math

import pytest
from ats.market.features import V1_FEATURE_CODES, compute_feature_bundle

from .helpers import four_bars, snapshot


def test_three_bars_enable_volume_and_price_position_only() -> None:
    bundle = compute_feature_bundle(four_bars(), cutoff_sequence=3)
    assert "atr_3_sma" not in bundle.features
    assert "realized_volatility_3_population" not in bundle.features
    assert "roc_3_fraction" not in bundle.features
    assert bundle.features["rolling_volume_mean_3"] == 1000.0
    assert bundle.features["relative_volume_3"] == 0.8
    assert bundle.features["rolling_price_position_3"] == 0.5
    assert bundle.quality_flags == ("INSUFFICIENT_WARMUP",)


def test_four_bars_enable_every_v1_feature_in_registry_order() -> None:
    bundle = compute_feature_bundle(four_bars(), cutoff_sequence=4)
    assert tuple(bundle.features) == V1_FEATURE_CODES
    assert bundle.quality_flags == ()
    assert bundle.features["atr_3_sma"] == pytest.approx(14.0 / 3.0)
    assert bundle.features["roc_3_fraction"] == pytest.approx(5.0 / 101.0)
    assert bundle.features["rolling_volume_mean_3"] == 1200.0
    assert bundle.features["relative_volume_3"] == pytest.approx(4.0 / 3.0)
    assert bundle.features["rolling_price_position_3"] == pytest.approx(6.0 / 7.0)
    assert bundle.features["realized_volatility_3_population"] == pytest.approx(
        0.020114598737835915
    )


def test_constant_price_and_zero_volume_have_explicit_finite_results() -> None:
    bars = tuple(
        snapshot(
            sequence,
            open_="100",
            high="100",
            low="100",
            close="100",
            volume="0",
        )
        for sequence in range(1, 5)
    )
    bundle = compute_feature_bundle(bars, cutoff_sequence=4)
    assert bundle.features["simple_return"] == 0.0
    assert bundle.features["log_return"] == 0.0
    assert bundle.features["atr_3_sma"] == 0.0
    assert bundle.features["realized_volatility_3_population"] == 0.0
    assert bundle.features["roc_3_fraction"] == 0.0
    assert bundle.features["rolling_volume_mean_3"] == 0.0
    assert bundle.features["relative_volume_3"] == 0.0
    assert bundle.features["rolling_price_position_3"] == 0.5
    assert all(math.isfinite(value) for value in bundle.features.values())
