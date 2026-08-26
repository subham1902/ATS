"""Time-ordered calibration validation and drift health."""

from __future__ import annotations

import math
from enum import StrEnum
from statistics import fmean

from pydantic import PositiveInt

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.intelligence.types import NonNegativeFiniteFloat, PositiveFiniteFloat

from .models import CalibrationObservation


class CalibrationHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"


class ReliabilityBucket(ATSBaseModel):
    lower: NonNegativeFiniteFloat
    upper: PositiveFiniteFloat
    count: PositiveInt
    mean_forecast: NonNegativeFiniteFloat
    observed_frequency: NonNegativeFiniteFloat


class CalibrationValidationReport(ATSBaseModel):
    health: CalibrationHealth
    train_count: int
    validation_count: int
    oos_count: int
    train_window: tuple[UTCDateTime, UTCDateTime] | None
    validation_window: tuple[UTCDateTime, UTCDateTime] | None
    oos_window: tuple[UTCDateTime, UTCDateTime] | None
    brier_score: NonNegativeFiniteFloat | None
    log_loss: NonNegativeFiniteFloat | None
    expected_calibration_error: NonNegativeFiniteFloat | None
    reliability: tuple[ReliabilityBucket, ...]
    reason_codes: tuple[str, ...]


class CalibrationValidationPolicy(ATSBaseModel):
    minimum_total_samples: PositiveInt = 60
    minimum_oos_samples: PositiveInt = 12
    bin_count: PositiveInt = 10
    maximum_brier_score: PositiveFiniteFloat = 0.30
    maximum_log_loss: PositiveFiniteFloat = 0.80
    maximum_calibration_error: PositiveFiniteFloat = 0.15


def validate_calibration_history(
    observations: tuple[CalibrationObservation, ...],
    *,
    decision_time: UTCDateTime,
    policy: CalibrationValidationPolicy | None = None,
) -> CalibrationValidationReport:
    """Evaluate strictly ordered 60/20/20 windows using only available labels."""

    policy = policy or CalibrationValidationPolicy()
    eligible = tuple(
        sorted(
            (item for item in observations if item.available_to_strategy_time <= decision_time),
            key=lambda item: (item.available_to_strategy_time, item.observation_id),
        )
    )
    if len(eligible) < policy.minimum_total_samples:
        return _empty_report(len(eligible), "INSUFFICIENT_TIME_ORDERED_SUPPORT")
    train_end = max(1, int(len(eligible) * 0.60))
    validation_end = max(train_end + 1, int(len(eligible) * 0.80))
    train = eligible[:train_end]
    validation = eligible[train_end:validation_end]
    oos = eligible[validation_end:]
    if len(oos) < policy.minimum_oos_samples:
        return _empty_report(len(eligible), "INSUFFICIENT_OOS_SUPPORT")
    brier = fmean(
        (float(item.forecast_probability) - float(item.outcome_occurred)) ** 2 for item in oos
    )
    epsilon = 1e-12
    log_loss = -fmean(
        float(item.outcome_occurred) * math.log(max(epsilon, float(item.forecast_probability)))
        + (1.0 - float(item.outcome_occurred))
        * math.log(max(epsilon, 1.0 - float(item.forecast_probability)))
        for item in oos
    )
    reliability = _reliability(oos, policy.bin_count)
    ece = sum(
        bucket.count / len(oos) * abs(bucket.mean_forecast - bucket.observed_frequency)
        for bucket in reliability
    )
    reasons: list[str] = []
    if brier > policy.maximum_brier_score:
        reasons.append("BRIER_DRIFT")
    if log_loss > policy.maximum_log_loss:
        reasons.append("LOG_LOSS_DRIFT")
    if ece > policy.maximum_calibration_error:
        reasons.append("RELIABILITY_DRIFT")
    health = CalibrationHealth.HEALTHY if not reasons else CalibrationHealth.DEGRADED
    return CalibrationValidationReport(
        health=health,
        train_count=len(train),
        validation_count=len(validation),
        oos_count=len(oos),
        train_window=(train[0].available_to_strategy_time, train[-1].available_to_strategy_time),
        validation_window=(
            validation[0].available_to_strategy_time,
            validation[-1].available_to_strategy_time,
        ),
        oos_window=(oos[0].available_to_strategy_time, oos[-1].available_to_strategy_time),
        brier_score=brier,
        log_loss=log_loss,
        expected_calibration_error=ece,
        reliability=reliability,
        reason_codes=tuple(reasons or ["CALIBRATION_HEALTHY"]),
    )


def _reliability(
    observations: tuple[CalibrationObservation, ...], bin_count: int
) -> tuple[ReliabilityBucket, ...]:
    result: list[ReliabilityBucket] = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        group = tuple(
            item
            for item in observations
            if min(bin_count - 1, int(float(item.forecast_probability) * bin_count)) == index
        )
        if group:
            result.append(
                ReliabilityBucket(
                    lower=lower,
                    upper=upper,
                    count=len(group),
                    mean_forecast=fmean(float(item.forecast_probability) for item in group),
                    observed_frequency=fmean(float(item.outcome_occurred) for item in group),
                )
            )
    return tuple(result)


def _empty_report(count: int, reason: str) -> CalibrationValidationReport:
    return CalibrationValidationReport(
        health=CalibrationHealth.INVALID,
        train_count=count,
        validation_count=0,
        oos_count=0,
        train_window=None,
        validation_window=None,
        oos_window=None,
        brier_score=None,
        log_loss=None,
        expected_calibration_error=None,
        reliability=(),
        reason_codes=(reason,),
    )


__all__ = [
    "CalibrationHealth",
    "CalibrationValidationPolicy",
    "CalibrationValidationReport",
    "ReliabilityBucket",
    "validate_calibration_history",
]
