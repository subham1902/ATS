"""Fail-closed execution transitions and PaperBroker result adapters."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import PaperOrderStatus
from ats.contracts.hashing import canonical_sha256
from ats.execution.paper import (
    PaperExecutionResult,
    PaperReconciliationResult,
    PaperSubmissionState,
    ReconciliationOutcome,
)

from .journal import ExecutionJournal
from .models import ExecutionLifecycle, ExecutionState

_ALLOWED: Mapping[ExecutionState, frozenset[ExecutionState]] = {
    ExecutionState.DRAFT: frozenset({ExecutionState.AUTHORIZED}),
    ExecutionState.AUTHORIZED: frozenset({ExecutionState.RESERVED}),
    ExecutionState.RESERVED: frozenset({ExecutionState.SUBMITTING, ExecutionState.REJECTED}),
    ExecutionState.SUBMITTING: frozenset(
        {
            ExecutionState.SUBMITTED_UNACKNOWLEDGED,
            ExecutionState.ACKNOWLEDGED,
            ExecutionState.PARTIALLY_FILLED,
            ExecutionState.FILLED,
            ExecutionState.CANCELLED,
            ExecutionState.REJECTED,
        }
    ),
    ExecutionState.SUBMITTED_UNACKNOWLEDGED: frozenset(
        {
            ExecutionState.ACKNOWLEDGED,
            ExecutionState.PARTIALLY_FILLED,
            ExecutionState.FILLED,
            ExecutionState.CANCELLED,
            ExecutionState.REJECTED,
            ExecutionState.RECONCILING,
        }
    ),
    ExecutionState.ACKNOWLEDGED: frozenset(
        {
            ExecutionState.PARTIALLY_FILLED,
            ExecutionState.FILLED,
            ExecutionState.CANCEL_PENDING,
            ExecutionState.REJECTED,
            ExecutionState.RECONCILING,
        }
    ),
    ExecutionState.PARTIALLY_FILLED: frozenset(
        {
            ExecutionState.PARTIALLY_FILLED,
            ExecutionState.FILLED,
            ExecutionState.CANCEL_PENDING,
            ExecutionState.RECONCILING,
        }
    ),
    ExecutionState.CANCEL_PENDING: frozenset(
        {ExecutionState.CANCELLED, ExecutionState.RECONCILING}
    ),
    ExecutionState.RECONCILING: frozenset(
        {
            ExecutionState.RECONCILING,
            ExecutionState.ACKNOWLEDGED,
            ExecutionState.PARTIALLY_FILLED,
            ExecutionState.FILLED,
            ExecutionState.CANCELLED,
            ExecutionState.REJECTED,
        }
    ),
    ExecutionState.FILLED: frozenset({ExecutionState.CLOSED}),
    ExecutionState.CANCELLED: frozenset({ExecutionState.CLOSED}),
    ExecutionState.REJECTED: frozenset({ExecutionState.CLOSED}),
    ExecutionState.CLOSED: frozenset(),
}


def create_execution(
    *,
    execution_id: UUID,
    intent_id: UUID,
    reservation_id: UUID,
    autonomy_token_id: UUID,
    idempotency_key: str,
    instrument_id: str,
    created_at: UTCDateTime,
    journal: ExecutionJournal,
) -> ExecutionLifecycle:
    values = {
        "schema_version": "1.0",
        "execution_id": execution_id,
        "intent_id": intent_id,
        "reservation_id": reservation_id,
        "autonomy_token_id": autonomy_token_id,
        "idempotency_key": idempotency_key,
        "instrument_id": instrument_id,
        "state": ExecutionState.DRAFT,
        "paper_order_id": None,
        "reason_codes": ("EXECUTION_DRAFT_CREATED",),
        "created_at": created_at,
        "updated_at": created_at,
        "version": 1,
    }
    lifecycle = ExecutionLifecycle.model_validate(
        {**values, "payload_hash": canonical_sha256(values)}
    )
    journal.append(lifecycle)
    return lifecycle


def transition_execution(
    lifecycle: ExecutionLifecycle,
    *,
    target: ExecutionState,
    updated_at: UTCDateTime,
    journal: ExecutionJournal,
    paper_order_id: UUID | None = None,
    reason_codes: tuple[str, ...] = (),
) -> ExecutionLifecycle:
    _verify_hash(lifecycle)
    if target not in _ALLOWED[lifecycle.state]:
        raise ValueError(f"illegal execution transition {lifecycle.state.value}->{target.value}")
    if updated_at < lifecycle.updated_at:
        raise ValueError("execution update time moved backwards")
    values = lifecycle.model_dump(mode="python", exclude={"payload_hash"})
    values.update(
        {
            "state": target,
            "paper_order_id": paper_order_id or lifecycle.paper_order_id,
            "reason_codes": reason_codes,
            "updated_at": updated_at,
            "version": lifecycle.version + 1,
        }
    )
    updated = ExecutionLifecycle.model_validate(
        {**values, "payload_hash": canonical_sha256(values)}
    )
    journal.append(updated)
    return updated


def apply_paper_submission(
    lifecycle: ExecutionLifecycle,
    *,
    result: PaperExecutionResult,
    updated_at: UTCDateTime,
    journal: ExecutionJournal,
) -> ExecutionLifecycle:
    if lifecycle.state is not ExecutionState.SUBMITTING:
        raise ValueError("paper submission result requires SUBMITTING state")
    if result.submission_state is PaperSubmissionState.UNKNOWN:
        return transition_execution(
            lifecycle,
            target=ExecutionState.SUBMITTED_UNACKNOWLEDGED,
            updated_at=updated_at,
            journal=journal,
            reason_codes=result.reason_codes,
        )
    if result.order is None:
        raise ValueError("known paper submission state requires an order")
    return transition_execution(
        lifecycle,
        target=_paper_order_state(result.order.status),
        updated_at=updated_at,
        journal=journal,
        paper_order_id=result.order.paper_order_id,
        reason_codes=result.reason_codes,
    )


def apply_paper_reconciliation(
    lifecycle: ExecutionLifecycle,
    *,
    result: PaperReconciliationResult,
    updated_at: UTCDateTime,
    journal: ExecutionJournal,
) -> ExecutionLifecycle:
    if lifecycle.state not in {
        ExecutionState.SUBMITTED_UNACKNOWLEDGED,
        ExecutionState.RECONCILING,
    }:
        raise ValueError("reconciliation requires unknown/reconciling state")
    if result.retry_permitted:
        raise ValueError("unknown submission reconciliation cannot permit blind retry")
    if result.outcome is ReconciliationOutcome.STILL_UNKNOWN:
        target = ExecutionState.RECONCILING
        order_id = None
    elif result.outcome is ReconciliationOutcome.CONFIRMED_ABSENT:
        target = ExecutionState.REJECTED
        order_id = None
    else:
        if result.order is None:
            raise ValueError("confirmed present reconciliation requires order")
        target = _paper_order_state(result.order.status)
        order_id = result.order.paper_order_id
    return transition_execution(
        lifecycle,
        target=target,
        updated_at=updated_at,
        journal=journal,
        paper_order_id=order_id,
        reason_codes=result.reason_codes,
    )


def _paper_order_state(status: PaperOrderStatus) -> ExecutionState:
    return {
        PaperOrderStatus.ACCEPTED: ExecutionState.ACKNOWLEDGED,
        PaperOrderStatus.PARTIALLY_FILLED: ExecutionState.PARTIALLY_FILLED,
        PaperOrderStatus.FILLED: ExecutionState.FILLED,
        PaperOrderStatus.CANCELLED: ExecutionState.CANCELLED,
        PaperOrderStatus.REJECTED: ExecutionState.REJECTED,
    }[status]


def _verify_hash(lifecycle: ExecutionLifecycle) -> None:
    values = lifecycle.model_dump(mode="python", exclude={"payload_hash"})
    if canonical_sha256(values) != lifecycle.payload_hash:
        raise ValueError("execution lifecycle payload hash mismatch")


__all__ = [
    "apply_paper_reconciliation",
    "apply_paper_submission",
    "create_execution",
    "transition_execution",
]
