"""Persistence-facing records for A03 events and the durable outbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class OutboxState(StrEnum):
    PENDING = "PENDING"
    DISPATCHING = "DISPATCHING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


class ExternalSubmissionState(StrEnum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    outbox_id: str
    event_id: str
    topic: str
    idempotency_key: str
    payload: dict[str, Any]
    payload_hash: str
    state: OutboxState
    external_state: ExternalSubmissionState
    attempts: int
    available_at: datetime
    created_at: datetime
    locked_at: datetime | None = None
    dispatched_at: datetime | None = None
    last_error: str | None = None


__all__ = ["ExternalSubmissionState", "OutboxRecord", "OutboxState"]
