from __future__ import annotations

from ats.api.models import AutonomyTokenReadModel, ErrorEnvelope, StreamEvent

from tests.unit.api.fixtures import make_api_fixture

EXPECTED_OPERATIONS = {
    ("get", "/health/live"),
    ("get", "/health/ready"),
    ("get", "/v1/system"),
    ("get", "/v1/policies/active"),
    ("get", "/v1/policies/{policy_id}"),
    ("post", "/v1/policies/validate"),
    ("get", "/v1/campaigns/{campaign_id}"),
    ("get", "/v1/candidates/{candidate_id}"),
    ("get", "/v1/governance-contexts/{context_id}"),
    ("get", "/v1/risk-decisions/{decision_id}"),
    ("get", "/v1/advisories/{advisory_id}"),
    ("get", "/v1/autonomy-tokens/{token_id}"),
    ("get", "/v1/activity"),
    ("get", "/v1/stream"),
    ("get", "/v1/operator-intelligence"),
    ("get", "/v1/operator-intelligence/stream"),
    ("get", "/v1/runtime/status"),
    ("post", "/v1/runtime/command"),
    ("post", "/v1/agent-chat"),
    ("get", "/v1/harness/status"),
    ("get", "/v1/harness/agents"),
    ("post", "/v1/harness/advisory"),
    ("get", "/v1/pipeline/counters"),
}


def test_openapi_exports_all_and_only_operator_operations() -> None:
    schema = make_api_fixture()["app"].openapi()
    operations = {
        (method, path)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operations == EXPECTED_OPERATIONS


def test_openapi_has_typed_requests_responses_and_errors() -> None:
    schema = make_api_fixture()["app"].openapi()
    validate = schema["paths"]["/v1/policies/validate"]["post"]
    assert "application/json" in validate["requestBody"]["content"]
    assert validate["responses"]["200"]["content"]["application/json"]["schema"]
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    assert "PolicyValidationRequest" in schema["components"]["schemas"]


def test_sse_openapi_declares_text_event_stream_and_no_replay_contract() -> None:
    schema = make_api_fixture()["app"].openapi()
    stream = schema["paths"]["/v1/stream"]["get"]
    assert "text/event-stream" in stream["responses"]["200"]["content"]
    assert "non-replayable" in stream["responses"]["200"]["description"].lower()


def test_safe_token_schema_excludes_nonce_and_hash() -> None:
    fields = AutonomyTokenReadModel.model_fields
    assert "nonce" not in fields
    assert "payload_hash" not in fields
    assert "state" in fields


def test_all_public_a05_models_export_json_schema() -> None:
    for model in (AutonomyTokenReadModel, ErrorEnvelope, StreamEvent):
        assert model.model_json_schema()["type"] == "object"
