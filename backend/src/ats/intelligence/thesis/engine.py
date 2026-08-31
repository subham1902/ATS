"""Pure R07 market-thesis synthesis over frozen evidence contracts."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, ForecastStatus
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    EnsembleForecast,
    MarketContext,
    MarketThesis,
    RegimeEvidence,
)
from ats.contracts.intelligence.types import (
    MarketThesisStatus,
    PriceLevelKind,
    RegimeDirection,
    ThesisStance,
)

from .errors import ThesisSynthesisError
from .models import (
    ThesisSynthesisConfiguration,
    ThesisSynthesisFacts,
    ThesisSynthesisResult,
    ThesisSynthesisStatus,
)

_THESIS_NAMESPACE = UUID("f01acfc0-8e54-5ad3-9340-f40e728ea4c2")


def synthesize_market_thesis(
    *,
    market_context: MarketContext,
    regime_evidence: RegimeEvidence,
    ensemble: EnsembleForecast,
    distribution: CalibratedOutcomeDistribution,
    facts: ThesisSynthesisFacts,
    configuration: ThesisSynthesisConfiguration,
) -> ThesisSynthesisResult:
    """Construct evidence only when lineage, freshness, and quality are known."""

    _validate_lineage(
        market_context=market_context,
        regime_evidence=regime_evidence,
        ensemble=ensemble,
        distribution=distribution,
    )
    if not facts.opportunity_conditions or not facts.invalidation_conditions:
        return _insufficient("THESIS_CONDITIONS_INCOMPLETE")
    if any(level.kind is not PriceLevelKind.SUPPORT for level in facts.support_levels):
        raise ThesisSynthesisError("support_levels contains a non-support level")
    if any(level.kind is not PriceLevelKind.RESISTANCE for level in facts.resistance_levels):
        raise ThesisSynthesisError("resistance_levels contains a non-resistance level")
    allowed_sources = {
        market_context.market_context_id,
        regime_evidence.regime_evidence_id,
        ensemble.ensemble_forecast_id,
        distribution.distribution_id,
    }
    if any(
        level.source_ref not in allowed_sources
        for level in facts.support_levels + facts.resistance_levels
    ):
        raise ThesisSynthesisError("price level source is outside supplied evidence")
    if (
        market_context.data_quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED)
        or regime_evidence.quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED)
        or distribution.quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED)
    ):
        return _insufficient("EVIDENCE_QUALITY_UNACCEPTABLE")
    if regime_evidence.direction is RegimeDirection.UNKNOWN:
        return _insufficient("REGIME_DIRECTION_UNKNOWN")

    bullish = _probability(distribution, configuration.bullish_outcome_code)
    bearish = _probability(distribution, configuration.bearish_outcome_code)
    stance = _stance(
        bullish=bullish,
        bearish=bearish,
        threshold=configuration.activation_probability,
        regime_direction=regime_evidence.direction,
    )
    strength = float(min(Decimal(1), Decimal(2) * abs(max(bullish, bearish) - Decimal("0.5"))))
    expires_at = min(
        distribution.valid_until,
        market_context.as_of_time + timedelta(milliseconds=configuration.validity_ms),
    )
    if expires_at <= market_context.as_of_time:
        return _insufficient("DISTRIBUTION_EXPIRED")
    quality = (
        DataQualityState.GOOD
        if market_context.data_quality_state is DataQualityState.GOOD
        and regime_evidence.quality_state is DataQualityState.GOOD
        and distribution.quality_state is DataQualityState.GOOD
        and ensemble.status is ForecastStatus.READY
        else DataQualityState.DEGRADED
    )
    evidence_refs = (
        market_context.market_context_id,
        regime_evidence.regime_evidence_id,
        ensemble.ensemble_forecast_id,
        distribution.distribution_id,
    )
    identity = ":".join(
        (
            str(market_context.market_context_id),
            str(regime_evidence.regime_evidence_id),
            str(distribution.distribution_id),
            configuration.synthesizer_id,
            configuration.synthesizer_version,
        )
    )
    value = MarketThesis(
        schema_version="1.0",
        thesis_id=uuid5(_THESIS_NAMESPACE, identity),
        thesis_version=1,
        instrument_id=market_context.instrument_id,
        market_context_id=market_context.market_context_id,
        regime_evidence_id=regime_evidence.regime_evidence_id,
        analogue_evidence_id=None,
        ensemble_forecast_id=ensemble.ensemble_forecast_id,
        distribution_id=distribution.distribution_id,
        timeframe=market_context.timeframe,
        as_of_time=market_context.as_of_time,
        data_cutoff=market_context.data_cutoff,
        stance=stance,
        thesis_strength=strength,
        support_levels=facts.support_levels,
        resistance_levels=facts.resistance_levels,
        opportunity_conditions=facts.opportunity_conditions,
        invalidation_conditions=facts.invalidation_conditions,
        disagreement_score=ensemble.disagreement_score,
        evidence_refs=evidence_refs,
        data_quality_state=quality,
        expires_at=expires_at,
        status=MarketThesisStatus.ACTIVE,
        supersedes_version=None,
        invalidation_reason_codes=(),
        payload_hash="0" * 64,
    )
    thesis = value.model_copy(update={"payload_hash": compute_payload_hash(value)})
    return ThesisSynthesisResult(
        status=ThesisSynthesisStatus.ACTIVE_THESIS,
        thesis=thesis,
        reason_codes=("THESIS_SYNTHESIZED",),
    )


def _validate_lineage(
    *,
    market_context: MarketContext,
    regime_evidence: RegimeEvidence,
    ensemble: EnsembleForecast,
    distribution: CalibratedOutcomeDistribution,
) -> None:
    for name, value in (
        ("market context", market_context),
        ("regime evidence", regime_evidence),
        ("ensemble", ensemble),
        ("distribution", distribution),
    ):
        if compute_payload_hash(value) != value.payload_hash:
            raise ThesisSynthesisError(f"{name} payload hash mismatch")
    if ensemble.status not in (ForecastStatus.READY, ForecastStatus.DEGRADED):
        raise ThesisSynthesisError("ensemble is not thesis-eligible")
    if (
        regime_evidence.market_context_id != market_context.market_context_id
        or ensemble.market_context_id != market_context.market_context_id
        or distribution.market_context_id != market_context.market_context_id
        or regime_evidence.instrument_id != market_context.instrument_id
        or ensemble.instrument_id != market_context.instrument_id
        or distribution.instrument_id != market_context.instrument_id
        or regime_evidence.timeframe != market_context.timeframe
        or ensemble.timeframe != market_context.timeframe
        or regime_evidence.as_of_time != market_context.as_of_time
        or ensemble.as_of_time != market_context.as_of_time
        or distribution.as_of_time != market_context.as_of_time
        or regime_evidence.data_cutoff != market_context.data_cutoff
        or ensemble.data_cutoff != market_context.data_cutoff
        or distribution.data_cutoff != market_context.data_cutoff
    ):
        raise ThesisSynthesisError("market evidence lineage mismatch")
    if (
        distribution.ensemble_forecast_id != ensemble.ensemble_forecast_id
        or distribution.event_definition_id != ensemble.event_definition_id
        or distribution.horizon_bars != ensemble.horizon_bars
    ):
        raise ThesisSynthesisError("forecast/distribution lineage mismatch")
    if distribution.regime_conditioned and (
        distribution.regime_evidence_id != regime_evidence.regime_evidence_id
    ):
        raise ThesisSynthesisError("conditioned distribution regime mismatch")


def _probability(distribution: CalibratedOutcomeDistribution, outcome_code: str) -> Decimal:
    matches = tuple(item for item in distribution.outcomes if item.outcome_code == outcome_code)
    if len(matches) != 1:
        raise ThesisSynthesisError(f"outcome {outcome_code!r} must exist exactly once")
    return matches[0].probability


def _stance(
    *,
    bullish: Decimal,
    bearish: Decimal,
    threshold: Decimal,
    regime_direction: RegimeDirection,
) -> ThesisStance:
    probabilistic = (
        ThesisStance.BULLISH
        if bullish >= threshold
        else ThesisStance.BEARISH
        if bearish >= threshold
        else ThesisStance.NEUTRAL
    )
    contradiction = (
        probabilistic is ThesisStance.BULLISH and regime_direction is RegimeDirection.DOWN
    ) or (probabilistic is ThesisStance.BEARISH and regime_direction is RegimeDirection.UP)
    return ThesisStance.MIXED if contradiction else probabilistic


def _insufficient(reason: str) -> ThesisSynthesisResult:
    return ThesisSynthesisResult(
        status=ThesisSynthesisStatus.INSUFFICIENT_EVIDENCE,
        thesis=None,
        reason_codes=(reason,),
    )


__all__ = ["synthesize_market_thesis"]
