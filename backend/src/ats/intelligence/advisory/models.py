"""Redacted, immutable advisory-session data with no financial authority."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, UnitIntervalFloat
from ats.contracts.governance.models import PositionThesis
from ats.contracts.governance.types import PositionRecommendation
from ats.contracts.intelligence.types import BoundedText, RegisteredCode


class AdvisoryEventKind(StrEnum):
    PRICE_SHOCK = "PRICE_SHOCK"
    VOLUME_SHOCK = "VOLUME_SHOCK"
    REGIME_CHANGED = "REGIME_CHANGED"
    FORECAST_CHANGED = "FORECAST_CHANGED"
    IV_SHOCK = "IV_SHOCK"
    NEWS_EVENT = "NEWS_EVENT"
    POSITION_STOP_APPROACHING = "POSITION_STOP_APPROACHING"
    POSITION_TARGET_APPROACHING = "POSITION_TARGET_APPROACHING"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    PORTFOLIO_RISK_CHANGED = "PORTFOLIO_RISK_CHANGED"
    ORDER_REJECTED = "ORDER_REJECTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    BROKER_STATE_CHANGED = "BROKER_STATE_CHANGED"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    SESSION_EXIT_APPROACHING = "SESSION_EXIT_APPROACHING"


class AdvisoryEvent(ATSBaseModel):
    event_id: UUID
    kind: AdvisoryEventKind
    occurred_at: UTCDateTime
    position_id: UUID | None
    evidence_refs: tuple[UUID, ...]
    summary: BoundedText

    @model_validator(mode="after")
    def validate_refs(self) -> AdvisoryEvent:
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("evidence_refs must be deduplicated")
        return self


class AdvisoryProposal(ATSBaseModel):
    """A typed recommendation, deliberately not an A04 authorization or ExitIntent."""

    proposal_id: UUID
    position_id: UUID
    recommendation: PositionRecommendation
    confidence_score: UnitIntervalFloat
    reason_codes: tuple[RegisteredCode, ...]
    evidence_refs: tuple[UUID, ...]
    rationale: BoundedText
    created_at: UTCDateTime

    @model_validator(mode="after")
    def validate_refs(self) -> AdvisoryProposal:
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("evidence_refs must be deduplicated")
        return self


class PositionAdvisoryContext(ATSBaseModel):
    """Caller-owned persistent context; it is safe to present to an injected advisor."""

    session_id: UUID
    position_thesis: PositionThesis
    event_history: tuple[AdvisoryEvent, ...]
    maximum_events: PositiveInt
    created_at: UTCDateTime
    updated_at: UTCDateTime
    provider_label: NonEmptyStr

    @model_validator(mode="after")
    def validate_context(self) -> PositionAdvisoryContext:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if len(self.event_history) > self.maximum_events:
            raise ValueError("event history exceeds configured bound")
        if any(
            event.position_id is not None and event.position_id != self.position_thesis.position_id
            for event in self.event_history
        ):
            raise ValueError("event position does not match context")
        return self


__all__ = [
    "AdvisoryEvent",
    "AdvisoryEventKind",
    "AdvisoryProposal",
    "PositionAdvisoryContext",
]
