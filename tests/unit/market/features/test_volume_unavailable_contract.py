from __future__ import annotations

import pytest
from ats.contracts.domain import DataQualityState
from ats.contracts.domain.types import SessionState
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.regime.detector import detect_regime
from ats.intelligence.regime.models import RegimeDetectorConfiguration
from ats.market.features import FeatureInputError, compute_feature_bundle

from tests.unit.market.features.helpers import snapshot


def test_index_volume_unavailable_allows_price_features_and_omits_volume() -> None:
    """Index snapshots with VOLUME_UNAVAILABLE must compute all price features,
    omit volume features, and flag VOLUME_UNAVAILABLE.
    """
    bars = tuple(
        snapshot(
            seq,
            quality_state=DataQualityState.DEGRADED,
            quality_flags=("VOLUME_UNAVAILABLE",),
            open_="100",
            high="105",
            low="98",
            close="103",
            volume="0",
        )
        for seq in range(1, 5)
    )
    bundle = compute_feature_bundle(bars, cutoff_sequence=4)

    # 1. Price features MUST be present
    assert "simple_return" in bundle.features
    assert "log_return" in bundle.features
    assert "candle_body" in bundle.features
    assert "candle_range" in bundle.features
    assert "upper_wick" in bundle.features
    assert "lower_wick" in bundle.features
    assert "rolling_price_position_3" in bundle.features
    assert "atr_3_sma" in bundle.features
    assert "realized_volatility_3_population" in bundle.features
    assert "roc_3_fraction" in bundle.features

    # 2. Volume-dependent features MUST NOT be fabricated or present
    assert "rolling_volume_mean_3" not in bundle.features
    assert "relative_volume_3" not in bundle.features

    # 3. Provenance flag preserved
    assert bundle.quality_flags == ("VOLUME_UNAVAILABLE",)


def test_regime_detector_computes_with_volume_unavailable() -> None:
    """RegimeDetector computes price-based structure & volatility when volume is unavailable."""
    bars = tuple(
        snapshot(
            seq,
            quality_state=DataQualityState.DEGRADED,
            quality_flags=("VOLUME_UNAVAILABLE",),
            open_="100",
            high="105",
            low="98",
            close=str(100 + seq),
            volume="0",
        )
        for seq in range(1, 5)
    )
    bundle = compute_feature_bundle(bars, cutoff_sequence=4)

    ctx = MarketContext(
        schema_version="1.0",
        market_context_id=bundle.feature_bundle_id,
        instrument_spec_id=bundle.feature_bundle_id,
        instrument_id="NIFTY",
        timeframe="5m",
        snapshot_id=bundle.snapshot_id,
        feature_bundle_id=bundle.feature_bundle_id,
        as_of_time=bundle.computed_at,
        data_cutoff=bundle.computed_at,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.DEGRADED,
        freshness_ms=50,
        liquidity_state=LiquidityState.UNKNOWN,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="1.0.0",
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    regime = detect_regime(
        market_context=ctx,
        feature_history=(bundle,),
        configuration=RegimeDetectorConfiguration(
            detector_id="regime.v1",
            detector_version="1.0.0",
            direction_threshold=0.002,
            trend_threshold=0.005,
            breakout_high=0.8,
            breakout_low=0.2,
            low_volatility_threshold=0.005,
            high_volatility_threshold=0.02,
            expansion_ratio=1.2,
            contraction_ratio=0.8,
            change_return_scale=0.01,
            change_volatility_scale=0.01,
            full_familiarity_bars=20,
        ),
    )
    assert regime.structure.value != "UNKNOWN"
    assert regime.volatility.value != "UNKNOWN"


def test_fatal_quality_flags_still_fail_closed() -> None:
    """Non-volume fatal quality flags (e.g. CORRUPTED_DATA) must fail closed with
    FeatureInputError.
    """
    bars = tuple(
        snapshot(
            seq,
            quality_state=DataQualityState.DEGRADED,
            quality_flags=("CORRUPTED_DATA",),
            open_="100",
            high="105",
            low="98",
            close="103",
            volume="0",
        )
        for seq in range(1, 5)
    )
    with pytest.raises(FeatureInputError, match="fatal quality flags"):
        compute_feature_bundle(bars, cutoff_sequence=4)

