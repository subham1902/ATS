"""Immutable inputs and fail-closed results for deterministic calibration."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import PositiveInt, field_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat, Probability, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr
from ats.contracts.intelligence.models import CalibratedOutcomeDistribution
from ats.contracts.intelligence.types import (
    NonNegativeFiniteFloat,
    PositiveFiniteFloat,
    RegisteredCode,
)


class CalibrationEvaluationStatus(StrEnum):
    CALIBRATED_DISTRIBUTION = "CALIBRATED_DISTRIBUTION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CalibrationObservation(ATSBaseModel):
    observation_id: UUID
    forecast_probability: Probability
    outcome_occurred: bool
    observed_at: UTCDateTime
    regime_evidence_id: UUID | None
    realized_return_fraction: FiniteFloat
    realized_volatility_fraction: NonNegativeFiniteFloat
    realized_mfe_fraction: FiniteFloat
    realized_mae_fraction: FiniteFloat


class CalibrationConfiguration(ATSBaseModel):
    calibrator_id: RegisteredCode
    calibrator_version: NonEmptyStr
    bin_count: PositiveInt
    minimum_support: PositiveInt
    interval_z: PositiveFiniteFloat
    validity_ms: PositiveInt
    tail_loss_return_threshold: FiniteFloat
    regime_conditioned: bool

    @field_validator("tail_loss_return_threshold")
    @classmethod
    def validate_tail_threshold(cls, value: float) -> float:
        if value >= 0.0:
            raise ValueError("tail loss return threshold must be negative")
        return value


class CalibrationEvaluationResult(ATSBaseModel):
    status: CalibrationEvaluationStatus
    distribution: CalibratedOutcomeDistribution | None
    support_count: int
    reason_codes: tuple[RegisteredCode, ...]


__all__ = [
    "CalibrationConfiguration",
    "CalibrationEvaluationResult",
    "CalibrationEvaluationStatus",
    "CalibrationObservation",
]
