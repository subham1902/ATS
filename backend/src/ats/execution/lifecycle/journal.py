"""R17-backed minimal recoverable execution journal."""

from __future__ import annotations

import json
from typing import Protocol
from uuid import UUID, uuid5

from ats.contracts.hashing import canonical_sha256
from ats.persistence import AuditRecord, TransactionManager

from .models import ExecutionLifecycle

_AUDIT_NAMESPACE = UUID("98a9b8c5-957f-5248-a6ac-22691d28f246")


class ExecutionJournal(Protocol):
    def append(self, lifecycle: ExecutionLifecycle) -> None: ...
    def recover_latest(self, execution_id: UUID) -> ExecutionLifecycle | None: ...


class R17ExecutionJournal:
    """Commits a minimal lifecycle record before the caller proceeds."""

    def __init__(self, transaction_manager: TransactionManager) -> None:
        self._transactions = transaction_manager

    def append(self, lifecycle: ExecutionLifecycle) -> None:
        payload_without_hash = lifecycle.model_dump(mode="python", exclude={"payload_hash"})
        if canonical_sha256(payload_without_hash) != lifecycle.payload_hash:
            raise ValueError("execution lifecycle payload hash mismatch")
        payload = lifecycle.model_dump(mode="python")
        record = AuditRecord(
            audit_id=str(uuid5(_AUDIT_NAMESPACE, f"{lifecycle.execution_id}:{lifecycle.version}")),
            event_id=None,
            actor_type="SYSTEM",
            actor_id="A2_PAPER_EXECUTION_FSM",
            action=f"EXECUTION_{lifecycle.state.value}",
            object_type="EXECUTION_LIFECYCLE",
            object_id=str(lifecycle.execution_id),
            payload=payload,
            record_hash=canonical_sha256(payload),
            occurred_at=lifecycle.updated_at,
            trace_id=str(lifecycle.execution_id),
        )
        with self._transactions.transaction() as transaction:
            transaction.audit.append(record)

    def recover_latest(self, execution_id: UUID) -> ExecutionLifecycle | None:
        with self._transactions.transaction() as transaction:
            records = transaction.audit.for_object("EXECUTION_LIFECYCLE", str(execution_id))
        if not records:
            return None
        for record in records:
            if canonical_sha256(record.payload) != record.record_hash:
                raise ValueError("execution journal record hash mismatch")
        lifecycles = tuple(
            ExecutionLifecycle.model_validate_json(
                json.dumps(record.payload, sort_keys=True, separators=(",", ":"))
            )
            for record in records
        )
        if any(item.execution_id != execution_id for item in lifecycles):
            raise ValueError("execution journal object binding mismatch")
        versions = tuple(item.version for item in lifecycles)
        if len(set(versions)) != len(versions):
            raise ValueError("duplicate execution journal version")
        return max(lifecycles, key=lambda item: item.version)


__all__ = ["ExecutionJournal", "R17ExecutionJournal"]
