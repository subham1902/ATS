"""Immutable R05 aggregation inputs."""

from __future__ import annotations

from uuid import UUID

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain import ForecastBundle
from ats.contracts.domain.types import NonEmptyStr, UnitIntervalFloat
from ats.contracts.intelligence.types import RegisteredCode


class ForecastEventBinding(ATSBaseModel):
    event_definition_id: UUID
    forecast_event_code: NonEmptyStr
    target_outcome_code: RegisteredCode
    complement_outcome_code: RegisteredCode


class WeightedForecast(ATSBaseModel):
    forecast: ForecastBundle
    configured_weight: UnitIntervalFloat
    baseline: bool


class EnsembleConfiguration(ATSBaseModel):
    aggregation_method: RegisteredCode
    aggregation_version: NonEmptyStr


__all__ = ["EnsembleConfiguration", "ForecastEventBinding", "WeightedForecast"]
