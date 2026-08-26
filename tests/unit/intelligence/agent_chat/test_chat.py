from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_chat import (
    AgentChatRequest,
    ChatEvidence,
    ChatIntent,
    EvidenceBackedChatService,
)
from ats.intelligence.agent_governance import RuntimeChangeType

NOW = datetime(2026, 8, 27, tzinfo=UTC)


class Clock:
    def now(self) -> datetime:
        return NOW


class Resolver:
    def __init__(self, evidence: ChatEvidence) -> None:
        self.evidence = evidence

    def resolve(self, request: AgentChatRequest) -> ChatEvidence:
        return self.evidence


class Advisor:
    def answer(self, *, question: str, evidence: ChatEvidence) -> str:
        return f"Recorded evidence: {evidence.facts['reason']}"


def evidence(*, cutoff: datetime = NOW) -> ChatEvidence:
    facts = {"reason": "drawdown de-escalation"}
    return ChatEvidence(
        resolved_at=NOW,
        data_cutoff=cutoff,
        context_hash=canonical_sha256(facts),
        risk_decision_ids=(uuid4(),),
        facts=facts,
    )


def request(intent: ChatIntent) -> AgentChatRequest:
    return AgentChatRequest(
        request_id=uuid4(),
        session_id=uuid4(),
        agent_id="portfolio-analyst",
        question="Why are we safe?",
        intent=intent,
        as_of=NOW,
    )


def test_explanation_is_evidence_bound_and_has_no_proposal() -> None:
    proposals = []
    answer = EvidenceBackedChatService(
        clock=Clock(),
        resolver=Resolver(evidence()),
        advisor=Advisor(),
        proposal_sink=proposals.append,
    ).respond(request(ChatIntent.EXPLAIN))
    assert answer.authority == "ADVISORY_ONLY"
    assert answer.evidence_refs
    assert answer.proposal_id is None
    assert not proposals


def test_chat_change_creates_governed_proposal_not_direct_mutation() -> None:
    proposals = []
    answer = EvidenceBackedChatService(
        clock=Clock(),
        resolver=Resolver(evidence()),
        advisor=Advisor(),
        proposal_sink=proposals.append,
    ).respond(request(ChatIntent.REQUEST_SAFE_MODE))
    assert answer.proposal_id == proposals[0].proposal_id
    assert proposals[0].proposal_type is RuntimeChangeType.SET_SAFE_MODE
    assert proposals[0].proposed_value == {"mode": "SAFE"}


def test_stale_or_tampered_evidence_is_rejected() -> None:
    stale = evidence(cutoff=NOW - timedelta(minutes=6))
    service = EvidenceBackedChatService(
        clock=Clock(),
        resolver=Resolver(stale),
        advisor=Advisor(),
        proposal_sink=lambda _: None,
    )
    with pytest.raises(ValueError, match="CHAT_EVIDENCE_STALE"):
        service.respond(request(ChatIntent.EXPLAIN))
    bad = evidence().model_copy(update={"facts": {"reason": "invented"}})
    service = EvidenceBackedChatService(
        clock=Clock(),
        resolver=Resolver(bad),
        advisor=Advisor(),
        proposal_sink=lambda _: None,
    )
    with pytest.raises(ValueError, match="CHAT_EVIDENCE_HASH_MISMATCH"):
        service.respond(request(ChatIntent.EXPLAIN))
