"""Contract: the operator console exposes research capability but no financial authority.

The A05 read-only surface is pinned to a fixed operation set by
``test_openapi_exports_all_and_only_a05_operations``. This module pins the
*other* side of the split: :mod:`ats.console` is the operator workbench, so it is
allowed to be broad, but it must never be able to construct, authorize or route
an order.

Authority to construct an ``OrderIntent`` and mint an ``AutonomyToken`` belongs
exclusively to the A04 authority chain
(``ATS_QUANT_RESEARCH_CONSTITUTION_v1.0.md`` §1.2). If a console route ever
grows one, this test fails.
"""

from __future__ import annotations

from pathlib import Path

CONSOLE_ROOT = Path("backend/src/ats/console")

# Substrings that would indicate the console reaching into execution authority.
FORBIDDEN_AUTHORITY_MARKERS = (
    "orderintent(",
    "autonomytoken(",
    "liveauthoritylease",
    "a04authorit",
    "authorize_order",
    "route_to_gateway",
    "broker.login(",
    "broker_login(",
)


def _console_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8").lower() for path in CONSOLE_ROOT.glob("*.py"))


def test_console_source_does_not_construct_authorization_objects() -> None:
    """The console must never build an order intent or autonomy token itself."""
    source = _console_source()
    assert not {marker for marker in FORBIDDEN_AUTHORITY_MARKERS if marker in source}


def test_console_exposes_no_order_execution_or_consume_route() -> None:
    """No console path may place, execute or consume an order."""
    from ats.console.app import create_console_app

    schema = create_console_app().openapi()
    paths = set(schema["paths"])
    offending = {
        path for path in paths if "order" in path or "execute" in path or "consume" in path
    }
    assert not offending, f"console exposes execution-shaped routes: {sorted(offending)}"


def test_console_does_not_mount_a_broker_login_capability() -> None:
    """The broker surface is manifest/read-only; it must not open a broker session."""
    from ats.console.app import create_console_app

    schema = create_console_app().openapi()
    post_paths = {path for path, operations in schema["paths"].items() if "post" in operations}
    assert not any("login" in path for path in post_paths)


def test_deleted_external_advisory_routes_cannot_authorize_or_raise_limits() -> None:
    from ats.console.app import create_console_app
    from fastapi.testclient import TestClient

    client = TestClient(create_console_app())
    for action in ("authorize_candidate", "update_agent_principal"):
        response = client.post("/v1/ai/laya/action", json={"action_type": action})
        assert response.status_code == 404


def test_a05_surface_remains_a_strict_subset_of_the_console() -> None:
    """The served app must still serve the full A05 projection.

    Splitting the surfaces must not silently drop the constitution read routes
    from the app the operator actually talks to.
    """
    from ats.api.app import create_app as create_a05_app
    from ats.console.app import create_console_app

    a05_ops = {
        (method, path)
        for path, methods in create_a05_app().openapi()["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    console_ops = {
        (method, path)
        for path, methods in create_console_app().openapi()["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert a05_ops <= console_ops
    assert console_ops > a05_ops, "console should expose the workbench beyond A05"
