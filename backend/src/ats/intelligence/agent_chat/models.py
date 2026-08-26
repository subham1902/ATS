"""Evidence-bound agent chat contracts; answers have no financial authority."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, Sha256


class ChatIntent(StrEnum):
    EXPLAIN = "EXPLAIN"
    REQUEST_SAFE_MODE = "REQUEST_SAFE_MODE"
    REQUEST_STRATEGY_PAUSE = "REQUEST_STRATEGY_PAUSE"
    REQUEST_REDUCED_ALLOCATION = "REQUEST_REDUCED_ALLOCATION"
    PROPOSE_EXPERIMENT = "PROPOSE_EXPERIMENT"


class AgentChatRequest(ATSBaseModel):
    request_id: UUID
    session_id: UUID
    agent_id: NonEmptyStr
    question: NonEmptyStr
    intent: ChatIntent
    as_of: UTCDateTime


class ChatEvidence(ATSBaseModel):
    resolved_at: UTCDateTime
    data_cutoff: UTCDateTime
    context_hash: Sha256
    candidate_ids: tuple[UUID, ...] = ()
    thesis_ids: tuple[UUID, ...] = ()
    position_ids: tuple[UUID, ...] = ()
    allocation_decision_ids: tuple[UUID, ...] = ()
    risk_decision_ids: tuple[UUID, ...] = ()
    strategy_ids: tuple[UUID, ...] = ()
    event_ids: tuple[UUID, ...] = ()
    experiment_ids: tuple[UUID, ...] = ()
    facts: dict[str, str]

    @model_validator(mode="after")
    def validate_cutoff(self) -> ChatEvidence:
        if self.data_cutoff > self.resolved_at:
            raise ValueError("chat evidence data_cutoff exceeds resolved_at")
        return self


class AgentChatAnswer(ATSBaseModel):
    answer_id: UUID
    request_id: UUID
    generated_at: UTCDateTime
    data_cutoff: UTCDateTime
    context_hash: Sha256
    answer: NonEmptyStr
    evidence_refs: tuple[UUID, ...]
    proposal_id: UUID | None
    authority: str = "ADVISORY_ONLY"


__all__ = ["AgentChatAnswer", "AgentChatRequest", "ChatEvidence", "ChatIntent"]
