"""Driver-neutral types used by PostgreSQL repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    identifier: str
    version: int
    payload: dict[str, Any]
    payload_hash: str
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    identifier: str
    version: int
    state: str
    payload: dict[str, Any]
    payload_hash: str
    updated_at: datetime
    external_state: str | None = None


@dataclass(frozen=True, slots=True)
class StoredToken:
    token_id: str
    candidate_id: str
    policy_id: str
    policy_version: int
    risk_decision_id: str
    advisory_id: str
    system_state_version: int
    scope: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None
    payload_hash: str


@dataclass(frozen=True, slots=True)
class AuditRecord:
    audit_id: str
    event_id: str | None
    actor_type: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    payload: dict[str, Any]
    record_hash: str
    occurred_at: datetime
    trace_id: str


@dataclass(frozen=True, slots=True)
class OrderAuthorityRecord:
    authority_id: str
    idempotency_key: str
    token_id: str
    external_state: str
    payload: dict[str, Any]
    payload_hash: str
    recorded_at: datetime


__all__ = [
    "AuditRecord",
    "EvidenceRecord",
    "OrderAuthorityRecord",
    "StateSnapshot",
    "StoredToken",
]
