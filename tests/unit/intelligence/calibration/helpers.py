from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.models import EnsembleForecast, RegimeEvidence
from ats.contracts.intelligence.types import (
    LiquidityState,
    RegimeDirection,
    RegimeStructure,
    VolatilityState,
)
from ats.intelligence.calibration import CalibrationConfiguration, CalibrationObservation
from ats.intelligence.ensemble import build_ensemble_forecast

from tests.unit.intelligence.ensemble.helpers import binding, context, weighted
from tests.unit.intelligence.ensemble.helpers import configuration as ensemble_config


def ensemble() -> EnsembleForecast:
    return build_ensemble_forecast(
        market_context=context(),
        event_binding=binding(),
        horizon_bars=2,
        weighted_forecasts=(weighted(1, "0.7", 1.0),),
        configuration=ensemble_config(),
    )


def calibration_config(
    *, minimum_support: int = 3, regime_conditioned: bool = False
) -> CalibrationConfiguration:
    return CalibrationConfiguration(
        calibrator_id="EMPIRICAL_BINNED_V1",
        calibrator_version="1.0.0",
        bin_count=10,
        minimum_support=minimum_support,
        interval_z=1.96,
        validity_ms=300_000,
        tail_loss_return_threshold=-0.01,
        regime_conditioned=regime_conditioned,
    )


def observation(
    index: int,
    occurred: bool,
    *,
    probability: str = "0.72",
    minutes_before: int | None = None,
    regime_id: UUID | None = None,
) -> CalibrationObservation:
    current = context()
    observed_at = current.data_cutoff - timedelta(
        minutes=minutes_before if minutes_before is not None else 10 - index
    )
    return CalibrationObservation(
        observation_id=UUID(f"30000000-0000-0000-0000-{index:012d}"),
        forecast_probability=Decimal(probability),
        outcome_occurred=occurred,
        observed_at=observed_at,
        available_to_strategy_time=observed_at,
        regime_evidence_id=regime_id,
        realized_return_fraction=0.01 if occurred else -0.02,
        realized_volatility_fraction=0.015,
        realized_mfe_fraction=0.02,
        realized_mae_fraction=-0.01,
    )


def observations(*, regime_id: UUID | None = None) -> tuple[CalibrationObservation, ...]:
    return (
        observation(1, True, regime_id=regime_id),
        observation(2, True, regime_id=regime_id),
        observation(3, False, regime_id=regime_id),
    )


def regime() -> RegimeEvidence:
    current = context()
    value = RegimeEvidence(
        schema_version="1.0",
        regime_evidence_id=UUID("40000000-0000-0000-0000-000000000001"),
        market_context_id=current.market_context_id,
        instrument_id=current.instrument_id,
        timeframe=current.timeframe,
        as_of_time=current.as_of_time,
        data_cutoff=current.data_cutoff,
        detector_id="R02",
        detector_version="1.0.0",
        direction=RegimeDirection.UP,
        structure=RegimeStructure.TREND,
        volatility=VolatilityState.NORMAL,
        liquidity=LiquidityState.NORMAL,
        change_score=0.2,
        regime_familiarity=0.8,
        support_window_bars=10,
        reason_codes=("UPWARD_MOMENTUM",),
        quality_state=DataQualityState.GOOD,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})
