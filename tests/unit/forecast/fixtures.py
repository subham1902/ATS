from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ats.contracts.ids import fixture_id
from ats.forecast import (
    ForecastEventDefinition,
    ForecastObservation,
    ModelMetadata,
    ModelRunRequest,
    ProviderConfiguration,
    build_model_run_request,
)

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
HASH = "a" * 64


def observation(step: int, *, instrument: str = "ABC") -> ForecastObservation:
    price = Decimal(100 + step)
    return ForecastObservation(
        instrument_id=instrument,
        timeframe="5m",
        observation_time=T0 + timedelta(minutes=5 * step),
        open=price,
        high=price + Decimal("1"),
        low=price - Decimal("1"),
        close=price + Decimal("0.5"),
        volume=Decimal("1000"),
        amount=Decimal("100500"),
    )


def naive_metadata() -> ModelMetadata:
    return ModelMetadata(
        provider_name="naive",
        model_id="naive-last-close",
        model_version="1.0.0",
        checkpoint_hash=HASH,
        method="last-close-persistence",
        seed=7,
        source_revision="ats-iba-r04",
    )


def configuration(metadata: ModelMetadata | None = None) -> ProviderConfiguration:
    value = metadata or naive_metadata()
    return ProviderConfiguration(
        model_id=value.model_id,
        model_version=value.model_version,
        checkpoint_hash=value.checkpoint_hash,
        data_version="fixture-v1",
        method=value.method,
        seed=value.seed,
        timeout_ms=100,
        minimum_context=2,
        supported_horizons=(2, 3),
        device="cpu",
        precision="float64",
        options={"purpose": "baseline"},
    )


def request(
    *,
    observations: tuple[ForecastObservation, ...] | None = None,
    metadata: ModelMetadata | None = None,
) -> ModelRunRequest:
    history = observations or tuple(observation(step) for step in range(4))
    cutoff = history[-1].observation_time
    return build_model_run_request(
        forecast_id=fixture_id("r04:forecast"),
        feature_bundle_id=fixture_id("r04:features"),
        instrument_id="ABC",
        timeframe="5m",
        observations=history,
        as_of_time=cutoff + timedelta(minutes=1),
        data_cutoff=cutoff,
        event_definition=ForecastEventDefinition(
            event_definition_id="close-above-last-v1",
            kind="CLOSE_ABOVE_LAST",
        ),
        horizon_bars=2,
        configuration=configuration(metadata),
        started_at=cutoff + timedelta(minutes=1),
        completed_at=cutoff + timedelta(minutes=1, milliseconds=5),
    )


__all__ = [
    "HASH",
    "T0",
    "configuration",
    "naive_metadata",
    "observation",
    "request",
]
