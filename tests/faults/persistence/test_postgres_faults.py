from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from ats.contracts.events import EventType
from ats.contracts.hashing import canonical_sha256
from ats.persistence import (
    IntegrityViolationError,
    PostgresTransaction,
    TokenConsumeError,
    TransactionConflictError,
    UnsupportedStoredEventError,
)
from ats.persistence.types import StateSnapshot

from tests.integration.persistence.test_postgres_store import NOW, consume_args, token
from tests.unit.contracts.events.fixtures import make_event


def test_rollback_after_event_before_outbox(pg_connection: object) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with pytest.raises(RuntimeError, match="crash"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.events.append(event)
            raise RuntimeError("simulated crash before outbox")
    assert pg_connection.execute("SELECT count(*) FROM event_records").fetchone()[0] == 0
    pg_connection.rollback()


def test_rollback_after_state_before_event(pg_connection: object) -> None:
    payload = {"state": "MUTATED"}
    snapshot = StateSnapshot(
        "campaign-fault", 1, "MUTATED", payload, canonical_sha256(payload), NOW
    )
    with pytest.raises(RuntimeError, match="crash"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.campaigns.save(snapshot, expected_version=None)
            raise RuntimeError("simulated crash before event")
    assert pg_connection.execute("SELECT count(*) FROM campaign_state").fetchone()[0] == 0
    pg_connection.rollback()


def test_concurrent_token_consumption_has_one_winner(
    postgres_dsn: str, pg_connection: object
) -> None:
    import psycopg

    value = token()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.tokens.issue(value)

    def attempt() -> str:
        connection = psycopg.connect(postgres_dsn)
        try:
            with PostgresTransaction(connection) as tx:
                tx.tokens.consume(str(value.token_id), **consume_args(value))
            return "consumed"
        except TokenConsumeError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(lambda _: attempt(), range(8)))
    assert results.count("consumed") == 1
    assert results.count("rejected") == 7


def test_malformed_stored_payload_hash_fails_closed(pg_connection: object) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(event)
    pg_connection.execute("ALTER TABLE event_records DISABLE TRIGGER USER")
    pg_connection.execute(
        "UPDATE event_records SET payload_hash=%s WHERE event_id=%s",
        ("f" * 64, str(event.event_id)),
    )
    pg_connection.execute("ALTER TABLE event_records ENABLE TRIGGER USER")
    pg_connection.commit()
    with pytest.raises(IntegrityViolationError, match="hash mismatch"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.events.by_aggregate(str(event.aggregate_id))


def test_unknown_event_version_fails_closed(pg_connection: object) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(event)
    pg_connection.execute("ALTER TABLE event_records DISABLE TRIGGER USER")
    pg_connection.execute(
        "UPDATE event_records SET event_version=999 WHERE event_id=%s", (str(event.event_id),)
    )
    pg_connection.execute("ALTER TABLE event_records ENABLE TRIGGER USER")
    pg_connection.commit()
    with pytest.raises(UnsupportedStoredEventError, match="version 999"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.events.by_aggregate(str(event.aggregate_id))


def test_event_history_rejects_update_and_delete(pg_connection: object) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(event)
    with pytest.raises(Exception, match="immutable"):
        pg_connection.execute(
            "UPDATE event_records SET producer='changed' WHERE event_id=%s", (str(event.event_id),)
        )
    pg_connection.rollback()
    with pytest.raises(Exception, match="immutable"):
        pg_connection.execute("DELETE FROM event_records WHERE event_id=%s", (str(event.event_id),))
    pg_connection.rollback()


def test_optimistic_transaction_conflict_is_deterministic(pg_connection: object) -> None:
    initial_payload = {"version": 1}
    initial = StateSnapshot(
        "campaign-conflict", 1, "OPEN", initial_payload, canonical_sha256(initial_payload), NOW
    )
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.campaigns.save(initial, expected_version=None)
    next_payload = {"version": 2}
    stale = StateSnapshot(
        "campaign-conflict",
        2,
        "OPEN",
        next_payload,
        canonical_sha256(next_payload),
        NOW + timedelta(seconds=1),
    )
    with pytest.raises(TransactionConflictError, match="version conflict"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.campaigns.save(stale, expected_version=0)
