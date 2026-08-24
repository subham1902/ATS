from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.domain import ForecastBundle
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import (
    DataQualityState,
    ForecastStatus,
    SessionState,
    UncertaintyEvidence,
)
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.ensemble import (
    EnsembleConfiguration,
    ForecastEventBinding,
    WeightedForecast,
)

AS_OF = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
CUTOFF = AS_OF - timedelta(minutes=1)
FEATURE_ID = UUID("00000000-0000-0000-0000-000000000801")


def context() -> MarketContext:
    value = MarketContext(
        schema_version="1.0",
        market_context_id=UUID("00000000-0000-0000-0000-000000000802"),
        instrument_spec_id=UUID("00000000-0000-0000-0000-000000000803"),
        instrument_id="NIFTY",
        snapshot_id=UUID("00000000-0000-0000-0000-000000000804"),
        feature_bundle_id=FEATURE_ID,
        timeframe="5m",
        as_of_time=AS_OF,
        data_cutoff=CUTOFF,
        session_state=SessionState.OPEN,
        data_quality_state=DataQualityState.GOOD,
        freshness_ms=0,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="PAPER-V1",
        input_hash="a" * 64,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def binding() -> ForecastEventBinding:
    return ForecastEventBinding(
        event_definition_id=UUID("00000000-0000-0000-0000-000000000805"),
        forecast_event_code="close-above-last-v1",
        target_outcome_code="ABOVE",
        complement_outcome_code="NOT_ABOVE",
    )


def configuration() -> EnsembleConfiguration:
    return EnsembleConfiguration(
        aggregation_method="WEIGHTED_MEAN_RAW",
        aggregation_version="1.0.0",
    )


def forecast(
    index: int,
    probability: Decimal | None,
    *,
    status: ForecastStatus = ForecastStatus.READY,
) -> ForecastBundle:
    value = ForecastBundle(
        schema_version="1.0",
        forecast_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
        feature_bundle_id=FEATURE_ID,
        model_id=f"MODEL-{index}",
        model_version=f"V{index}",
        checkpoint_hash=f"{index:064x}",
        data_version="DATA-V1",
        horizon_bars=2,
        event_definition_id="close-above-last-v1",
        raw_evidence={
            "instrument_id": "NIFTY",
            "timeframe": "5m",
            "as_of_time": AS_OF.isoformat(),
            "data_cutoff": CUTOFF.isoformat(),
        },
        forecast_paths=None,
        raw_probability=probability,
        calibrated_probability=None,
        calibrator_version=None,
        uncertainty=UncertaintyEvidence(method="FIXTURE", score=0.1),
        baseline_results=(),
        seed=index,
        status=status,
        started_at=AS_OF,
        completed_at=AS_OF,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def weighted(
    index: int,
    probability: str | None,
    weight: float,
    *,
    status: ForecastStatus = ForecastStatus.READY,
    baseline: bool = False,
) -> WeightedForecast:
    return WeightedForecast(
        forecast=forecast(
            index, None if probability is None else Decimal(probability), status=status
        ),
        configured_weight=weight,
        baseline=baseline,
    )
