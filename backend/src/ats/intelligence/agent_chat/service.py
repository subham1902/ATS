"""Resolve evidence before advisory generation and route change requests to O4."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from ats.contracts.common import ClockProtocol
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_governance import (
    RuntimeChangeCategory,
    RuntimeChangeProposal,
    RuntimeChangeType,
)

from .models import AgentChatAnswer, AgentChatRequest, ChatEvidence, ChatIntent


class ChatEvidenceResolver(Protocol):
    def resolve(self, request: AgentChatRequest) -> ChatEvidence: ...


class ChatAdvisor(Protocol):
    def answer(self, *, question: str, evidence: ChatEvidence) -> str: ...


ProposalSink = Callable[[RuntimeChangeProposal], None]

_CHANGE_TYPES: dict[ChatIntent, tuple[RuntimeChangeCategory, RuntimeChangeType]] = {
    ChatIntent.REQUEST_SAFE_MODE: (
        RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
        RuntimeChangeType.SET_SAFE_MODE,
    ),
    ChatIntent.REQUEST_STRATEGY_PAUSE: (
        RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
        RuntimeChangeType.PAUSE_STRATEGY,
    ),
    ChatIntent.REQUEST_REDUCED_ALLOCATION: (
        RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
        RuntimeChangeType.REDUCE_ALLOCATION,
    ),
    ChatIntent.PROPOSE_EXPERIMENT: (
        RuntimeChangeCategory.RESEARCH_STATE,
        RuntimeChangeType.PROPOSE_EXPERIMENT,
    ),
}


class EvidenceBackedChatService:
    def __init__(
        self,
        *,
        clock: ClockProtocol,
        resolver: ChatEvidenceResolver,
        advisor: ChatAdvisor,
        proposal_sink: ProposalSink,
        maximum_evidence_age: timedelta = timedelta(minutes=5),
    ) -> None:
        self._clock = clock
        self._resolver = resolver
        self._advisor = advisor
        self._proposal_sink = proposal_sink
        self._maximum_evidence_age = maximum_evidence_age

    def respond(self, request: AgentChatRequest) -> AgentChatAnswer:
        evidence = self._resolver.resolve(request)
        now = self._clock.now()
        if now - evidence.data_cutoff > self._maximum_evidence_age:
            raise ValueError("CHAT_EVIDENCE_STALE")
        if evidence.context_hash != canonical_sha256(evidence.facts):
            raise ValueError("CHAT_EVIDENCE_HASH_MISMATCH")
        answer = self._advisor.answer(question=request.question, evidence=evidence).strip()
        if not answer:
            raise ValueError("CHAT_ADVISORY_EMPTY")
        refs = _all_refs(evidence)
        proposal_id = None
        change = _CHANGE_TYPES.get(request.intent)
        if change is not None:
            category, proposal_type = change
            proposal = self._proposal(request, evidence, category, proposal_type, now)
            self._proposal_sink(proposal)
            proposal_id = proposal.proposal_id
        return AgentChatAnswer(
            answer_id=uuid4(),
            request_id=request.request_id,
            generated_at=now,
            data_cutoff=evidence.data_cutoff,
            context_hash=evidence.context_hash,
            answer=answer,
            evidence_refs=refs,
            proposal_id=proposal_id,
        )

    @staticmethod
    def _proposal(
        request: AgentChatRequest,
        evidence: ChatEvidence,
        category: RuntimeChangeCategory,
        proposal_type: RuntimeChangeType,
        now: datetime,
    ) -> RuntimeChangeProposal:
        proposed_value: dict[str, object] = {"requested": True}
        current_value: dict[str, object] = {}
        if proposal_type is RuntimeChangeType.SET_SAFE_MODE:
            proposed_value = {"mode": "SAFE"}
        elif proposal_type is RuntimeChangeType.REDUCE_ALLOCATION:
            current_value = {"allocation": 1.0}
            proposed_value = {"allocation": 0.5}
        draft = RuntimeChangeProposal(
            proposal_id=uuid4(),
            agent_id=request.agent_id,
            session_id=request.session_id,
            created_at=now,
            as_of=request.as_of,
            data_cutoff=evidence.data_cutoff,
            category=category,
            proposal_type=proposal_type,
            target="runtime",
            requested_change={"chat_request_id": str(request.request_id)},
            current_value=current_value,
            proposed_value=proposed_value,
            reason=request.question,
            evidence_refs=_all_refs(evidence),
            input_hash=evidence.context_hash,
            valid_until=now + timedelta(minutes=1),
            payload_hash="0" * 64,
        )
        return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def _all_refs(evidence: ChatEvidence) -> tuple[UUID, ...]:
    return tuple(
        dict.fromkeys(
            evidence.candidate_ids
            + evidence.thesis_ids
            + evidence.position_ids
            + evidence.allocation_decision_ids
            + evidence.risk_decision_ids
            + evidence.strategy_ids
            + evidence.event_ids
            + evidence.experiment_ids
        )
    )


__all__ = ["ChatAdvisor", "ChatEvidenceResolver", "EvidenceBackedChatService", "ProposalSink"]
