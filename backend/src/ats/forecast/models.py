"""Bounded, immutable inputs and provider outputs for forecast workers."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import (
    InstrumentId,
    JsonValue,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    Sha256,
)
from ats.contracts.ids import OpaqueId


class ForecastObservation(ATSBaseModel):
    instrument_id: InstrumentId
    timeframe: Literal["5m"]
    observation_time: UTCDateTime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    amount: NonNegativeDecimal | None = None

    @model_validator(mode="after")
    def validate_prices(self) -> ForecastObservation:
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low/high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low/high")
        return self


class ForecastEventDefinition(ATSBaseModel):
    event_definition_id: NonEmptyStr
    kind: Literal["CLOSE_ABOVE_LAST"]


class ProviderConfiguration(ATSBaseModel):
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    checkpoint_hash: Sha256
    data_version: NonEmptyStr
    method: NonEmptyStr
    seed: int
    timeout_ms: PositiveInt
    minimum_context: PositiveInt
    supported_horizons: tuple[PositiveInt, ...]
    device: NonEmptyStr = "cpu"
    precision: NonEmptyStr = "float32"
    options: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_horizons(self) -> ProviderConfiguration:
        if not self.supported_horizons:
            raise ValueError("supported_horizons must be non-empty")
        if len(set(self.supported_horizons)) != len(self.supported_horizons):
            raise ValueError("supported_horizons must be unique")
        return self


class ModelRunRequest(ATSBaseModel):
    forecast_id: OpaqueId
    feature_bundle_id: OpaqueId
    instrument_id: InstrumentId
    timeframe: Literal["5m"]
    observations: tuple[ForecastObservation, ...]
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    event_definition: ForecastEventDefinition
    horizon_bars: PositiveInt
    configuration: ProviderConfiguration
    started_at: UTCDateTime
    completed_at: UTCDateTime

    @model_validator(mode="after")
    def validate_lineage(self) -> ModelRunRequest:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be >= started_at")
        if self.horizon_bars not in self.configuration.supported_horizons:
            raise ValueError("horizon is not supported by provider configuration")
        if not self.observations:
            raise ValueError("observations must be non-empty")
        timestamps = tuple(item.observation_time for item in self.observations)
        if timestamps != tuple(sorted(timestamps)) or len(timestamps) != len(set(timestamps)):
            raise ValueError("observations must be strictly time ordered")
        for observation in self.observations:
            if observation.observation_time > self.data_cutoff:
                raise ValueError("observation exceeds data_cutoff")
            if observation.instrument_id != self.instrument_id:
                raise ValueError("observation instrument mismatch")
            if observation.timeframe != self.timeframe:
                raise ValueError("observation timeframe mismatch")
        return self


class ModelMetadata(ATSBaseModel):
    provider_name: NonEmptyStr
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    checkpoint_hash: Sha256
    method: NonEmptyStr
    seed: int
    source_revision: NonEmptyStr


class ResourceEvidence(ATSBaseModel):
    device: NonEmptyStr
    precision: NonEmptyStr
    runtime_ms: NonNegativeInt
    model_loaded: bool
    status: Literal["READY", "UNAVAILABLE", "DEGRADED"]


class ProviderForecast(ATSBaseModel):
    instrument_id: InstrumentId
    timeframe: Literal["5m"]
    data_cutoff: UTCDateTime
    event_definition_id: NonEmptyStr
    horizon_bars: PositiveInt
    metadata: ModelMetadata
    forecast_paths: tuple[tuple[FiniteFloat, ...], ...]
    raw_probability: Decimal
    uncertainty_method: NonEmptyStr
    uncertainty_score: FiniteFloat
    resource: ResourceEvidence


def build_model_run_request(
    *,
    forecast_id: OpaqueId,
    feature_bundle_id: OpaqueId,
    instrument_id: InstrumentId,
    timeframe: Literal["5m"],
    observations: tuple[ForecastObservation, ...],
    as_of_time: UTCDateTime,
    data_cutoff: UTCDateTime,
    event_definition: ForecastEventDefinition,
    horizon_bars: PositiveInt,
    configuration: ProviderConfiguration,
    started_at: UTCDateTime,
    completed_at: UTCDateTime,
) -> ModelRunRequest:
    """Freeze only observations visible at the caller-supplied cutoff."""

    visible = tuple(item for item in observations if item.observation_time <= data_cutoff)
    return ModelRunRequest(
        forecast_id=forecast_id,
        feature_bundle_id=feature_bundle_id,
        instrument_id=instrument_id,
        timeframe=timeframe,
        observations=visible,
        as_of_time=as_of_time,
        data_cutoff=data_cutoff,
        event_definition=event_definition,
        horizon_bars=horizon_bars,
        configuration=configuration,
        started_at=started_at,
        completed_at=completed_at,
    )


def next_observation_times(request: ModelRunRequest) -> tuple[UTCDateTime, ...]:
    """Return deterministic future 5-minute timestamps for provider adapters."""

    return tuple(
        request.data_cutoff + timedelta(minutes=5 * step)
        for step in range(1, request.horizon_bars + 1)
    )


__all__ = [
    "ForecastEventDefinition",
    "ForecastObservation",
    "ModelMetadata",
    "ModelRunRequest",
    "ProviderConfiguration",
    "ProviderForecast",
    "ResourceEvidence",
    "build_model_run_request",
    "next_observation_times",
]
