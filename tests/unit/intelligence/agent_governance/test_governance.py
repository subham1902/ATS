from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_governance import (
    FORBIDDEN_AGENT_CAPABILITIES,
    AgentCapabilityError,
    AgentToolName,
    AgentToolResponse,
    GovernedAgentOutput,
    MaterialWakeCoalescer,
    MaterialWakeEvent,
    MaterialWakeKind,
    ReadOnlyAgentToolRegistry,
    RuntimeChangeCategory,
    RuntimeChangeGovernor,
    RuntimeChangeOutcome,
    RuntimeChangeProposal,
    RuntimeChangeType,
)
from ats.trading_runtime.modes import TradingMode

NOW = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def now(self) -> datetime:
        return self.value


def proposal(
    kind: RuntimeChangeType,
    *,
    category: RuntimeChangeCategory = RuntimeChangeCategory.BOUNDED_RUNTIME_CONFIG,
    current: dict[str, object] | None = None,
    proposed: dict[str, object] | None = None,
) -> RuntimeChangeProposal:
    draft = RuntimeChangeProposal(
        proposal_id=uuid4(),
        agent_id="research-agent",
        session_id=uuid4(),
        created_at=NOW,
        as_of=NOW,
        data_cutoff=NOW,
        category=category,
        proposal_type=kind,
        target="runtime",
        requested_change={"kind": kind.value},
        current_value=current or {},
        proposed_value=proposed or {},
        reason="evidence-bound request",
        evidence_refs=(uuid4(),),
        input_hash="a" * 64,
        valid_until=NOW + timedelta(minutes=1),
        payload_hash="0" * 64,
    )
    return draft.model_copy(update={"payload_hash": compute_payload_hash(draft)})


def test_tool_allowlist_is_complete_and_forbidden_tools_are_absent() -> None:
    assert len(AgentToolName) == 13
    assert "place_order" not in {item.value for item in AgentToolName}
    assert {"place_order", "mint_token", "enable_live", "bypass_A04"} <= (
        FORBIDDEN_AGENT_CAPABILITIES
    )


def test_registry_rejects_unknown_and_hash_mismatched_responses() -> None:
    registry = ReadOnlyAgentToolRegistry({})
    with pytest.raises(AgentCapabilityError, match="CAPABILITY_NOT_ALLOWLISTED"):
        registry.invoke("place_order", {})

    response = AgentToolResponse(
        tool=AgentToolName.GET_MARKET_CONTEXT,
        as_of=NOW,
        data_cutoff=NOW,
        context_hash="a" * 64,
        evidence_refs=(),
        payload={"state": "FRESH"},
    )
    registry = ReadOnlyAgentToolRegistry({AgentToolName.GET_MARKET_CONTEXT: lambda _: response})
    with pytest.raises(AgentCapabilityError, match="TOOL_RESPONSE_HASH_MISMATCH"):
        registry.invoke("get_market_context", {})


def test_registry_returns_typed_bounded_response() -> None:
    payload = {"state": "FRESH"}
    response = AgentToolResponse(
        tool=AgentToolName.GET_MARKET_CONTEXT,
        as_of=NOW,
        data_cutoff=NOW,
        context_hash=canonical_sha256(payload),
        evidence_refs=(),
        payload=payload,
    )
    registry = ReadOnlyAgentToolRegistry({AgentToolName.GET_MARKET_CONTEXT: lambda _: response})
    assert registry.invoke("get_market_context", {}).payload == payload


@pytest.mark.parametrize(
    "kind",
    [
        RuntimeChangeType.SET_AGGRESSIVE_MODE,
        RuntimeChangeType.INCREASE_HARD_RISK,
        RuntimeChangeType.PLACE_ORDER,
        RuntimeChangeType.PROMOTE_STRATEGY,
    ],
)
def test_risk_broadening_and_financial_authority_are_rejected(kind: RuntimeChangeType) -> None:
    decision = RuntimeChangeGovernor(clock=Clock()).evaluate(
        proposal(kind), effective_mode=TradingMode.NORMAL
    )
    assert decision.outcome is RuntimeChangeOutcome.REJECT


def test_valid_research_action_and_safe_deescalation_are_applied_and_audited() -> None:
    governor = RuntimeChangeGovernor(clock=Clock())
    research = proposal(
        RuntimeChangeType.CREATE_HYPOTHESIS,
        category=RuntimeChangeCategory.RESEARCH_STATE,
        proposed={"question": "Does IV acceleration improve timing?"},
    )
    safe = proposal(RuntimeChangeType.SET_SAFE_MODE, proposed={"mode": "SAFE"})
    assert (
        governor.evaluate(research, effective_mode=TradingMode.NORMAL).outcome
        is RuntimeChangeOutcome.APPLY
    )
    assert (
        governor.evaluate(safe, effective_mode=TradingMode.AGGRESSIVE).outcome
        is RuntimeChangeOutcome.APPLY
    )
    assert len(governor.audits) == 2


def test_allocation_must_strictly_decrease() -> None:
    governor = RuntimeChangeGovernor(clock=Clock())
    bad = proposal(
        RuntimeChangeType.REDUCE_ALLOCATION,
        current={"allocation": 0.4},
        proposed={"allocation": 0.5},
    )
    assert (
        governor.evaluate(bad, effective_mode=TradingMode.NORMAL).outcome
        is RuntimeChangeOutcome.REJECT
    )


def test_stale_tampered_and_duplicate_proposals_fail_closed() -> None:
    clock = Clock()
    governor = RuntimeChangeGovernor(clock=clock)
    value = proposal(RuntimeChangeType.REQUEST_POSITION_REVIEW)
    clock.value = NOW + timedelta(minutes=2)
    stale = governor.evaluate(value, effective_mode=TradingMode.NORMAL)
    assert stale.reason_codes == ("PROPOSAL_STALE",)
    assert governor.evaluate(value, effective_mode=TradingMode.NORMAL) is stale

    tampered = proposal(RuntimeChangeType.REQUEST_POSITION_REVIEW).model_copy(
        update={"reason": "changed after signing"}
    )
    assert RuntimeChangeGovernor(clock=Clock()).evaluate(
        tampered, effective_mode=TradingMode.NORMAL
    ).reason_codes == ("PROPOSAL_HASH_MISMATCH",)


def test_stale_agent_output_cannot_change_current_runtime() -> None:
    clock = Clock()
    output = GovernedAgentOutput(
        output_id=uuid4(),
        agent_id="agent",
        session_id=uuid4(),
        as_of=NOW,
        data_cutoff=NOW,
        context_hash="a" * 64,
        generated_at=NOW,
        valid_until=NOW + timedelta(seconds=5),
        evidence_refs=(),
        content="Advisory only",
    )
    governor = RuntimeChangeGovernor(clock=clock)
    assert governor.output_is_current(output, context_hash="a" * 64)
    clock.value += timedelta(seconds=6)
    assert not governor.output_is_current(output, context_hash="a" * 64)


def test_material_wakes_are_deduplicated_and_memory_bounded() -> None:
    coalescer = MaterialWakeCoalescer(maximum_pending=2, deduplication_window=timedelta(seconds=5))
    first = MaterialWakeEvent(
        event_id=uuid4(),
        kind=MaterialWakeKind.PRICE_SHOCK,
        scope="NIFTY",
        occurred_at=NOW,
        evidence_refs=(),
        context_hash="a" * 64,
    )
    duplicate = first.model_copy(
        update={"event_id": uuid4(), "occurred_at": NOW + timedelta(seconds=1)}
    )
    second = first.model_copy(update={"event_id": uuid4(), "kind": MaterialWakeKind.IV_SHOCK})
    third = first.model_copy(update={"event_id": uuid4(), "kind": MaterialWakeKind.OI_SHIFT})
    assert coalescer.submit(first)
    assert not coalescer.submit(duplicate)
    assert coalescer.submit(second)
    assert coalescer.submit(third)
    assert coalescer.pending_count == 2
