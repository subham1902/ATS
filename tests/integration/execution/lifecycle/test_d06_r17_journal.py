from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from ats.execution.lifecycle import (
    ExecutionState,
    R17ExecutionJournal,
    create_execution,
    transition_execution,
)
from ats.persistence import connect_postgres
from ats.persistence.postgres import PostgresTransactionManager


def test_r17_journal_recovers_latest_execution_state(postgres_dsn: str, pg_connection) -> None:
    journal = R17ExecutionJournal(
        PostgresTransactionManager(lambda: connect_postgres(postgres_dsn))
    )
    now = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
    execution_id = UUID("78000000-0000-0000-0000-000000000001")
    current = create_execution(
        execution_id=execution_id,
        intent_id=UUID("78000000-0000-0000-0000-000000000002"),
        reservation_id=UUID("78000000-0000-0000-0000-000000000003"),
        autonomy_token_id=UUID("78000000-0000-0000-0000-000000000004"),
        idempotency_key="TEST-EXECUTION-IDEMPOTENCY",
        instrument_id="TEST-OPTION",
        created_at=now,
        journal=journal,
    )
    current = transition_execution(
        current,
        target=ExecutionState.AUTHORIZED,
        updated_at=now + timedelta(seconds=1),
        journal=journal,
    )
    current = transition_execution(
        current,
        target=ExecutionState.RESERVED,
        updated_at=now + timedelta(seconds=1),
        journal=journal,
    )
    assert journal.recover_latest(execution_id) == current
