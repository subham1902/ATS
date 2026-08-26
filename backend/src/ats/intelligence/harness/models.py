"""Strict control-plane records for the local DeepSeek Harness sidecar."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveInt
from ats.contracts.intelligence.types import BoundedText


class HarnessAgentType(StrEnum):
    SESSION_MARKET = "SESSION_MARKET"
    POSITION = "POSITION"
    PORTFOLIO_ANALYST = "PORTFOLIO_ANALYST"
    RESEARCH = "RESEARCH"


class HarnessRuntimeState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"


class HarnessRuntimeConfiguration(ATSBaseModel):
    source_url: Literal["https://github.com/deepseek-ai/deepseek-harness"]
    source_tag: Literal["dsh-v0.1.1-rc.2"]
    source_commit: Literal["b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"]
    license: Literal["MIT"]
    command: tuple[NonEmptyStr, ...]
    cwd: NonEmptyStr
    startup_timeout_ms: PositiveInt = 30_000
    request_timeout_ms: PositiveInt = 60_000
    maximum_pending_frames: PositiveInt = 64
    acp_protocol_version: PositiveInt = 1

    @model_validator(mode="after")
    def validate_command(self) -> HarnessRuntimeConfiguration:
        if not self.command:
            raise ValueError("Harness command must not be empty")
        return self


class HarnessHealth(ATSBaseModel):
    state: HarnessRuntimeState
    checked_at: UTCDateTime
    version: Literal["0.1.1-rc.2"]
    active_sessions: int = Field(ge=0)
    durable_resume_supported: Literal[False] = False
    reason_codes: tuple[NonEmptyStr, ...]


class HarnessSession(ATSBaseModel):
    session_id: UUID
    provider_session_id: NonEmptyStr
    agent_type: HarnessAgentType
    created_at: UTCDateTime
    last_activity_at: UTCDateTime
    active: bool


class MaterialAgentEvent(ATSBaseModel):
    event_type: NonEmptyStr
    occurred_at: UTCDateTime
    summary: BoundedText
    evidence_refs: tuple[UUID, ...]


class HarnessAdvisory(ATSBaseModel):
    session_id: UUID
    generated_at: UTCDateTime
    content: BoundedText
    provider_label: Literal["DEEPSEEK_HARNESS_LOCAL"] = "DEEPSEEK_HARNESS_LOCAL"
    authority: Literal["ADVISORY_ONLY"] = "ADVISORY_ONLY"


class HarnessRuntimeError(RuntimeError):
    """Sanitized sidecar failure; raw process output is never attached."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Harness runtime unavailable: {code}")


__all__ = [
    "HarnessAdvisory",
    "HarnessAgentType",
    "HarnessHealth",
    "HarnessRuntimeConfiguration",
    "HarnessRuntimeError",
    "HarnessRuntimeState",
    "HarnessSession",
    "MaterialAgentEvent",
]
