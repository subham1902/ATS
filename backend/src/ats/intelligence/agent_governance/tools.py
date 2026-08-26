"""Explicit read-only ATS tool registry exposed to Harness agents."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from ats.contracts.hashing import canonical_sha256

from .models import AgentToolName, AgentToolResponse

ToolResolver = Callable[[Mapping[str, object]], AgentToolResponse]

FORBIDDEN_AGENT_CAPABILITIES = frozenset(
    {
        "place_order",
        "modify_order",
        "cancel_order",
        "mint_token",
        "bypass_A04",
        "modify_capital",
        "write_portfolio_ledger",
        "increase_hard_risk",
        "disable_halt",
        "enable_live",
        "promote_strategy",
    }
)


class AgentCapabilityError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Agent capability denied: {code}")


class ReadOnlyAgentToolRegistry:
    """Closed registry: only typed enum members can ever be registered or invoked."""

    def __init__(self, resolvers: Mapping[AgentToolName, ToolResolver]) -> None:
        self._resolvers = dict(resolvers)

    @property
    def available_tools(self) -> tuple[AgentToolName, ...]:
        return tuple(sorted(self._resolvers, key=str))

    def invoke(self, tool: str, arguments: Mapping[str, object]) -> AgentToolResponse:
        try:
            name = AgentToolName(tool)
        except ValueError as error:
            raise AgentCapabilityError("CAPABILITY_NOT_ALLOWLISTED") from error
        resolver = self._resolvers.get(name)
        if resolver is None:
            raise AgentCapabilityError("CAPABILITY_NOT_CONFIGURED")
        response = resolver(arguments)
        if response.tool is not name:
            raise AgentCapabilityError("TOOL_RESPONSE_IDENTITY_MISMATCH")
        if response.context_hash != canonical_sha256(response.payload):
            raise AgentCapabilityError("TOOL_RESPONSE_HASH_MISMATCH")
        return response


__all__ = [
    "AgentCapabilityError",
    "FORBIDDEN_AGENT_CAPABILITIES",
    "ReadOnlyAgentToolRegistry",
    "ToolResolver",
]
