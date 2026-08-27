"""Local Ollama structured-output client — first-class local provider for Harness."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, SecretStr, ValidationError

from ats.contracts.common import ATSBaseModel, FiniteFloat
from ats.contracts.domain.types import NonEmptyStr, PositiveInt

from .models import InferenceMetrics, ModelAvailability, OpenRouterError
from .transport import InferenceHttpResponse, InferenceTransport

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class OllamaConfiguration(ATSBaseModel):
    provider: Literal["LOCAL_OLLAMA"] = "LOCAL_OLLAMA"
    endpoint: NonEmptyStr = "http://127.0.0.1:11434"
    model: NonEmptyStr = "qwen3:14b"
    fallback_model: NonEmptyStr | None = "qwen2.5:14b"
    max_tokens: PositiveInt = 1024
    timeout_ms: PositiveInt = 90_000
    temperature: FiniteFloat = Field(default=0.0, ge=0.0, le=2.0)
    maximum_attempts: PositiveInt = 2
    circuit_failure_threshold: PositiveInt = 3
    circuit_recovery_ms: PositiveInt = 30_000
    supports_chat_api: bool = True


class OllamaInferenceProvider:
    def __init__(
        self,
        *,
        configuration: OllamaConfiguration,
        transport: InferenceTransport,
        monotonic_ms: Callable[[], int],
        wait: Callable[[float], None],
    ) -> None:
        self._configuration = configuration
        self._transport = transport
        self._monotonic_ms = monotonic_ms
        self._wait = wait
        self._requests = 0
        self._successes = 0
        self._failures = 0
        self._retries = 0
        self._fallback_count = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_latency_ms = 0
        self._selected_model: str | None = None
        self._last_latency_ms: int | None = None
        self._last_error_code: str | None = None
        self._consecutive_failures = 0
        self._circuit_opened_at: int | None = None

    @property
    def metrics(self) -> InferenceMetrics:
        if self._circuit_is_open():
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

    @property
    def local_provider_identity(self) -> str:
        return self._configuration.provider

    @property
    def ollama_configuration(self) -> OllamaConfiguration:
        return self._configuration

    @property
    def fallback_count(self) -> int:
        return self._fallback_count

    @property
    def last_latency_ms(self) -> int | None:
        return self._last_latency_ms

    @property
    def last_error_code(self) -> str | None:
        return self._last_error_code

    def infer(self, *, prompt: str, response_type: type[ResponseT]) -> ResponseT:
        if not prompt.strip():
            raise ValueError("inference prompt must not be empty")
        if self._circuit_is_open():
            self._last_error_code = "CIRCUIT_OPEN"
            raise OpenRouterError("CIRCUIT_OPEN")
        return self._attempt_with_fallback(prompt, response_type)

    def _attempt_with_fallback(self, prompt: str, response_type: type[ResponseT]) -> ResponseT:
        models = [self._configuration.model]
        if self._configuration.fallback_model:
            models.append(self._configuration.fallback_model)
        last_error: OpenRouterError | None = None
        for idx, model in enumerate(models):
            try:
                result = self._infer_with_model(prompt, response_type, model)
                if idx > 0:
                    self._fallback_count += 1
                return result
            except OpenRouterError as error:
                last_error = error
                if error.code in (
                    "TIMEOUT",
                    "PROVIDER_UNAVAILABLE",
                    "RATE_LIMITED",
                    "ATTEMPTS_EXHAUSTED",
                    "MALFORMED_STRUCTURED_OUTPUT",
                    "MODEL_NOT_AVAILABLE",
                ):
                    if idx + 1 < len(models):
                        continue
                raise
        assert last_error is not None
        raise last_error

    def _infer_with_model(
        self, prompt: str, response_type: type[ResponseT], model: str
    ) -> ResponseT:
        self._requests += 1
        started = self._monotonic_ms()
        try:
            for attempt in range(1, self._configuration.maximum_attempts + 1):
                payload = self._payload(prompt, response_type, model)
                try:
                    response = self._transport.post(
                        payload=payload,
                        api_key=SecretStr("not-used-local"),
                        timeout_ms=self._configuration.timeout_ms,
                    )
                except TimeoutError:
                    if attempt < self._configuration.maximum_attempts:
                        self._retry(attempt)
                        continue
                    raise OpenRouterError("TIMEOUT") from None
                if _is_model_not_available(response):
                    raise OpenRouterError("MODEL_NOT_AVAILABLE")
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
                self._last_error_code = None
                return result
            raise OpenRouterError("ATTEMPTS_EXHAUSTED")
        except (OpenRouterError, ValidationError, ValueError, json.JSONDecodeError) as error:
            self._record_failure()
            if isinstance(error, OpenRouterError):
                self._last_error_code = error.code
                raise
            self._last_error_code = "MALFORMED_STRUCTURED_OUTPUT"
            raise OpenRouterError("MALFORMED_STRUCTURED_OUTPUT") from error
        finally:
            elapsed = max(0, self._monotonic_ms() - started)
            self._total_latency_ms += elapsed
            self._last_latency_ms = elapsed

    def _payload(
        self, prompt: str, response_type: type[BaseModel], model: str
    ) -> dict[str, object]:
        schema = response_type.model_json_schema()
        if self._configuration.supports_chat_api:
            return {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": schema,
                "think": False,
                "options": {
                    "num_predict": self._configuration.max_tokens,
                    "temperature": self._configuration.temperature,
                },
                "_ollama_path": "/api/chat",
            }
        return {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {
                "num_predict": self._configuration.max_tokens,
                "temperature": self._configuration.temperature,
            },
            "_ollama_path": "/api/generate",
        }

    def _parse(self, body: bytes, response_type: type[ResponseT]) -> ResponseT:
        document = json.loads(body)
        content: str | None = None
        if isinstance(document.get("message"), dict):
            content = document["message"].get("content")
        if content is None:
            content = (
                document.get("response") if isinstance(document.get("response"), str) else None
            )
        if not isinstance(content, str):
            raise ValueError("missing structured content from Ollama")
        content_stripped = content.strip()
        if content_stripped.startswith("```"):
            lines = content_stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip().startswith("```"):
                content_stripped = "\n".join(lines[1:-1]).strip()
        if not content_stripped:
            raise ValueError("empty content from Ollama")
        start = content_stripped.find("{")
        end = content_stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = content_stripped[start : end + 1]
            try:
                json.loads(candidate)
                content_stripped = candidate
            except json.JSONDecodeError:
                pass
        try:
            return response_type.model_validate_json(content_stripped)
        except ValidationError:
            try:
                raw = json.loads(content_stripped)
                if isinstance(raw, dict):
                    allowed = set(response_type.model_fields.keys())
                    filtered = {k: v for k, v in raw.items() if k in allowed}
                    if "summary" not in filtered and "message" in raw:
                        filtered["summary"] = str(raw["message"])[:4000]
                    if "opportunity_status" not in filtered and "opportunities" in raw:
                        filtered["opportunity_status"] = str(raw["opportunities"])[:320]
                    for key in ("regime", "summary", "opportunity_status"):
                        if key not in filtered:
                            filtered[key] = "UNKNOWN — see evidence"
                    for key in ("key_observations", "evidence_refs_cited", "risks_or_caveats"):
                        if key not in filtered:
                            filtered[key] = []
                        elif not isinstance(filtered[key], list):
                            filtered[key] = [str(filtered[key])]
                    if "confidence" not in filtered or filtered["confidence"] not in (
                        "LOW",
                        "MEDIUM",
                        "HIGH",
                    ):
                        filtered["confidence"] = "LOW"
                    return response_type.model_validate(filtered)
            except Exception:
                pass
            raise
        finally:
            model = document.get("model")
            if isinstance(model, str) and model:
                self._selected_model = model
            self._prompt_tokens += _non_negative_int(document.get("prompt_eval_count"))
            self._completion_tokens += _non_negative_int(document.get("eval_count"))
            if "usage" in document and isinstance(document["usage"], dict):
                self._prompt_tokens += _non_negative_int(document["usage"].get("prompt_tokens"))
                self._completion_tokens += _non_negative_int(
                    document["usage"].get("completion_tokens")
                )

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


def _is_model_not_available(response: InferenceHttpResponse) -> bool:
    if response.status_code not in (400, 404):
        return False
    try:
        doc = json.loads(response.body) if response.body else {}
        msg = json.dumps(doc).lower()
        return "not found" in msg or "no such model" in msg or "model not" in msg
    except Exception:
        return False


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


__all__ = ["OllamaConfiguration", "OllamaInferenceProvider"]
