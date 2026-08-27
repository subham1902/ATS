from __future__ import annotations

import json

import pytest
from ats.intelligence.inference.models import OpenRouterError
from ats.intelligence.inference.ollama import OllamaConfiguration, OllamaInferenceProvider
from ats.intelligence.inference.transport import InferenceHttpResponse
from pydantic import BaseModel, ConfigDict, SecretStr


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    conclusion: str
    evidence_refs: list[str]


class FakeTransport:
    def __init__(self, responses: list[InferenceHttpResponse | Exception]) -> None:
        self.responses = iter(responses)
        self.payloads: list[dict[str, object]] = []

    def post(
        self, *, payload: dict[str, object], api_key: SecretStr, timeout_ms: int
    ) -> InferenceHttpResponse:
        assert api_key.get_secret_value() == "not-used-local"
        assert timeout_ms == 1_000
        self.payloads.append(payload)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def response(*, model: str = "qwen3:14b") -> InferenceHttpResponse:
    content = json.dumps({"conclusion": "DEFER", "evidence_refs": ["runtime:status"]})
    body = json.dumps({"model": model, "message": {"content": content}}).encode()
    return InferenceHttpResponse(status_code=200, body=body)


def provider(
    responses: list[InferenceHttpResponse | Exception],
) -> tuple[OllamaInferenceProvider, FakeTransport]:
    transport = FakeTransport(responses)
    subject = OllamaInferenceProvider(
        configuration=OllamaConfiguration(
            timeout_ms=1_000,
            maximum_attempts=1,
            circuit_failure_threshold=3,
        ),
        transport=transport,
        monotonic_ms=lambda: 0,
        wait=lambda _seconds: None,
    )
    return subject, transport


def test_primary_uses_json_schema_and_records_selected_model() -> None:
    subject, transport = provider([response()])

    assert subject.infer(prompt="assess", response_type=Answer).conclusion == "DEFER"
    assert transport.payloads[0]["format"] == Answer.model_json_schema()
    assert subject.metrics.selected_model == "qwen3:14b"
    assert subject.fallback_count == 0


def test_missing_primary_uses_pinned_qwen25_fallback() -> None:
    missing = InferenceHttpResponse(status_code=404, body=b'{"error":"model not found"}')
    subject, transport = provider([missing, response(model="qwen2.5:14b")])

    assert subject.infer(prompt="assess", response_type=Answer).conclusion == "DEFER"
    assert [payload["model"] for payload in transport.payloads] == [
        "qwen3:14b",
        "qwen2.5:14b",
    ]
    assert subject.metrics.selected_model == "qwen2.5:14b"
    assert subject.fallback_count == 1


def test_both_models_unavailable_fail_closed() -> None:
    missing = InferenceHttpResponse(status_code=404, body=b'{"error":"model not found"}')
    subject, _ = provider([missing, missing])

    with pytest.raises(OpenRouterError, match="MODEL_NOT_AVAILABLE"):
        subject.infer(prompt="assess", response_type=Answer)
    assert subject.metrics.successes == 0
    assert subject.metrics.failures == 2


def test_malformed_responses_and_transport_crashes_fail_closed() -> None:
    malformed = InferenceHttpResponse(status_code=200, body=b'{"message":{"content":"{"}}')
    subject, _ = provider([malformed, malformed])
    with pytest.raises(OpenRouterError, match="MALFORMED_STRUCTURED_OUTPUT"):
        subject.infer(prompt="assess", response_type=Answer)

    subject, _ = provider([TimeoutError(), TimeoutError()])
    with pytest.raises(OpenRouterError, match="TIMEOUT"):
        subject.infer(prompt="assess", response_type=Answer)
