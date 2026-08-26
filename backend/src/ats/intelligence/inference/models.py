"""Provider-neutral inference configuration and health records."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat
from ats.contracts.domain.types import NonEmptyStr, NonNegativeInt, PositiveInt


class ReasoningMode(StrEnum):
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class ModelAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    UNCONFIGURED = "UNCONFIGURED"


class OpenRouterConfiguration(ATSBaseModel):
    provider: Literal["OPENROUTER"] = "OPENROUTER"
    model: NonEmptyStr
    max_tokens: PositiveInt
    timeout_ms: PositiveInt
    reasoning_mode: ReasoningMode
    structured_output_required: Literal[True] = True
    tool_use_required: bool
    temperature: FiniteFloat = Field(ge=0.0, le=2.0)
    maximum_attempts: PositiveInt = 2
    circuit_failure_threshold: PositiveInt = 3
    circuit_recovery_ms: PositiveInt = 30_000
    development_only_nondeterministic_routing: bool = False

    @model_validator(mode="after")
    def label_free_router(self) -> OpenRouterConfiguration:
        if self.model == "openrouter/free" and not self.development_only_nondeterministic_routing:
            raise ValueError(
                "openrouter/free must be marked development-only nondeterministic routing"
            )
        return self


class InferenceMetrics(ATSBaseModel):
    requests: NonNegativeInt
    successes: NonNegativeInt
    failures: NonNegativeInt
    retries: NonNegativeInt
    prompt_tokens: NonNegativeInt
    completion_tokens: NonNegativeInt
    total_latency_ms: NonNegativeInt
    selected_model: NonEmptyStr | None
    availability: ModelAvailability


class OpenRouterError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"OpenRouter inference unavailable: {code}")


__all__ = [
    "InferenceMetrics",
    "ModelAvailability",
    "OpenRouterConfiguration",
    "OpenRouterError",
    "ReasoningMode",
]
