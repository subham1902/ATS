"""Immutable execution state with stable intent, reservation, token, and idempotency binding."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveInt, Sha256
from ats.contracts.intelligence.types import RegisteredCode


class ExecutionState(StrEnum):
    DRAFT = "DRAFT"
    AUTHORIZED = "AUTHORIZED"
    RESERVED = "RESERVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED_UNACKNOWLEDGED = "SUBMITTED_UNACKNOWLEDGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    RECONCILING = "RECONCILING"
    CLOSED = "CLOSED"


class ExecutionLifecycle(ATSBaseModel):
    schema_version: Literal["1.0"]
    execution_id: UUID
    intent_id: UUID
    reservation_id: UUID
    autonomy_token_id: UUID
    idempotency_key: NonEmptyStr
    instrument_id: RegisteredCode
    state: ExecutionState
    paper_order_id: UUID | None
    reason_codes: tuple[RegisteredCode, ...]
    created_at: UTCDateTime
    updated_at: UTCDateTime
    version: PositiveInt
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_lifecycle(self) -> ExecutionLifecycle:
        if self.updated_at < self.created_at:
            raise ValueError("execution update cannot precede creation")
        if (
            self.state
            in {
                ExecutionState.ACKNOWLEDGED,
                ExecutionState.PARTIALLY_FILLED,
                ExecutionState.FILLED,
                ExecutionState.CANCEL_PENDING,
                ExecutionState.CANCELLED,
            }
            and self.paper_order_id is None
        ):
            raise ValueError("acknowledged/order states require paper_order_id")
        return self


__all__ = ["ExecutionLifecycle", "ExecutionState"]
