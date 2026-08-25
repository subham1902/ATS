from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.execution.lifecycle import (
    ExecutionLifecycle,
    ExecutionState,
    apply_paper_reconciliation,
    apply_paper_submission,
    create_execution,
    transition_execution,
)
from ats.execution.paper import (
    ObservedSubmissionState,
    PaperExecutionError,
    PaperSubmissionScenario,
    SubmissionObservation,
    cancel_paper_order,
    reconcile_unknown_submission,
    submit_paper_order,
)
from ats.kernel.types import GateCode, KernelOutcome, KernelResult
from pydantic import ValidationError

from tests.unit.execution.paper.helpers import (
    evaluation_time,
    instrument,
    intent,
    market,
    policy,
)
from tests.unit.market.derivatives.option_chain.helpers import AS_OF

ALLOW = KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))


class MemoryJournal:
    def __init__(self, *, fail: bool = False) -> None:
        self.records: list[ExecutionLifecycle] = []
        self.fail = fail

    def append(self, lifecycle: ExecutionLifecycle) -> None:
        if self.fail:
            raise RuntimeError("simulated journal failure")
        self.records.append(lifecycle)

    def recover_latest(self, execution_id: UUID) -> ExecutionLifecycle | None:
        matches = [item for item in self.records if item.execution_id == execution_id]
        return max(matches, key=lambda item: item.version) if matches else None


def draft(journal: MemoryJournal) -> ExecutionLifecycle:
    order_intent = intent()
    return create_execution(
        execution_id=UUID("77000000-0000-0000-0000-000000000001"),
        intent_id=order_intent.intent_id,
        reservation_id=UUID("77000000-0000-0000-0000-000000000002"),
        autonomy_token_id=order_intent.autonomy_token_id,
        idempotency_key=order_intent.idempotency_key,
        instrument_id=order_intent.instrument_id,
        created_at=AS_OF,
        journal=journal,
    )


def submitting(journal: MemoryJournal) -> ExecutionLifecycle:
    current = draft(journal)
    for state, milliseconds in (
        (ExecutionState.AUTHORIZED, 100),
        (ExecutionState.RESERVED, 200),
        (ExecutionState.SUBMITTING, 300),
    ):
        current = transition_execution(
            current,
            target=state,
            updated_at=AS_OF + timedelta(milliseconds=milliseconds),
            journal=journal,
        )
    return current


def submission(scenario: PaperSubmissionScenario, *, quantity: str = "65"):
    return submit_paper_order(
        intent=intent(quantity=quantity),
        authorization=ALLOW,
        instrument=instrument(),
        market=market(
            scenario=scenario,
            ask_quantity=65,
            rejection_reason=(
                "TEST_ONLY_REJECT" if scenario is PaperSubmissionScenario.REJECT else None
            ),
        ),
        policy=policy(),
        evaluation_time=evaluation_time(),
    )


def test_full_synchronous_partial_fill_lifecycle_is_journaled() -> None:
    journal = MemoryJournal()
    current = submitting(journal)
    updated = apply_paper_submission(
        current,
        result=submission(PaperSubmissionScenario.ACKNOWLEDGE, quantity="130"),
        updated_at=evaluation_time(),
        journal=journal,
    )
    assert updated.state is ExecutionState.PARTIALLY_FILLED
    assert updated.paper_order_id is not None
    assert journal.recover_latest(updated.execution_id) == updated
    assert tuple(item.version for item in journal.records) == (1, 2, 3, 4, 5)


def test_timeout_enters_submitted_unacknowledged_and_cannot_blind_retry() -> None:
    journal = MemoryJournal()
    unknown = apply_paper_submission(
        submitting(journal),
        result=submission(PaperSubmissionScenario.TIMEOUT_UNKNOWN),
        updated_at=evaluation_time(),
        journal=journal,
    )
    assert unknown.state is ExecutionState.SUBMITTED_UNACKNOWLEDGED
    with pytest.raises(ValueError, match="illegal execution transition"):
        transition_execution(
            unknown,
            target=ExecutionState.SUBMITTING,
            updated_at=evaluation_time() + timedelta(seconds=1),
            journal=journal,
        )


def test_unknown_reconciliation_stays_bounded_then_confirms_present() -> None:
    journal = MemoryJournal()
    unknown = apply_paper_submission(
        submitting(journal),
        result=submission(PaperSubmissionScenario.TIMEOUT_UNKNOWN),
        updated_at=evaluation_time(),
        journal=journal,
    )
    still_unknown = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(
            state=ObservedSubmissionState.UNKNOWN,
            order=None,
            observed_at=evaluation_time() + timedelta(seconds=1),
        ),
    )
    reconciling = apply_paper_reconciliation(
        unknown,
        result=still_unknown,
        updated_at=evaluation_time() + timedelta(seconds=1),
        journal=journal,
    )
    assert reconciling.state is ExecutionState.RECONCILING
    known_order = submission(PaperSubmissionScenario.ACKNOWLEDGE).order
    assert known_order is not None
    present = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(
            state=ObservedSubmissionState.PRESENT,
            order=known_order,
            observed_at=evaluation_time() + timedelta(seconds=2),
        ),
    )
    confirmed = apply_paper_reconciliation(
        reconciling,
        result=present,
        updated_at=evaluation_time() + timedelta(seconds=2),
        journal=journal,
    )
    assert confirmed.state is ExecutionState.FILLED


def test_confirmed_absent_is_terminal_rejection_not_retry_permission() -> None:
    journal = MemoryJournal()
    unknown = apply_paper_submission(
        submitting(journal),
        result=submission(PaperSubmissionScenario.TIMEOUT_UNKNOWN),
        updated_at=evaluation_time(),
        journal=journal,
    )
    absent = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(
            state=ObservedSubmissionState.ABSENT,
            order=None,
            observed_at=evaluation_time() + timedelta(seconds=1),
        ),
    )
    rejected = apply_paper_reconciliation(
        unknown,
        result=absent,
        updated_at=evaluation_time() + timedelta(seconds=1),
        journal=journal,
    )
    assert rejected.state is ExecutionState.REJECTED
    with pytest.raises(ValueError):
        transition_execution(
            rejected,
            target=ExecutionState.SUBMITTING,
            updated_at=evaluation_time() + timedelta(seconds=2),
            journal=journal,
        )


def test_delayed_ack_can_cancel_without_duplicate_submit_or_fill() -> None:
    journal = MemoryJournal()
    unknown = apply_paper_submission(
        submitting(journal),
        result=submission(PaperSubmissionScenario.TIMEOUT_UNKNOWN),
        updated_at=evaluation_time(),
        journal=journal,
    )
    accepted = submit_paper_order(
        intent=intent(),
        authorization=ALLOW,
        instrument=instrument(),
        market=market(ask_quantity=64),
        policy=policy(),
        evaluation_time=evaluation_time(),
    ).order
    assert accepted is not None and accepted.filled_quantity == 0
    observed = reconcile_unknown_submission(
        intent=intent(),
        observation=SubmissionObservation(
            state=ObservedSubmissionState.PRESENT,
            order=accepted,
            observed_at=evaluation_time() + timedelta(seconds=1),
        ),
    )
    acknowledged = apply_paper_reconciliation(
        unknown,
        result=observed,
        updated_at=evaluation_time() + timedelta(seconds=1),
        journal=journal,
    )
    cancel_pending = transition_execution(
        acknowledged,
        target=ExecutionState.CANCEL_PENDING,
        updated_at=evaluation_time() + timedelta(seconds=2),
        journal=journal,
    )
    cancelled_order = cancel_paper_order(
        accepted, cancelled_at=evaluation_time() + timedelta(seconds=3)
    )
    cancelled = transition_execution(
        cancel_pending,
        target=ExecutionState.CANCELLED,
        updated_at=evaluation_time() + timedelta(seconds=3),
        journal=journal,
        paper_order_id=cancelled_order.paper_order_id,
        reason_codes=("DELAYED_ACK_ORDER_CANCELLED",),
    )
    assert cancelled.state is ExecutionState.CANCELLED
    assert len({item.version for item in journal.records}) == len(journal.records)


def test_journal_failure_prevents_transition_from_being_returned() -> None:
    good = MemoryJournal()
    current = draft(good)
    failing = MemoryJournal(fail=True)
    with pytest.raises(RuntimeError, match="journal failure"):
        transition_execution(
            current,
            target=ExecutionState.AUTHORIZED,
            updated_at=AS_OF + timedelta(seconds=1),
            journal=failing,
        )
    assert current.state is ExecutionState.DRAFT
    assert current.version == 1


def test_payload_tampering_is_rejected_before_transition() -> None:
    journal = MemoryJournal()
    current = draft(journal).model_copy(update={"instrument_id": "TAMPERED"})
    with pytest.raises(ValueError, match="payload hash"):
        transition_execution(
            current,
            target=ExecutionState.AUTHORIZED,
            updated_at=AS_OF + timedelta(seconds=1),
            journal=journal,
        )


def test_exact_quote_age_boundary_does_not_truncate_milliseconds() -> None:
    exact_policy = policy().model_copy(update={"maximum_quote_age_ms": 1000})
    with pytest.raises(PaperExecutionError, match="stale"):
        submit_paper_order(
            intent=intent(),
            authorization=ALLOW,
            instrument=instrument(),
            market=market(),
            policy=exact_policy,
            evaluation_time=AS_OF + timedelta(milliseconds=1001),
        )


def test_zero_bid_is_rejected_at_strict_market_fact_boundary() -> None:
    with pytest.raises(ValidationError):
        market(bid=Decimal("0"))
