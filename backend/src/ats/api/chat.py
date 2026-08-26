"""Safe deterministic chat composition over recorded control-plane evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ats.contracts.common import SystemClock
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_chat import (
    AgentChatRequest,
    ChatEvidence,
    ChatIntent,
    EvidenceBackedChatService,
)
from ats.intelligence.agent_governance import RuntimeChangeProposal

from .providers import ControlPlaneReader


class AgentChatHttpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    session_id: UUID
    agent_id: str
    question: str
    intent: ChatIntent
    as_of: datetime

    def to_domain(self) -> AgentChatRequest:
        return AgentChatRequest.model_validate(self.model_dump())


class ControlPlaneChatEvidenceResolver:
    def __init__(self, reader: ControlPlaneReader) -> None:
        self._reader = reader

    def resolve(self, request: AgentChatRequest) -> ChatEvidence:
        now = SystemClock().now()
        system = self._reader.get_system()
        visible_system = (
            system if system is not None and system.last_state_at <= request.as_of else None
        )
        activity = tuple(
            item for item in self._reader.list_activity() if item.occurred_at <= request.as_of
        )
        facts = {
            "question": request.question,
            "system_state": visible_system.system_state.value if visible_system else "UNKNOWN",
            "readiness": visible_system.readiness.value if visible_system else "UNKNOWN",
            "loss_state": visible_system.loss_state.value if visible_system else "UNKNOWN",
            "authority_mode": visible_system.authority_mode if visible_system else "A2_PAPER",
            "recent_activity": " | ".join(item.summary for item in activity[-10:]) or "NONE",
        }
        cutoffs = [item.occurred_at for item in activity]
        if visible_system is not None:
            cutoffs.append(visible_system.last_event_at or visible_system.last_state_at)
        return ChatEvidence(
            resolved_at=now,
            data_cutoff=max(cutoffs) if cutoffs else request.as_of,
            context_hash=canonical_sha256(facts),
            event_ids=tuple(item.activity_id for item in activity[-10:]),
            facts=facts,
        )


class DeterministicEvidenceAdvisor:
    def answer(self, *, question: str, evidence: ChatEvidence) -> str:
        facts = evidence.facts
        return (
            f"Recorded ATS state is {facts['system_state']} with readiness "
            f"{facts['readiness']} and loss state {facts['loss_state']}. "
            f"Recent recorded activity: {facts['recent_activity']}. "
            "This answer is advisory and does not authorize financial action."
        )


def build_control_plane_chat(
    reader: ControlPlaneReader, proposal_log: list[RuntimeChangeProposal]
) -> EvidenceBackedChatService:
    return EvidenceBackedChatService(
        clock=SystemClock(),
        resolver=ControlPlaneChatEvidenceResolver(reader),
        advisor=DeterministicEvidenceAdvisor(),
        proposal_sink=proposal_log.append,
    )


__all__ = [
    "ControlPlaneChatEvidenceResolver",
    "DeterministicEvidenceAdvisor",
    "AgentChatHttpRequest",
    "build_control_plane_chat",
]
