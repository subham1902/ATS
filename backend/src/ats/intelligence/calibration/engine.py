"""Deterministic empirical calibration without future-data access."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext
from statistics import fmean
from uuid import UUID, uuid5

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, ForecastStatus, ProbabilityInterval
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    EnsembleForecast,
    MarketContext,
    RegimeEvidence,
)
from ats.contracts.intelligence.types import CalibratedOutcome

from .errors import CalibrationInputError
from .models import (
    CalibrationConfiguration,
    CalibrationEvaluationResult,
    CalibrationEvaluationStatus,
    CalibrationObservation,
)

_DISTRIBUTION_NAMESPACE = UUID("7bda3f5c-f3e4-5fa2-9fe6-e2a75d508ddb")


def calibrate_outcome_distribution(
    *,
    ensemble: EnsembleForecast,
    market_context: MarketContext,
    target_outcome_code: str,
    observations: tuple[CalibrationObservation, ...],
    configuration: CalibrationConfiguration,
    regime_evidence: RegimeEvidence | None,
) -> CalibrationEvaluationResult:
    """Calibrate one binary ensemble outcome or return insufficient evidence."""

    _validate_inputs(
        ensemble=ensemble,
        market_context=market_context,
        target_outcome_code=target_outcome_code,
        observations=observations,
        configuration=configuration,
        regime_evidence=regime_evidence,
    )
    target = next(
        item for item in ensemble.raw_outcomes if item.outcome_code == target_outcome_code
    )
    complement = next(
        item for item in ensemble.raw_outcomes if item.outcome_code != target_outcome_code
    )
    eligible = tuple(
        sorted(
            (
                item
                for item in observations
                if not configuration.regime_conditioned
                or item.regime_evidence_id == regime_evidence.regime_evidence_id  # type: ignore[union-attr]
            ),
            key=lambda item: (item.observed_at, item.observation_id),
        )
    )
    selected = tuple(
        item
        for item in eligible
        if _bin_index(item.forecast_probability, configuration.bin_count)
        == _bin_index(target.probability, configuration.bin_count)
    )
    if len(selected) < configuration.minimum_support:
        return CalibrationEvaluationResult(
            status=CalibrationEvaluationStatus.INSUFFICIENT_EVIDENCE,
            distribution=None,
            support_count=len(selected),
            reason_codes=("INSUFFICIENT_CALIBRATION_SUPPORT",),
        )

    calibrated_probability = _empirical_probability(selected)
    interval = _wilson_interval(
        calibrated_probability,
        len(selected),
        configuration.interval_z,
    )
    complement_probability = Decimal(1) - calibrated_probability
    outcomes = (
        CalibratedOutcome(
            outcome_code=target.outcome_code,
            probability=calibrated_probability,
            interval=interval,
        ),
        CalibratedOutcome(
            outcome_code=complement.outcome_code,
            probability=complement_probability,
            interval=ProbabilityInterval(
                low=Decimal(1) - interval.high,
                high=Decimal(1) - interval.low,
            ),
        ),
    )
    quality = (
        DataQualityState.GOOD
        if ensemble.status is ForecastStatus.READY
        and market_context.data_quality_state is DataQualityState.GOOD
        else DataQualityState.DEGRADED
    )
    identity = ":".join(
        (
            str(ensemble.ensemble_forecast_id),
            configuration.calibrator_id,
            configuration.calibrator_version,
            str(regime_evidence.regime_evidence_id) if regime_evidence else "UNCONDITIONED",
            *(str(item.observation_id) for item in selected),
        )
    )
    value = CalibratedOutcomeDistribution(
        schema_version="1.0",
        distribution_id=uuid5(_DISTRIBUTION_NAMESPACE, identity),
        ensemble_forecast_id=ensemble.ensemble_forecast_id,
        market_context_id=market_context.market_context_id,
        instrument_id=ensemble.instrument_id,
        event_definition_id=ensemble.event_definition_id,
        horizon_bars=ensemble.horizon_bars,
        as_of_time=ensemble.as_of_time,
        data_cutoff=ensemble.data_cutoff,
        calibrator_id=configuration.calibrator_id,
        calibrator_version=configuration.calibrator_version,
        calibration_window_start=eligible[0].observed_at,
        calibration_window_end=eligible[-1].observed_at,
        support_count=len(selected),
        outcomes=outcomes,
        brier_score=_brier_score(eligible),
        expected_calibration_error=_expected_calibration_error(
            eligible, configuration.bin_count
        ),
        regime_conditioned=configuration.regime_conditioned,
        regime_evidence_id=regime_evidence.regime_evidence_id if regime_evidence else None,
        expected_return_fraction=fmean(item.realized_return_fraction for item in selected),
        expected_volatility_fraction=fmean(
            item.realized_volatility_fraction for item in selected
        ),
        expected_mfe_fraction=fmean(item.realized_mfe_fraction for item in selected),
        expected_mae_fraction=fmean(item.realized_mae_fraction for item in selected),
        tail_loss_probability=Decimal(
            sum(
                item.realized_return_fraction
                <= configuration.tail_loss_return_threshold
                for item in selected
            )
        )
        / Decimal(len(selected)),
        quality_state=quality,
        valid_until=ensemble.as_of_time + timedelta(milliseconds=configuration.validity_ms),
        payload_hash="0" * 64,
    )
    distribution = value.model_copy(update={"payload_hash": compute_payload_hash(value)})
    return CalibrationEvaluationResult(
        status=CalibrationEvaluationStatus.CALIBRATED_DISTRIBUTION,
        distribution=distribution,
        support_count=len(selected),
        reason_codes=("CALIBRATION_SUPPORT_ACCEPTED",),
    )


def _validate_inputs(
    *,
    ensemble: EnsembleForecast,
    market_context: MarketContext,
    target_outcome_code: str,
    observations: tuple[CalibrationObservation, ...],
    configuration: CalibrationConfiguration,
    regime_evidence: RegimeEvidence | None,
) -> None:
    if compute_payload_hash(ensemble) != ensemble.payload_hash:
        raise CalibrationInputError("ensemble payload hash mismatch")
    if compute_payload_hash(market_context) != market_context.payload_hash:
        raise CalibrationInputError("market context payload hash mismatch")
    if ensemble.status not in (ForecastStatus.READY, ForecastStatus.DEGRADED):
        raise CalibrationInputError("ensemble is not calibratable")
    if market_context.data_quality_state not in (
        DataQualityState.GOOD,
        DataQualityState.DEGRADED,
    ):
        raise CalibrationInputError("market context quality is not calibratable")
    if (
        ensemble.market_context_id != market_context.market_context_id
        or ensemble.instrument_id != market_context.instrument_id
        or ensemble.timeframe != market_context.timeframe
        or ensemble.as_of_time != market_context.as_of_time
        or ensemble.data_cutoff != market_context.data_cutoff
    ):
        raise CalibrationInputError("ensemble and market context lineage mismatch")
    if len(ensemble.raw_outcomes) != 2:
        raise CalibrationInputError("R06 v1 requires a binary outcome distribution")
    if sum(item.outcome_code == target_outcome_code for item in ensemble.raw_outcomes) != 1:
        raise CalibrationInputError("target outcome must exist exactly once")
    observation_ids = tuple(item.observation_id for item in observations)
    if len(observation_ids) != len(set(observation_ids)):
        raise CalibrationInputError("duplicate calibration observation")
    if any(item.observed_at > ensemble.data_cutoff for item in observations):
        raise CalibrationInputError("future calibration observation")
    if configuration.regime_conditioned:
        if regime_evidence is None:
            raise CalibrationInputError("regime-conditioned calibration requires regime evidence")
        if compute_payload_hash(regime_evidence) != regime_evidence.payload_hash:
            raise CalibrationInputError("regime evidence payload hash mismatch")
        if (
            regime_evidence.market_context_id != market_context.market_context_id
            or regime_evidence.instrument_id != market_context.instrument_id
            or regime_evidence.timeframe != market_context.timeframe
            or regime_evidence.as_of_time != market_context.as_of_time
            or regime_evidence.data_cutoff != market_context.data_cutoff
        ):
            raise CalibrationInputError("regime evidence lineage mismatch")
    elif regime_evidence is not None:
        raise CalibrationInputError("unconditioned calibration must not receive regime evidence")


def _bin_index(probability: Decimal, bin_count: int) -> int:
    return min(bin_count - 1, int(probability * bin_count))


def _empirical_probability(observations: tuple[CalibrationObservation, ...]) -> Decimal:
    return Decimal(sum(item.outcome_occurred for item in observations)) / Decimal(len(observations))


def _wilson_interval(probability: Decimal, count: int, z_value: float) -> ProbabilityInterval:
    with localcontext() as context:
        context.prec = 50
        n = Decimal(count)
        z = Decimal(str(z_value))
        z_squared = z * z
        denominator = Decimal(1) + z_squared / n
        center = (probability + z_squared / (Decimal(2) * n)) / denominator
        radicand = probability * (Decimal(1) - probability) / n + z_squared / (
            Decimal(4) * n * n
        )
        margin = z * context.sqrt(radicand) / denominator
        return ProbabilityInterval(
            low=max(Decimal(0), center - margin),
            high=min(Decimal(1), center + margin),
        )


def _brier_score(observations: tuple[CalibrationObservation, ...]) -> float:
    total = sum(
        (float(item.forecast_probability) - float(item.outcome_occurred)) ** 2
        for item in observations
    )
    return float(total / len(observations))


def _expected_calibration_error(
    observations: tuple[CalibrationObservation, ...], bin_count: int
) -> float:
    total = 0.0
    for index in range(bin_count):
        group = tuple(
            item
            for item in observations
            if _bin_index(item.forecast_probability, bin_count) == index
        )
        if group:
            empirical = fmean(float(item.outcome_occurred) for item in group)
            predicted = fmean(float(item.forecast_probability) for item in group)
            total += len(group) / len(observations) * abs(empirical - predicted)
    return float(min(1.0, total))


__all__ = ["calibrate_outcome_distribution"]
