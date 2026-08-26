"""Bounded OpenRouter structured-output client for advisory work."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, SecretStr, ValidationError

from .models import (
    InferenceMetrics,
    ModelAvailability,
    OpenRouterConfiguration,
    OpenRouterError,
    ReasoningMode,
)
from .transport import InferenceTransport

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class OpenRouterInferenceProvider:
    def __init__(
        self,
        *,
        configuration: OpenRouterConfiguration,
        api_key: SecretStr | None,
        transport: InferenceTransport,
        monotonic_ms: Callable[[], int],
        wait: Callable[[float], None],
    ) -> None:
        self._configuration = configuration
        self._api_key = api_key
        self._transport = transport
        self._monotonic_ms = monotonic_ms
        self._wait = wait
        self._requests = 0
        self._successes = 0
        self._failures = 0
        self._retries = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_latency_ms = 0
        self._selected_model: str | None = None
        self._consecutive_failures = 0
        self._circuit_opened_at: int | None = None

    @property
    def metrics(self) -> InferenceMetrics:
        if self._api_key is None:
            availability = ModelAvailability.UNCONFIGURED
        elif self._circuit_is_open():
            availability = ModelAvailability.CIRCUIT_OPEN
        elif self._consecutive_failures:
            availability = ModelAvailability.UNAVAILABLE
        else:
            availability = ModelAvailability.AVAILABLE
        return InferenceMetrics(
            requests=self._requests,
            successes=self._successes,
            failures=self._failures,
            retries=self._retries,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_latency_ms=self._total_latency_ms,
            selected_model=self._selected_model,
            availability=availability,
        )

    def infer(self, *, prompt: str, response_type: type[ResponseT]) -> ResponseT:
        if self._api_key is None:
            raise OpenRouterError("API_KEY_NOT_CONFIGURED")
        if not prompt.strip():
            raise ValueError("inference prompt must not be empty")
        if self._circuit_is_open():
            raise OpenRouterError("CIRCUIT_OPEN")
        self._requests += 1
        started = self._monotonic_ms()
        payload = self._payload(prompt, response_type)
        try:
            for attempt in range(1, self._configuration.maximum_attempts + 1):
                try:
                    response = self._transport.post(
                        payload=payload,
                        api_key=self._api_key,
                        timeout_ms=self._configuration.timeout_ms,
                    )
                except TimeoutError:
                    if attempt < self._configuration.maximum_attempts:
                        self._retry(attempt)
                        continue
                    raise OpenRouterError("TIMEOUT") from None
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._configuration.maximum_attempts:
                        self._retry(attempt)
                        continue
                    raise OpenRouterError(
                        "RATE_LIMITED" if response.status_code == 429 else "PROVIDER_UNAVAILABLE"
                    )
                if not 200 <= response.status_code < 300:
                    raise OpenRouterError("REQUEST_REJECTED")
                result = self._parse(response.body, response_type)
                self._successes += 1
                self._consecutive_failures = 0
                self._circuit_opened_at = None
                return result
            raise OpenRouterError("ATTEMPTS_EXHAUSTED")
        except (OpenRouterError, ValidationError, ValueError, json.JSONDecodeError) as error:
            self._record_failure()
            if isinstance(error, OpenRouterError):
                raise
            raise OpenRouterError("MALFORMED_STRUCTURED_OUTPUT") from error
        finally:
            self._total_latency_ms += max(0, self._monotonic_ms() - started)

    def _payload(self, prompt: str, response_type: type[BaseModel]) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._configuration.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._configuration.max_tokens,
            "temperature": self._configuration.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_type.__name__,
                    "strict": True,
                    "schema": response_type.model_json_schema(),
                },
            },
        }
        if self._configuration.reasoning_mode is ReasoningMode.ENABLED:
            payload["reasoning"] = {"enabled": True}
        return payload

    def _parse(self, body: bytes, response_type: type[ResponseT]) -> ResponseT:
        document = json.loads(body)
        choices = document.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("missing choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError("missing structured content")
        model = document.get("model")
        if isinstance(model, str) and model:
            self._selected_model = model
        usage = document.get("usage")
        if isinstance(usage, dict):
            self._prompt_tokens += _non_negative_int(usage.get("prompt_tokens"))
            self._completion_tokens += _non_negative_int(usage.get("completion_tokens"))
        return response_type.model_validate_json(content)

    def _retry(self, attempt: int) -> None:
        self._retries += 1
        self._wait(min(2 ** (attempt - 1), 4))

    def _record_failure(self) -> None:
        self._failures += 1
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._configuration.circuit_failure_threshold:
            self._circuit_opened_at = self._monotonic_ms()

    def _circuit_is_open(self) -> bool:
        if self._circuit_opened_at is None:
            return False
        elapsed = self._monotonic_ms() - self._circuit_opened_at
        if elapsed >= self._configuration.circuit_recovery_ms:
            self._circuit_opened_at = None
            self._consecutive_failures = 0
            return False
        return True


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


__all__ = ["OpenRouterInferenceProvider"]
