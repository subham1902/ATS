from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from ats.contracts.domain.models import AutonomyToken
from ats.contracts.events import EventType
from ats.contracts.hashing import canonical_sha256
from ats.events import ExternalSubmissionState, OutboxRecord, OutboxState
from ats.persistence import (
    DuplicateAggregateSequenceError,
    DuplicateEventIdError,
    DuplicateIdempotencyKeyError,
    PostgresTransaction,
    TokenConsumeError,
)
from ats.persistence.migrations import apply_migrations
from ats.persistence.types import (
    AuditRecord,
    EvidenceRecord,
    OrderAuthorityRecord,
    StateSnapshot,
)

from tests.unit.contracts.events.fixtures import make_event, uid

NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)


def outbox_for(event_id: str, *, key: str = "intent:one") -> OutboxRecord:
    payload = {"event_id": event_id, "delivery": "at-least-once"}
    return OutboxRecord(
        outbox_id=f"outbox-{key}",
        event_id=event_id,
        topic="ats.events",
        idempotency_key=key,
        payload=payload,
        payload_hash=canonical_sha256(payload),
        state=OutboxState.PENDING,
        external_state=ExternalSubmissionState.NOT_SUBMITTED,
        attempts=0,
        available_at=NOW,
        created_at=NOW,
    )


def token() -> AutonomyToken:
    return AutonomyToken(
        token_id=uid("r17-token"),
        scope="A2_PAPER",
        candidate_id=uid("r17-candidate"),
        policy_id=uid("r17-policy"),
        policy_version=3,
        risk_decision_id=uid("r17-risk"),
        advisory_id=uid("r17-advisory"),
        system_state_version=7,
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        nonce="secret-local-alpha-nonce",
        consumed_at=None,
        payload_hash="a" * 64,
    )


def consume_args(value: AutonomyToken) -> dict[str, object]:
    return {
        "evaluated_at": NOW + timedelta(seconds=1),
        "candidate_id": str(value.candidate_id),
        "policy_id": str(value.policy_id),
        "policy_version": value.policy_version,
        "risk_decision_id": str(value.risk_decision_id),
        "advisory_id": str(value.advisory_id),
        "system_state_version": value.system_state_version,
    }


def test_migration_repeatable_and_schema_complete(pg_connection: object) -> None:
    assert apply_migrations(pg_connection, __import__("pathlib").Path("backend/migrations")) == ()
    cursor = pg_connection.cursor()
    cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    assert cursor.fetchone()[0] >= 11
    pg_connection.rollback()


def test_state_event_and_outbox_commit_as_one_transaction(pg_connection: object) -> None:
    event = make_event(EventType.CANDIDATE_CREATED)
    state_payload = {"phase": "EVIDENCED"}
    state = StateSnapshot(
        "campaign-1", 1, "EVIDENCED", state_payload, canonical_sha256(state_payload), NOW
    )
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.campaigns.save(state, expected_version=None)
        tx.events.append(event)
        tx.outbox.append(outbox_for(str(event.event_id)))

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert tx.campaigns.get("campaign-1") == state
        assert tx.events.by_aggregate(str(event.aggregate_id)) == (event,)
        assert tx.outbox.get_by_idempotency_key("intent:one") is not None


def test_event_uniqueness_and_deterministic_replay(pg_connection: object) -> None:
    first = make_event(EventType.CANDIDATE_CREATED)
    second = make_event(EventType.RISK_EVALUATED).model_copy(
        update={"aggregate_id": first.aggregate_id, "sequence": 2}
    )
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(second)
        tx.events.append(first)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert tx.events.by_aggregate(str(first.aggregate_id)) == (first, second)
        assert tx.events.by_correlation(str(first.correlation_id)) == (first, second)
        assert tx.events.between(first.recorded_at, first.recorded_at + timedelta(seconds=1)) == (
            first,
            second,
        )
        with pytest.raises(DuplicateEventIdError):
            tx.events.append(first)
    pg_connection.rollback()

    duplicate_sequence = make_event(EventType.SUPERVISOR_EVALUATED).model_copy(
        update={"aggregate_id": first.aggregate_id, "sequence": 1}
    )
    with pytest.raises(DuplicateAggregateSequenceError):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.events.append(duplicate_sequence)


@pytest.mark.parametrize("event_type", tuple(EventType))
def test_every_a03_envelope_round_trips_exactly(
    pg_connection: object, event_type: EventType
) -> None:
    event = make_event(event_type)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(event)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert tx.events.by_aggregate(str(event.aggregate_id)) == (event,)


def test_outbox_idempotency_and_claim_lifecycle(pg_connection: object) -> None:
    event = make_event(EventType.ORDER_INTENT_CREATED)
    record = outbox_for(str(event.event_id), key="order-key")
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.events.append(event)
        tx.outbox.append(record)
    with pytest.raises(DuplicateIdempotencyKeyError):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.outbox.append(replace(record, outbox_id="retry"))

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        claimed = tx.outbox.claim_pending(limit=1, claimed_at=NOW + timedelta(seconds=1))
        assert claimed[0].state is OutboxState.DISPATCHING
        assert claimed[0].attempts == 1
        tx.outbox.mark_failed(
            claimed[0].outbox_id,
            error="submission outcome unavailable",
            retry_at=NOW + timedelta(seconds=2),
            unknown=True,
        )
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        retried = tx.outbox.claim_pending(limit=1, claimed_at=NOW + timedelta(seconds=3))
        assert retried[0].attempts == 2
        assert retried[0].external_state is ExternalSubmissionState.UNKNOWN

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert (
            tx.outbox.recover_stale_dispatches(
                claimed_before=NOW + timedelta(seconds=4),
                retry_at=NOW + timedelta(seconds=5),
            )
            == 1
        )
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        crash_retry = tx.outbox.claim_pending(limit=1, claimed_at=NOW + timedelta(seconds=6))
        assert crash_retry[0].idempotency_key == "order-key"
        assert crash_retry[0].attempts == 3


def test_nonce_is_not_stored_and_token_consumes_once(pg_connection: object) -> None:
    value = token()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.tokens.issue(value)
    row = pg_connection.execute(
        "SELECT nonce_hash,token_payload::text FROM autonomy_token_state WHERE token_id=%s",
        (str(value.token_id),),
    ).fetchone()
    assert row[0] != value.nonce
    assert value.nonce not in row[1]
    pg_connection.rollback()

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        consumed = tx.tokens.consume(str(value.token_id), **consume_args(value))
        assert consumed.consumed_at == NOW + timedelta(seconds=1)


def test_caller_supplied_expiry_and_binding_are_authoritative(pg_connection: object) -> None:
    value = token()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.tokens.issue(value)
    with pytest.raises(TokenConsumeError, match="expired, or binding mismatch"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            args = consume_args(value)
            args["evaluated_at"] = value.expires_at
            tx.tokens.consume(str(value.token_id), **args)


def test_authority_evidence_seams_preserve_versions_and_unknown_state(
    pg_connection: object,
) -> None:
    candidate_one = {"candidate": "candidate-1", "score": 1}
    candidate_two = {"candidate": "candidate-1", "score": 2}
    risk_payload = {"decision": "ALLOW"}
    advisory_payload = {"recommendation": "APPROVE"}
    value = token()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.candidates.append(
            EvidenceRecord("candidate-1", 1, candidate_one, canonical_sha256(candidate_one), NOW)
        )
        tx.candidates.append(
            EvidenceRecord(
                "candidate-1",
                2,
                candidate_two,
                canonical_sha256(candidate_two),
                NOW + timedelta(seconds=1),
            )
        )
        tx.risk_decisions.append(
            EvidenceRecord("risk-1", 3, risk_payload, canonical_sha256(risk_payload), NOW),
            candidate_id="candidate-1",
        )
        tx.advisories.append(
            EvidenceRecord(
                "advisory-1", 1, advisory_payload, canonical_sha256(advisory_payload), NOW
            ),
            candidate_id="candidate-1",
            model_version="supervisor-1",
        )
        position_payload = {"quantity": "2"}
        tx.positions.save(
            StateSnapshot(
                "position-1",
                1,
                "OPEN",
                position_payload,
                canonical_sha256(position_payload),
                NOW,
                "UNKNOWN",
            ),
            expected_version=None,
        )
        tx.tokens.issue(value)
        authority_payload = {"intent_id": "intent-1"}
        tx.order_authority.append(
            OrderAuthorityRecord(
                "authority-1",
                "order-idempotency-1",
                str(value.token_id),
                "UNKNOWN",
                authority_payload,
                canonical_sha256(authority_payload),
                NOW,
            )
        )
        audit_payload = {"result": "RECORDED"}
        tx.audit.append(
            AuditRecord(
                "audit-1",
                None,
                "SYSTEM",
                "ats",
                "AUTHORIZE",
                "ORDER_INTENT",
                "intent-1",
                audit_payload,
                canonical_sha256(audit_payload),
                NOW,
                "trace-1",
            )
        )

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        latest = tx.candidates.get("candidate-1")
        assert latest is not None and latest.version == 2
        assert tx.risk_decisions.get("risk-1") is not None
        assert tx.advisories.get("advisory-1") is not None
        position = tx.positions.get("position-1")
        assert position is not None and position.external_state == "UNKNOWN"
        authority = tx.order_authority.get_by_idempotency_key("order-idempotency-1")
        assert authority is not None and authority.external_state == "UNKNOWN"
        assert len(tx.audit.for_object("ORDER_INTENT", "intent-1")) == 1
