"""Narrow repository and transaction contracts for future runtime packages."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, Self

from ats.contracts.domain.models import AutonomyToken
from ats.contracts.events.models import EventEnvelope
from ats.events import OutboxRecord

from .types import (
    AuditRecord,
    EvidenceRecord,
    OrderAuthorityRecord,
    ReductionAuthorityRecord,
    StateSnapshot,
    StoredToken,
)

if TYPE_CHECKING:
    from ats.portfolio.persistence import CapitalRepository, PositionRepository


class Cursor(Protocol):
    def execute(self, query: str, params: Sequence[object] | None = None) -> Self: ...
    def fetchone(self) -> Sequence[Any] | None: ...
    def fetchall(self) -> list[Sequence[Any]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class EventStore(Protocol):
    def append(self, event: EventEnvelope) -> None: ...
    def by_aggregate(self, aggregate_id: str) -> tuple[EventEnvelope, ...]: ...
    def by_correlation(self, correlation_id: str) -> tuple[EventEnvelope, ...]: ...
    def between(self, start: datetime, end: datetime) -> tuple[EventEnvelope, ...]: ...


class OutboxRepository(Protocol):
    def append(self, record: OutboxRecord) -> None: ...
    def get_by_idempotency_key(self, key: str) -> OutboxRecord | None: ...
    def claim_pending(self, *, limit: int, claimed_at: datetime) -> tuple[OutboxRecord, ...]: ...
    def mark_dispatched(self, outbox_id: str, dispatched_at: datetime) -> None: ...
    def mark_failed(
        self, outbox_id: str, *, error: str, retry_at: datetime, unknown: bool
    ) -> None: ...
    def recover_stale_dispatches(self, *, claimed_before: datetime, retry_at: datetime) -> int: ...


class TokenRepository(Protocol):
    def issue(self, token: AutonomyToken) -> None: ...
    def get(self, token_id: str) -> StoredToken | None: ...
    def consume(
        self,
        token_id: str,
        *,
        evaluated_at: datetime,
        candidate_id: str,
        policy_id: str,
        policy_version: int,
        risk_decision_id: str,
        advisory_id: str,
        system_state_version: int,
    ) -> StoredToken: ...


class CampaignStateRepository(Protocol):
    def save(self, snapshot: StateSnapshot, *, expected_version: int | None) -> None: ...
    def get(self, campaign_id: str) -> StateSnapshot | None: ...


class CandidateEvidenceRepository(Protocol):
    def append(self, evidence: EvidenceRecord) -> None: ...
    def get(self, candidate_id: str) -> EvidenceRecord | None: ...


class RiskDecisionEvidenceRepository(Protocol):
    def append(self, evidence: EvidenceRecord, *, candidate_id: str) -> None: ...
    def get(self, risk_decision_id: str) -> EvidenceRecord | None: ...


class AdvisoryEvidenceRepository(Protocol):
    def append(
        self, evidence: EvidenceRecord, *, candidate_id: str, model_version: str
    ) -> None: ...
    def get(self, advisory_id: str) -> EvidenceRecord | None: ...


class AuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...
    def for_object(self, object_type: str, object_id: str) -> tuple[AuditRecord, ...]: ...


class OrderAuthorityRepository(Protocol):
    def append(self, record: OrderAuthorityRecord) -> None: ...
    def get_by_idempotency_key(self, key: str) -> OrderAuthorityRecord | None: ...


class ReductionAuthorityRepository(Protocol):
    def append(self, record: ReductionAuthorityRecord) -> None: ...
    def get(self, reduction_id: str) -> ReductionAuthorityRecord | None: ...
    def for_position(self, position_id: str) -> tuple[ReductionAuthorityRecord, ...]: ...


class Transaction(Protocol):
    events: EventStore
    outbox: OutboxRepository
    tokens: TokenRepository
    campaigns: CampaignStateRepository
    positions: PositionRepository
    capital: CapitalRepository
    candidates: CandidateEvidenceRepository
    risk_decisions: RiskDecisionEvidenceRepository
    advisories: AdvisoryEvidenceRepository
    audit: AuditRepository
    order_authority: OrderAuthorityRepository
    reduction_authority: ReductionAuthorityRepository

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool: ...


class TransactionManager(Protocol):
    def transaction(self) -> Transaction: ...


__all__ = [
    "AdvisoryEvidenceRepository",
    "AuditRepository",
    "CampaignStateRepository",
    "CandidateEvidenceRepository",
    "Connection",
    "Cursor",
    "EventStore",
    "OutboxRepository",
    "OrderAuthorityRepository",
    "ReductionAuthorityRepository",
    "RiskDecisionEvidenceRepository",
    "TokenRepository",
    "Transaction",
    "TransactionManager",
]
