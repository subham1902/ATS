from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from ats.contracts.domain import FeatureBundle
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.regime import RegimeDetectorConfiguration

BASE = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def configuration() -> RegimeDetectorConfiguration:
    return RegimeDetectorConfiguration(
        detector_id="R02_DETERMINISTIC_V1",
        detector_version="1.0.0",
        direction_threshold=0.002,
        trend_threshold=0.01,
        breakout_high=0.8,
        breakout_low=0.2,
        low_volatility_threshold=0.002,
        high_volatility_threshold=0.02,
        expansion_ratio=1.5,
        contraction_ratio=0.5,
        change_return_scale=0.02,
        change_volatility_scale=0.02,
        full_familiarity_bars=10,
    )


def bundle(
    index: int,
    *,
    roc: float = 0.0,
    volatility: float = 0.01,
    position: float = 0.5,
    quality_flags: tuple[str, ...] = (),
    features: dict[str, float] | None = None,
) -> FeatureBundle:
    resolved = features or {
        "roc_3_fraction": roc,
        "realized_volatility_3_population": volatility,
        "rolling_price_position_3": position,
    }
    return FeatureBundle(
        schema_version="1.0",
        feature_bundle_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
        snapshot_id=UUID(f"10000000-0000-0000-0000-{index:012d}"),
        feature_version="1.0.0",
        features=resolved,
        quality_flags=quality_flags,
        computed_at=BASE + timedelta(minutes=index),
        input_hash=f"{index:064x}",
    )


def context(
    current: FeatureBundle,
    *,
    quality: DataQualityState = DataQualityState.GOOD,
    liquidity: LiquidityState = LiquidityState.NORMAL,
) -> MarketContext:
    value = MarketContext(
        schema_version="1.0",
        market_context_id=UUID("20000000-0000-0000-0000-000000000001"),
        instrument_spec_id=UUID("20000000-0000-0000-0000-000000000002"),
        instrument_id="NIFTY",
        snapshot_id=current.snapshot_id,
        feature_bundle_id=current.feature_bundle_id,
        timeframe="5m",
        as_of_time=current.computed_at,
        data_cutoff=current.computed_at,
        session_state=SessionState.OPEN,
        data_quality_state=quality,
        freshness_ms=0,
        liquidity_state=liquidity,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="PAPER-V1",
        input_hash="a" * 64,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})
