"""LLM provider seam — no API keys, no model download, no remote call on hot path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    model: str
    max_tokens: int = 512


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    latency_ms: int
    provider: str


class LLMProvider(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def health(self) -> str: ...


class FakeLLMProvider:
    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=f"[FAKE:{request.model}] {request.prompt[:64]}",
            model=request.model,
            latency_ms=1,
            provider="fake",
        )

    def health(self) -> str:
        return "HEALTHY"


class LocalLLMProvider:
    def __init__(self, *, endpoint: str = "http://localhost:11434") -> None:
        self._endpoint = endpoint

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=f"[LOCAL:{request.model}@{self._endpoint}] stub",
            model=request.model,
            latency_ms=5,
            provider="local",
        )

    def health(self) -> str:
        return "NOT_CONFIGURED"


class OpenRouterProvider:
    def __init__(self, *, endpoint: str = "https://openrouter.ai/api/v1") -> None:
        self._endpoint = endpoint

    def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=f"[OPENROUTER:{request.model}@{self._endpoint}] stub",
            model=request.model,
            latency_ms=5,
            provider="openrouter",
        )

    def health(self) -> str:
        return "NOT_CONFIGURED"


__all__ = [
    "FakeLLMProvider",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LocalLLMProvider",
    "OpenRouterProvider",
]
