from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from ats.api.app import create_app
from ats.contracts.domain.types import AutonomyLevel
from ats.trading_runtime.runtime_provider import TradingRuntimeProvider
from fastapi.testclient import TestClient

from tests.unit.api.fixtures import make_api_fixture
from tests.unit.kernel.fixtures import T0, _validated, uid


def test_health_and_system_state_endpoints() -> None:
    x = make_api_fixture()
    live = x["client"].get("/health/live")
    ready = x["client"].get("/health/ready")
    system = x["client"].get("/v1/system")
    assert live.status_code == 200 and live.json()["status"] == "LIVE"
    assert ready.status_code == 200 and ready.json()["status"] == "READY"
    assert system.status_code == 200
    assert system.json()["authority_mode"] == "A2_PAPER"
    unattached = TestClient(create_app()).get("/health/ready")
    assert unattached.status_code == 503
    assert unattached.json()["status"] == "NOT_READY"


def test_default_agent_chat_is_evidence_bound_and_changes_are_proposals() -> None:
    app = create_app()
    client = TestClient(app)
    body = {
        "request_id": str(uuid4()),
        "session_id": str(uuid4()),
        "agent_id": "operator-chat",
        "question": "switch SAFE",
        "intent": "REQUEST_SAFE_MODE",
        "as_of": datetime.now(UTC).isoformat(),
    }
    response = client.post("/v1/agent-chat", json=body)
    assert response.status_code == 200
    assert response.json()["authority"] == "ADVISORY_ONLY"
    assert response.json()["proposal_id"] is not None
    assert len(app.state.runtime_change_proposals) == 1
    assert app.state.runtime_change_proposals[0].proposed_value == {"mode": "SAFE"}


def test_runtime_status_is_truthfully_unavailable_without_provider() -> None:
    response = TestClient(create_app()).get("/v1/runtime/status")
    assert response.status_code == 503


def test_runtime_status_and_all_bounded_a2_commands_use_only_injected_provider() -> None:
    provider = TradingRuntimeProvider()
    client = TestClient(create_app(trading_runtime_provider=provider))

    status = client.get("/v1/runtime/status")
    assert status.status_code == 200
    assert status.json()["trading_mode"] == {
        "user_selected": "NORMAL",
        "effective": "NORMAL",
        "deescalation_reason": None,
    }
    assert status.json()["capital"]["total"] == "100000"
    assert status.json()["open_positions"] == []

    mode = client.post("/v1/runtime/command", json={"command": "SET_MODE", "mode": "SAFE"})
    assert mode.json() == {
        "accepted": True,
        "reason_codes": ["MODE_UPDATED"],
        "effective_mode": "SAFE",
    }
    paused = client.post("/v1/runtime/command", json={"command": "PAUSE_NEW_ENTRIES"})
    assert paused.json()["reason_codes"] == ["PAUSED"]
    assert provider.get_state().paused is True
    resumed = client.post("/v1/runtime/command", json={"command": "RESUME_NEW_ENTRIES"})
    assert resumed.json()["reason_codes"] == ["RESUMED"]
    assert provider.get_state().paused is False

    exit_result = client.post(
        "/v1/runtime/command",
        json={"command": "EXIT_POSITION", "position_id": str(uuid4())},
    )
    flatten = client.post("/v1/runtime/command", json={"command": "FLATTEN_PORTFOLIO"})
    assert exit_result.json()["reason_codes"] == ["COMMAND_ACCEPTED_AWAITING_ENGINE"]
    assert flatten.json()["reason_codes"] == ["COMMAND_ACCEPTED_AWAITING_ENGINE"]

    halted = client.post("/v1/runtime/command", json={"command": "HALT_SYSTEM"})
    assert halted.json()["reason_codes"] == ["HALTED"]
    assert provider.get_state().is_halted is True


def test_policy_campaign_candidate_governance_and_risk_reads() -> None:
    x = make_api_fixture()
    requests = (
        ("/v1/policies/active", "policy_id", x["policy"].policy_id),
        (f"/v1/policies/{x['policy'].policy_id}", "policy_id", x["policy"].policy_id),
        (
            f"/v1/campaigns/{x['campaign'].campaign_id}",
            "campaign_id",
            x["campaign"].campaign_id,
        ),
        (
            f"/v1/candidates/{x['candidate'].candidate_id}",
            "candidate_id",
            x["candidate"].candidate_id,
        ),
        (
            f"/v1/governance-contexts/{x['context'].governance_context_id}",
            "governance_context_id",
            x["context"].governance_context_id,
        ),
        (
            f"/v1/risk-decisions/{x['risk_decision'].risk_decision_id}",
            "risk_decision_id",
            x["risk_decision"].risk_decision_id,
        ),
        (
            f"/v1/advisories/{x['advisory'].advisory_id}",
            "advisory_id",
            x["advisory"].advisory_id,
        ),
    )
    for path, field, expected in requests:
        response = x["client"].get(path)
        assert response.status_code == 200
        assert response.json()[field] == str(expected)


def test_policy_validation_calls_a04_without_activation() -> None:
    x = make_api_fixture()
    body = {
        "policy": x["policy"].model_dump(mode="json"),
        "evaluation_time": T0.isoformat(),
        "timeframe": "5m",
        "event_definition_id": x["policy"].event_definition_id,
        "model_version": x["policy"].compatible_model_versions[0],
        "calibrator_version": x["policy"].compatible_calibrator_versions[0],
    }
    allowed = x["client"].post("/v1/policies/validate", json=body)
    assert allowed.status_code == 200
    assert allowed.json() == {"outcome": "ALLOW", "reason_codes": ["OK"]}
    policy = _validated(x["policy"], autonomy_level=AutonomyLevel.A0)
    body["policy"] = policy.model_dump(mode="json")
    denied = x["client"].post("/v1/policies/validate", json=body)
    assert denied.status_code == 200
    assert denied.json()["outcome"] == "DENY"
    assert x["reader"].get_active_policy().autonomy_level is AutonomyLevel.A2


def test_typed_error_envelope_for_not_found_and_invalid_request() -> None:
    x = make_api_fixture()
    missing = x["client"].get(
        f"/v1/campaigns/{uid(999)}",
        headers={"X-Correlation-ID": "request-123"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"
    assert missing.json()["correlation_id"] == "request-123"
    assert "traceback" not in missing.text.lower()
    invalid = x["client"].post("/v1/policies/validate", json={})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "REQUEST_INVALID"
    assert invalid.json()["details"]


def test_safe_autonomy_activity_and_sse_visibility() -> None:
    x = make_api_fixture()
    token = x["client"].get(f"/v1/autonomy-tokens/{x['token_view'].token_id}")
    assert token.status_code == 200
    assert token.json()["scope"] == "A2_PAPER"
    assert "nonce" not in token.json() and "payload_hash" not in token.json()
    activity = x["client"].get("/v1/activity")
    assert activity.status_code == 200
    assert activity.json()["replay_supported"] is False
    class DisconnectAfterFirstEvent:
        def __init__(self) -> None:
            self.calls = 0

        async def is_disconnected(self) -> bool:
            self.calls += 1
            return self.calls > 1

    route = next(
        route for route in x["app"].routes if getattr(route, "path", None) == "/v1/stream"
    )
    stream = route.endpoint(DisconnectAfterFirstEvent(), x["reader"])
    assert stream.media_type == "text/event-stream"
    assert stream.headers["x-ats-replay-supported"] == "false"

    async def consume() -> str:
        chunks = [chunk async for chunk in stream.body_iterator]
        return "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    body = asyncio.run(consume())
    assert "event: RISK_EVALUATED" in body
    assert "command" not in body.lower()
