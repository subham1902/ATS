from __future__ import annotations

from pathlib import Path

API_ROOT = Path("backend/src/ats/api")


def test_api_source_contains_no_authority_or_execution_runtime() -> None:
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in API_ROOT.glob("*.py"))
    forbidden = (
        "place_order",
        "submit_order",
        "send_order",
        "paperbroker",
        "broker.login",
        "liveauthoritylease",
        "subprocess",
        "eval(",
        "exec(",
        "compile(",
        "sqlalchemy",
        "psycopg",
        "redis",
        "nats",
        "kafka",
        "datetime.now(",
        "datetime.utcnow(",
        "time.time(",
    )
    assert not {marker for marker in forbidden if marker in source}


def test_api_has_no_state_mutation_or_token_authority_routes() -> None:
    from tests.unit.api.fixtures import make_api_fixture

    schema = make_api_fixture()["app"].openapi()
    paths = set(schema["paths"])
    assert not any("order" in path or "execute" in path or "consume" in path for path in paths)
    post_paths = {path for path, operations in schema["paths"].items() if "post" in operations}
    assert post_paths == {
        "/v1/agent-chat",
        "/v1/harness/advisory",
        "/v1/policies/validate",
        "/v1/runtime/command",
    }
