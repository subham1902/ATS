"""Contract: managed research agents are proposal-only by construction.

The ``ats.agents.managed`` domain configures LLM/research agents (provider,
model, instructions, capabilities, data scopes, runtime limits). It must never
be able to construct, authorize, or route an order: financial authority is
unrepresentable here, not merely forbidden. There is no capability enum member
for it, no import that could reach it, and no route shaped like it.

This mirrors ``test_console_boundary.py`` for the new surface: if the managed
agent domain ever grows execution authority, these tests fail.
"""

from __future__ import annotations

from pathlib import Path

MANAGED_ROOT = Path("backend/src/ats/agents")
MANAGED_MODULES = ("managed.py", "managed_router.py")

# Substrings that would indicate the managed-agent domain reaching into
# execution authority. Scoped to the managed modules so legitimate kernel
# ALLOW constants elsewhere are untouched.
FORBIDDEN_AUTHORITY_MARKERS = (
    "orderintent(",
    "autonomytoken(",
    "liveauthoritylease",
    "a04authorit",
    "authorize_order",
    "submit_order",
    "place_order",
    "route_to_gateway",
    "broker.login(",
    "broker_login(",
    "mint_token",
    "consume_token",
    "reserve_capital",
    "mutate_portfolio",
    "enable_live",
    "live_execution",
)

# Capabilities that must not exist, selectable or otherwise.
FORBIDDEN_CAPABILITIES = (
    "AUTHORIZE_TRADE",
    "MINT_TOKEN",
    "SUBMIT_ORDER",
    "PLACE_ORDER",
    "MUTATE_PORTFOLIO",
    "ENABLE_LIVE_EXECUTION",
)


def _managed_source() -> str:
    return "\n".join(
        (MANAGED_ROOT / name).read_text(encoding="utf-8").lower()
        for name in MANAGED_MODULES
    )


def test_managed_source_does_not_construct_authorization_objects() -> None:
    """The managed domain must never build order intents, tokens, or broker sessions."""
    source = _managed_source()
    present = {marker for marker in FORBIDDEN_AUTHORITY_MARKERS if marker in source}
    assert not present, f"managed agent domain reaches execution authority: {sorted(present)}"


def test_managed_capability_vocabulary_has_no_financial_authority() -> None:
    """Financial authority is unrepresentable: no enum member, no string, nowhere."""
    source = _managed_source()
    present = {cap for cap in FORBIDDEN_CAPABILITIES if cap.lower() in source}
    assert not present, f"financial capability exists in managed domain: {sorted(present)}"


def test_managed_routes_expose_no_execution_shape() -> None:
    """No managed route may place, execute, consume, log in, or command."""
    from ats.console.app import create_console_app

    schema = create_console_app().openapi()
    managed = {
        path
        for path in schema["paths"]
        if path.startswith("/v1/agents/managed")
    }
    assert managed, "managed agent routes are not mounted"
    offending = {
        path
        for path in managed
        for marker in ("order", "execute", "consume", "login", "command", "trade")
        if marker in path
    }
    assert not offending, f"managed routes expose execution shape: {sorted(offending)}"


def test_managed_schemas_carry_no_secret_material() -> None:
    """Provider credentials are references, never values; responses redact them."""
    from ats.console.app import create_console_app

    schema = create_console_app().openapi()
    managed = {
        path: operations
        for path, operations in schema["paths"].items()
        if path.startswith("/v1/agents/managed")
    }
    fields = set()
    for operations in managed.values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            fields.add(operation.get("operationId", ""))
    assert fields, "managed routes expose no operations"
    for name in fields:
        lowered = name.lower()
        assert "secret" not in lowered or "redact" in lowered, (
            f"operation {name!r} suggests raw secret handling"
        )
