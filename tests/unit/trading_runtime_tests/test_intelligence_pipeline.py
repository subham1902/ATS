from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.calibration import CalibrationObservation
from ats.trading_runtime.intelligence_pipeline import (
    IntelligencePipelineConfig,
    MarketIntelligencePipeline,
)


def _sample_snapshots() -> tuple[MarketSnapshot, ...]:
    base_time = datetime(2024, 6, 3, 5, 0, 0, tzinfo=UTC)
    snapshots = []
    prices = [
        (Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), Decimal("1000")),
        (Decimal("101"), Decimal("103"), Decimal("100"), Decimal("102"), Decimal("1200")),
        (Decimal("102"), Decimal("104"), Decimal("101"), Decimal("103"), Decimal("1500")),
        (Decimal("103"), Decimal("106"), Decimal("102"), Decimal("105"), Decimal("2000")),
        (Decimal("105"), Decimal("108"), Decimal("104"), Decimal("107"), Decimal("2500")),
    ]
    for i, (op, hi, lo, cl, vol) in enumerate(prices):
        t = base_time + timedelta(minutes=5 * i)
        s = MarketSnapshot(
            schema_version="1.0",
            snapshot_id=uuid4(),
            instrument_id="NIFTY",
            exchange="NSE",
            segment="CASH",
            timeframe="5m",
            sequence=i + 1,
            bar_timestamp=t,
            received_at=t,
            open=op,
            high=hi,
            low=lo,
            close=cl,
            volume=vol,
            quality_state=DataQualityState.GOOD,
            quality_flags=(),
            source="feed",
            source_version="1.0.0",
            session_state=SessionState.OPEN,
            payload_hash="0" * 64,
        )
        snapshots.append(s.model_copy(update={"payload_hash": compute_payload_hash(s)}))
    return tuple(snapshots)


def _calibration_observations(cutoff: datetime) -> tuple[CalibrationObservation, ...]:
    return tuple(
        CalibrationObservation(
            observation_id=uuid4(),
            forecast_probability=Decimal("0.74"),
            outcome_occurred=index < 15,
            observed_at=cutoff - timedelta(days=2, minutes=20 - index),
            available_to_strategy_time=cutoff - timedelta(days=2, minutes=20 - index),
            regime_evidence_id=None,
            realized_return_fraction=0.01 if index < 15 else -0.01,
            realized_volatility_fraction=0.015,
            realized_mfe_fraction=0.02,
            realized_mae_fraction=-0.01,
        )
        for index in range(20)
    )


def test_intelligence_pipeline_e2e() -> None:
    snapshots = _sample_snapshots()
    cutoff_snap = snapshots[-1]

    market_context = MarketContext(
        schema_version="1.0",
        market_context_id=uuid4(),
        instrument_spec_id=uuid4(),
        instrument_id="NIFTY",
        timeframe="5m",
        snapshot_id=cutoff_snap.snapshot_id,
        feature_bundle_id=uuid4(),
        as_of_time=cutoff_snap.received_at,
        data_cutoff=cutoff_snap.received_at,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.GOOD,
        freshness_ms=100,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="1.0.0",
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    market_context = market_context.model_copy(
        update={"payload_hash": compute_payload_hash(market_context)}
    )

    pipeline = MarketIntelligencePipeline(config=IntelligencePipelineConfig())

    t0 = time.perf_counter_ns()
    res = pipeline.evaluate(
        snapshots=snapshots,
        cutoff_sequence=5,
        market_context=market_context,
        campaign_id=uuid4(),
        strategy_id=uuid4(),
        evaluation_time=cutoff_snap.received_at,
        calibration_observations=_calibration_observations(cutoff_snap.received_at),
    )
    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000

    assert res.is_actionable
    assert res.direction == "BULLISH"
    assert res.candidate is not None
    assert res.thesis is not None
    assert res.regime is not None
    assert res.distribution is not None
    assert res.expected_edge_r > 0
    print(f"Pipeline single execution time: {elapsed_ms:.3f} ms")


def test_intelligence_pipeline_steady_state_latency() -> None:
    snapshots = _sample_snapshots()
    cutoff_snap = snapshots[-1]

    market_context = MarketContext(
        schema_version="1.0",
        market_context_id=uuid4(),
        instrument_spec_id=uuid4(),
        instrument_id="NIFTY",
        timeframe="5m",
        snapshot_id=cutoff_snap.snapshot_id,
        feature_bundle_id=uuid4(),
        as_of_time=cutoff_snap.received_at,
        data_cutoff=cutoff_snap.received_at,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.GOOD,
        freshness_ms=100,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="1.0.0",
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    market_context = market_context.model_copy(
        update={"payload_hash": compute_payload_hash(market_context)}
    )

    pipeline = MarketIntelligencePipeline(config=IntelligencePipelineConfig())

    # Warmup
    for _ in range(10):
        pipeline.evaluate(
            snapshots=snapshots,
            cutoff_sequence=5,
            market_context=market_context,
            campaign_id=uuid4(),
            strategy_id=uuid4(),
            evaluation_time=cutoff_snap.received_at,
            calibration_observations=_calibration_observations(cutoff_snap.received_at),
        )

    # 100 runs
    t0 = time.perf_counter_ns()
    N = 100
    for _ in range(N):
        res = pipeline.evaluate(
            snapshots=snapshots,
            cutoff_sequence=5,
            market_context=market_context,
            campaign_id=uuid4(),
            strategy_id=uuid4(),
            evaluation_time=cutoff_snap.received_at,
            calibration_observations=_calibration_observations(cutoff_snap.received_at),
        )
        assert res.is_actionable

    total_ms = (time.perf_counter_ns() - t0) / 1_000_000
    avg_ms = total_ms / N
    print(
        f"Pipeline 100-run steady state: Total {total_ms:.2f} ms | "
        f"Avg: {avg_ms:.3f} ms ({1000 / avg_ms:.0f} cycles/sec)"
    )
    assert avg_ms < 20.0  # Well within steady state threshold!


def test_pipeline_fails_closed_without_realized_calibration_evidence() -> None:
    snapshots = _sample_snapshots()
    cutoff = snapshots[-1]
    context = MarketContext(
        schema_version="1.0",
        market_context_id=uuid4(),
        instrument_spec_id=uuid4(),
        instrument_id="NIFTY",
        timeframe="5m",
        snapshot_id=cutoff.snapshot_id,
        feature_bundle_id=uuid4(),
        as_of_time=cutoff.received_at,
        data_cutoff=cutoff.received_at,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.GOOD,
        freshness_ms=100,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="1.0.0",
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    context = context.model_copy(update={"payload_hash": compute_payload_hash(context)})
    result = MarketIntelligencePipeline().evaluate(
        snapshots=snapshots,
        cutoff_sequence=5,
        market_context=context,
        campaign_id=uuid4(),
        strategy_id=uuid4(),
        evaluation_time=cutoff.received_at,
    )
    assert not result.is_actionable
    assert result.reason_codes == ("CALIBRATION_EVIDENCE_REQUIRED",)
