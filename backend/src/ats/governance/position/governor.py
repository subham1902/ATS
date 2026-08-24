"""Pure construction of frozen, advisory-only PositionThesis evidence."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, PositionStatus
from ats.contracts.governance.models import PositionThesis
from ats.contracts.governance.types import (
    CandidateStatus,
    PositionRecommendation,
    PositionThesisState,
)
from ats.contracts.intelligence.types import MarketThesisStatus

from .models import PositionEvaluationResult, PositionObservation

_POSITION_THESIS_NAMESPACE = UUID("28c975a9-64f6-5306-8a83-e7c9cc1b7295")
_TTL = timedelta(minutes=5)


def evaluate_position(observation: PositionObservation) -> PositionEvaluationResult:
    """Return evidence only; callers must route any action through A04 separately."""

    _validate_lineage(observation)
    state, recommendation, reasons = _classify(observation)
    identity = f"{observation.position.position_id}:{observation.position.version}"
    value = PositionThesis(
        schema_version="1.0",
        position_thesis_id=uuid5(_POSITION_THESIS_NAMESPACE, identity),
        position_thesis_version=observation.position.version,
        position_id=observation.position.position_id,
        position_version=observation.position.version,
        originating_candidate_id=observation.originating_candidate.candidate_id,
        entry_thesis_id=observation.entry_thesis.thesis_id,
        entry_thesis_version=observation.entry_thesis.thesis_version,
        current_thesis_id=observation.current_thesis.thesis_id,
        current_thesis_version=observation.current_thesis.thesis_version,
        campaign_id=observation.campaign.campaign_id,
        campaign_version=observation.campaign.campaign_version,
        as_of_time=observation.evaluation_time,
        data_cutoff=observation.data_cutoff,
        state=state,
        current_distribution_id=observation.distribution.distribution_id,
        original_invalidation_conditions=observation.entry_thesis.invalidation_conditions,
        maximum_favourable_excursion_r=observation.maximum_favourable_excursion_r,
        maximum_adverse_excursion_r=observation.maximum_adverse_excursion_r,
        recommended_action=recommendation,
        reason_codes=reasons,
        evidence_refs=_evidence_refs(observation),
        expires_at=_expires_at(observation, state),
        payload_hash="0" * 64,
    )
    thesis = value.model_copy(update={"payload_hash": compute_payload_hash(value)})
    return PositionEvaluationResult(thesis=thesis, reason_codes=reasons)


def _validate_lineage(observation: PositionObservation) -> None:
    values = (
        observation.position,
        observation.originating_candidate,
        observation.entry_thesis,
        observation.current_thesis,
        observation.distribution,
        observation.campaign,
    )
    if any(compute_payload_hash(item) != item.payload_hash for item in values):
        raise ValueError("position observation contains an invalid payload hash")
    candidate = observation.originating_candidate
    if candidate.status not in (CandidateStatus.AUTHORIZED, CandidateStatus.CONSUMED):
        raise ValueError("position must originate from an authorized candidate")
    if observation.position.instrument_id != candidate.instrument_id:
        raise ValueError("position and candidate instrument mismatch")
    if (
        candidate.thesis_id != observation.entry_thesis.thesis_id
        or candidate.thesis_version != observation.entry_thesis.thesis_version
        or candidate.campaign_id != observation.campaign.campaign_id
        or candidate.campaign_version != observation.campaign.campaign_version
    ):
        raise ValueError("position candidate lineage mismatch")
    if (
        observation.current_thesis.distribution_id != observation.distribution.distribution_id
        or observation.current_thesis.market_context_id
        != observation.distribution.market_context_id
    ):
        raise ValueError("current thesis and distribution lineage mismatch")


def _classify(
    observation: PositionObservation,
) -> tuple[PositionThesisState, PositionRecommendation, tuple[str, ...]]:
    if observation.position.status is PositionStatus.CLOSED:
        return PositionThesisState.CLOSED, PositionRecommendation.UNKNOWN, ("POSITION_CLOSED",)
    if observation.invalidation_triggered:
        return PositionThesisState.INVALIDATED, PositionRecommendation.EXIT, ("THESIS_INVALIDATED",)
    if observation.session_exit_required:
        return (
            PositionThesisState.DEGRADING,
            PositionRecommendation.EXIT,
            ("SESSION_EXIT_REQUIRED",),
        )
    if observation.data_quality_state is not DataQualityState.GOOD:
        return (
            PositionThesisState.UNKNOWN,
            PositionRecommendation.UNKNOWN,
            ("MARKET_EVIDENCE_UNKNOWN",),
        )
    if observation.current_thesis.status is not MarketThesisStatus.ACTIVE:
        return (
            PositionThesisState.DEGRADING,
            PositionRecommendation.REDUCE,
            ("CURRENT_THESIS_INACTIVE",),
        )
    if observation.current_thesis.expires_at <= observation.evaluation_time:
        return (
            PositionThesisState.DEGRADING,
            PositionRecommendation.REDUCE,
            ("CURRENT_THESIS_EXPIRED",),
        )
    if observation.distribution.valid_until <= observation.evaluation_time:
        return (
            PositionThesisState.DEGRADING,
            PositionRecommendation.REDUCE,
            ("DISTRIBUTION_EXPIRED",),
        )
    if observation.risk_reduction_required:
        return (
            PositionThesisState.DEGRADING,
            PositionRecommendation.REDUCE,
            ("RISK_REDUCTION_REQUIRED",),
        )
    return PositionThesisState.HEALTHY, PositionRecommendation.HOLD, ("POSITION_THESIS_HEALTHY",)


def _expires_at(observation: PositionObservation, state: PositionThesisState) -> UTCDateTime:
    if state is PositionThesisState.CLOSED:
        return observation.evaluation_time
    if state in (PositionThesisState.DEGRADING, PositionThesisState.UNKNOWN):
        return observation.evaluation_time + _TTL
    return min(
        observation.current_thesis.expires_at,
        observation.distribution.valid_until,
        observation.evaluation_time + _TTL,
    )


def _evidence_refs(observation: PositionObservation) -> tuple[UUID, ...]:
    """Preserve deterministic lineage order while meeting frozen tuple uniqueness."""

    return tuple(
        dict.fromkeys(
            (
                observation.originating_candidate.candidate_id,
                observation.entry_thesis.thesis_id,
                observation.current_thesis.thesis_id,
                observation.distribution.distribution_id,
                observation.campaign.campaign_id,
            )
        )
    )


__all__ = ["evaluate_position"]
