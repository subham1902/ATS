from datetime import UTC, datetime

import pytest
from ats.contracts.hashing import canonical_sha256
from ats.intelligence.agent_governance import (
    FORBIDDEN_AGENT_CAPABILITIES,
    AgentCapabilityError,
    AgentToolName,
    AgentToolResponse,
    ReadOnlyAgentToolRegistry,
)
from ats.intelligence.harness import HARNESS_AGENT_REGISTRY, HarnessAgentType

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def test_exactly_four_bounded_agent_scopes_exist() -> None:
    assert set(HARNESS_AGENT_REGISTRY) == set(HarnessAgentType)
    for agent_type, policy in HARNESS_AGENT_REGISTRY.items():
        assert policy.agent_type is agent_type
        assert policy.tools
        assert policy.maximum_tool_calls <= 16
        assert policy.context_item_limit <= 256
        assert policy.timeout.total_seconds() <= 60
        assert policy.staleness_ttl.total_seconds() <= 300


def test_all_read_only_tools_resolve_typed_fixture_data() -> None:
    def resolver(name: AgentToolName):
        payload = {"tool": name.value, "state": "TEST_ONLY"}
        return lambda _: AgentToolResponse(
            tool=name,
            as_of=NOW,
            data_cutoff=NOW,
            context_hash=canonical_sha256(payload),
            evidence_refs=(),
            payload=payload,
        )

    registry = ReadOnlyAgentToolRegistry({name: resolver(name) for name in AgentToolName})
    for name in AgentToolName:
        assert registry.invoke(name.value, {}).tool is name


@pytest.mark.parametrize(
    "capability",
    sorted(FORBIDDEN_AGENT_CAPABILITIES)
    + ["shell", "filesystem", "sql", "network", "write_frozen_contract"],
)
def test_forbidden_and_unrestricted_capabilities_are_absent(capability: str) -> None:
    with pytest.raises(AgentCapabilityError, match="NOT_ALLOWLISTED"):
        ReadOnlyAgentToolRegistry({}).invoke(capability, {})
