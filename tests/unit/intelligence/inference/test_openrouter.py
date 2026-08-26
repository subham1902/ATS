from __future__ import annotations

import json

import pytest
from ats.intelligence.inference import (
    InferenceHttpResponse,
    ModelAvailability,
    OpenRouterConfiguration,
    OpenRouterError,
    OpenRouterInferenceProvider,
    ReasoningMode,
)
from pydantic import BaseModel, ConfigDict, SecretStr


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    conclusion: str
    evidence_refs: list[str]


TEST_KEY = SecretStr("test-only-key")


class FakeTransport:
    def __init__(self, responses: list[InferenceHttpResponse | Exception]) -> None:
        self.responses = iter(responses)
        self.payloads: list[dict[str, object]] = []

    def post(
        self, *, payload: dict[str, object], api_key: SecretStr, timeout_ms: int
    ) -> InferenceHttpResponse:
        assert api_key.get_secret_value() == "test-only-key"
        assert timeout_ms == 1000
        self.payloads.append(payload)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class Monotonic:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        self.value += 5
        return self.value


def configuration(**overrides: object) -> OpenRouterConfiguration:
    values: dict[str, object] = {
        "model": "openrouter/free",
        "max_tokens": 200,
        "timeout_ms": 1000,
        "reasoning_mode": ReasoningMode.DISABLED,
        "tool_use_required": False,
        "temperature": 0.0,
        "maximum_attempts": 2,
        "circuit_failure_threshold": 2,
        "circuit_recovery_ms": 100,
        "development_only_nondeterministic_routing": True,
    }
    values.update(overrides)
    return OpenRouterConfiguration.model_validate(values)


def success_body() -> bytes:
    return json.dumps(
        {
            "model": "test/selected-model:free",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"conclusion": "DEFER", "evidence_refs": ["evidence-1"]}
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
    ).encode()


def provider(
    responses: list[InferenceHttpResponse | Exception],
    *,
    key: SecretStr | None = TEST_KEY,
    config: OpenRouterConfiguration | None = None,
) -> tuple[OpenRouterInferenceProvider, FakeTransport, list[float], Monotonic]:
    transport = FakeTransport(responses)
    waits: list[float] = []
    monotonic = Monotonic()
    subject = OpenRouterInferenceProvider(
        configuration=config or configuration(),
        api_key=key,
        transport=transport,
        monotonic_ms=monotonic,
        wait=waits.append,
    )
    return subject, transport, waits, monotonic


def test_success_requires_schema_and_records_usage() -> None:
    subject, transport, _, _ = provider(
        [InferenceHttpResponse(status_code=200, body=success_body())]
    )
    result = subject.infer(prompt="assess", response_type=Answer)
    assert result.conclusion == "DEFER"
    response_format = transport.payloads[0]["response_format"]
    assert isinstance(response_format, dict) and response_format["type"] == "json_schema"
    assert subject.metrics.prompt_tokens == 10
    assert subject.metrics.selected_model == "test/selected-model:free"


def test_malformed_json_and_schema_are_rejected() -> None:
    malformed = InferenceHttpResponse(status_code=200, body=b'{"choices":[')
    subject, _, _, _ = provider([malformed])
    with pytest.raises(OpenRouterError, match="MALFORMED_STRUCTURED_OUTPUT"):
        subject.infer(prompt="assess", response_type=Answer)

    wrong = json.dumps(
        {"choices": [{"message": {"content": '{"conclusion":1,"evidence_refs":[]}'}}]}
    ).encode()
    subject, _, _, _ = provider([InferenceHttpResponse(status_code=200, body=wrong)])
    with pytest.raises(OpenRouterError, match="MALFORMED_STRUCTURED_OUTPUT"):
        subject.infer(prompt="assess", response_type=Answer)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_failures_are_bounded(status: int) -> None:
    subject, transport, waits, _ = provider(
        [
            InferenceHttpResponse(status_code=status, body=b"{}"),
            InferenceHttpResponse(status_code=200, body=success_body()),
        ]
    )
    assert subject.infer(prompt="assess", response_type=Answer).conclusion == "DEFER"
    assert len(transport.payloads) == 2
    assert waits == [1]


def test_timeout_is_bounded() -> None:
    subject, _, waits, _ = provider([TimeoutError(), TimeoutError()])
    with pytest.raises(OpenRouterError, match="TIMEOUT"):
        subject.infer(prompt="assess", response_type=Answer)
    assert waits == [1]


def test_circuit_breaker_opens_and_recovers() -> None:
    config = configuration(maximum_attempts=1)
    responses = [
        InferenceHttpResponse(status_code=503, body=b"{}"),
        InferenceHttpResponse(status_code=503, body=b"{}"),
        InferenceHttpResponse(status_code=200, body=success_body()),
    ]
    subject, _, _, monotonic = provider(responses, config=config)
    for _ in range(2):
        with pytest.raises(OpenRouterError, match="PROVIDER_UNAVAILABLE"):
            subject.infer(prompt="assess", response_type=Answer)
    assert subject.metrics.availability is ModelAvailability.CIRCUIT_OPEN
    with pytest.raises(OpenRouterError, match="CIRCUIT_OPEN"):
        subject.infer(prompt="assess", response_type=Answer)
    monotonic.value += 100
    assert subject.infer(prompt="assess", response_type=Answer).conclusion == "DEFER"


def test_missing_key_is_unconfigured_without_transport_call() -> None:
    subject, transport, _, _ = provider([], key=None)
    with pytest.raises(OpenRouterError, match="API_KEY_NOT_CONFIGURED"):
        subject.infer(prompt="assess", response_type=Answer)
    assert not transport.payloads
    assert subject.metrics.availability is ModelAvailability.UNCONFIGURED


def test_free_router_requires_explicit_development_label() -> None:
    with pytest.raises(ValueError, match="development-only"):
        configuration(development_only_nondeterministic_routing=False)
    assert configuration(model="vendor/pinned-model").model == "vendor/pinned-model"
