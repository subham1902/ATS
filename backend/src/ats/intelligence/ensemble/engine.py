"""Pure weighted raw-probability aggregation with explicit lineage binding."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from uuid import UUID, uuid5

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import ForecastStatus
from ats.contracts.intelligence.models import EnsembleForecast, MarketContext
from ats.contracts.intelligence.types import EnsembleMember, OutcomeProbability

from .errors import EnsembleInputError
from .models import EnsembleConfiguration, ForecastEventBinding, WeightedForecast

_ENSEMBLE_NAMESPACE = UUID("2b650804-ac71-5644-8116-247108f4e2fe")


def build_ensemble_forecast(
    *,
    market_context: MarketContext,
    event_binding: ForecastEventBinding,
    horizon_bars: int,
    weighted_forecasts: tuple[WeightedForecast, ...],
    configuration: EnsembleConfiguration,
) -> EnsembleForecast:
    """Aggregate raw provider evidence; calibrated fields are never consumed."""

    if type(horizon_bars) is not int or horizon_bars <= 0:
        raise EnsembleInputError("horizon_bars must be a positive integer")
    if event_binding.target_outcome_code == event_binding.complement_outcome_code:
        raise EnsembleInputError("binary outcome codes must be distinct")
    if not weighted_forecasts:
        raise EnsembleInputError("weighted_forecasts must be non-empty")
    if compute_payload_hash(market_context) != market_context.payload_hash:
        raise EnsembleInputError("market context payload hash mismatch")
    forecast_ids = tuple(item.forecast.forecast_id for item in weighted_forecasts)
    if len(forecast_ids) != len(set(forecast_ids)):
        raise EnsembleInputError("duplicate forecast IDs")
    for item in weighted_forecasts:
        _validate_lineage(
            item,
            market_context=market_context,
            event_binding=event_binding,
            horizon_bars=horizon_bars,
        )

    eligible = tuple(item for item in weighted_forecasts if _eligible(item))
    configured_decimals = {
        item.forecast.forecast_id: Decimal(str(item.configured_weight)) for item in eligible
    }
    weight_total = sum(configured_decimals.values(), Decimal(0))
    if weight_total <= 0:
        members = tuple(_member(item, 0.0) for item in weighted_forecasts)
        return _build(
            market_context=market_context,
            event_binding=event_binding,
            horizon_bars=horizon_bars,
            configuration=configuration,
            members=members,
            outcomes=(),
            disagreement=0.0,
            baseline_ids=(),
            status=ForecastStatus.FAILED,
        )

    normalized = {
        forecast_id: weight / weight_total for forecast_id, weight in configured_decimals.items()
    }
    members = tuple(
        _member(item, float(normalized.get(item.forecast.forecast_id, Decimal(0))))
        for item in weighted_forecasts
    )
    probability = _weighted_probability(eligible, normalized)
    outcomes = (
        OutcomeProbability(
            outcome_code=event_binding.target_outcome_code,
            probability=probability,
        ),
        OutcomeProbability(
            outcome_code=event_binding.complement_outcome_code,
            probability=Decimal(1) - probability,
        ),
    )
    disagreement = _disagreement(eligible, normalized, probability)
    degraded = len(eligible) != len(weighted_forecasts) or any(
        item.forecast.status is ForecastStatus.DEGRADED for item in eligible
    )
    baseline_ids = tuple(item.forecast.forecast_id for item in eligible if item.baseline)
    return _build(
        market_context=market_context,
        event_binding=event_binding,
        horizon_bars=horizon_bars,
        configuration=configuration,
        members=members,
        outcomes=outcomes,
        disagreement=disagreement,
        baseline_ids=baseline_ids,
        status=ForecastStatus.DEGRADED if degraded else ForecastStatus.READY,
    )


def _eligible(item: WeightedForecast) -> bool:
    return (
        item.configured_weight > 0
        and item.forecast.status in (ForecastStatus.READY, ForecastStatus.DEGRADED)
        and item.forecast.raw_probability is not None
    )


def _validate_lineage(
    item: WeightedForecast,
    *,
    market_context: MarketContext,
    event_binding: ForecastEventBinding,
    horizon_bars: int,
) -> None:
    forecast = item.forecast
    if compute_payload_hash(forecast) != forecast.payload_hash:
        raise EnsembleInputError("forecast payload hash mismatch")
    if forecast.feature_bundle_id != market_context.feature_bundle_id:
        raise EnsembleInputError("forecast feature bundle mismatch")
    if forecast.event_definition_id != event_binding.forecast_event_code:
        raise EnsembleInputError("forecast event definition mismatch")
    if forecast.horizon_bars != horizon_bars:
        raise EnsembleInputError("forecast horizon mismatch")
    if forecast.calibrated_probability is not None or forecast.calibrator_version is not None:
        raise EnsembleInputError("R05 accepts raw forecasts only; calibration belongs to R06")
    evidence = forecast.raw_evidence
    if evidence.get("instrument_id") != market_context.instrument_id:
        raise EnsembleInputError("forecast instrument mismatch")
    if evidence.get("timeframe") != market_context.timeframe:
        raise EnsembleInputError("forecast timeframe mismatch")
    if _timestamp(evidence.get("as_of_time"), "as_of_time") != market_context.as_of_time:
        raise EnsembleInputError("forecast as_of_time mismatch")
    if _timestamp(evidence.get("data_cutoff"), "data_cutoff") != market_context.data_cutoff:
        raise EnsembleInputError("forecast data_cutoff mismatch")


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise EnsembleInputError(f"forecast {field} evidence must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise EnsembleInputError(f"forecast {field} evidence is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EnsembleInputError(f"forecast {field} evidence must be timezone-aware")
    return parsed.astimezone(UTC)


def _weighted_probability(
    eligible: tuple[WeightedForecast, ...], normalized: dict[UUID, Decimal]
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        total = Decimal(0)
        for item in eligible:
            probability = item.forecast.raw_probability
            assert probability is not None
            total += probability * normalized[item.forecast.forecast_id]
        return +total


def _disagreement(
    eligible: tuple[WeightedForecast, ...],
    normalized: dict[UUID, Decimal],
    mean: Decimal,
) -> float:
    variance = 0.0
    mean_float = float(mean)
    for item in eligible:
        probability = item.forecast.raw_probability
        assert probability is not None
        difference = float(probability) - mean_float
        variance += float(normalized[item.forecast.forecast_id]) * difference * difference
    score = min(1.0, 2.0 * math.sqrt(max(0.0, variance)))
    return float(score)


def _member(item: WeightedForecast, weight: float) -> EnsembleMember:
    return EnsembleMember(
        forecast_id=item.forecast.forecast_id,
        model_id=item.forecast.model_id,
        model_version=item.forecast.model_version,
        weight=weight,
        status=item.forecast.status,
    )


def _build(
    *,
    market_context: MarketContext,
    event_binding: ForecastEventBinding,
    horizon_bars: int,
    configuration: EnsembleConfiguration,
    members: tuple[EnsembleMember, ...],
    outcomes: tuple[OutcomeProbability, ...],
    disagreement: float,
    baseline_ids: tuple[UUID, ...],
    status: ForecastStatus,
) -> EnsembleForecast:
    identity = ":".join(
        (
            str(market_context.market_context_id),
            str(event_binding.event_definition_id),
            str(horizon_bars),
            configuration.aggregation_version,
            *(f"{member.forecast_id}:{member.weight}" for member in members),
        )
    )
    ensemble = EnsembleForecast(
        schema_version="1.0",
        ensemble_forecast_id=uuid5(_ENSEMBLE_NAMESPACE, identity),
        market_context_id=market_context.market_context_id,
        instrument_id=market_context.instrument_id,
        timeframe=market_context.timeframe,
        event_definition_id=event_binding.event_definition_id,
        horizon_bars=horizon_bars,
        as_of_time=market_context.as_of_time,
        data_cutoff=market_context.data_cutoff,
        aggregation_method=configuration.aggregation_method,
        aggregation_version=configuration.aggregation_version,
        members=members,
        raw_outcomes=outcomes,
        disagreement_score=disagreement,
        effective_member_count=sum(member.weight > 0 for member in members),
        baseline_member_ids=baseline_ids,
        status=status,
        payload_hash="0" * 64,
    )
    return ensemble.model_copy(update={"payload_hash": compute_payload_hash(ensemble)})


__all__ = ["build_ensemble_forecast"]
