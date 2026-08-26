from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.contracts.hashing import canonical_sha256
from ats.persistence import IntegrityViolationError, PostgresTransaction
from ats.persistence.types import ReductionAuthorityRecord, StateSnapshot

NOW = datetime(2026, 8, 26, 8, 0, tzinfo=UTC)


def _position(position_id: str = "position-1", *, version: int = 1) -> StateSnapshot:
    payload = {"instrument": "NIFTY-TEST-ONLY", "open_quantity": "100"}
    return StateSnapshot(
        identifier=position_id,
        version=version,
        state="OPEN",
        payload=payload,
        payload_hash=canonical_sha256(payload),
        updated_at=NOW,
    )


def _reduction(
    reduction_id: str = "reduction-1",
    *,
    position_id: str = "position-1",
    position_version: int = 1,
) -> ReductionAuthorityRecord:
    payload = {
        "reduction_id": reduction_id,
        "position_id": position_id,
        "position_version": position_version,
        "position_evidence_hash": "a" * 64,
        "governance_context_id": f"context-{reduction_id}",
        "governance_context_payload_hash": "b" * 64,
        "risk_decision_id": f"risk-{reduction_id}",
        "risk_decision_payload_hash": "c" * 64,
        "risk_direction": "REDUCE",
        "action_kind": "CLOSE_POSITION",
        "system_state_version": 7,
        "effective_constraints_hash": "d" * 64,
        "requested_quantity": "100",
        "exit_reason": "USER_REQUEST",
        "decision_outcome": "ALLOW",
    }
    return ReductionAuthorityRecord(
        reduction_id=reduction_id,
        position_id=position_id,
        position_version=position_version,
        position_evidence_hash="a" * 64,
        governance_context_id=f"context-{reduction_id}",
        governance_context_payload_hash="b" * 64,
        risk_decision_id=f"risk-{reduction_id}",
        risk_decision_payload_hash="c" * 64,
        action_kind="CLOSE_POSITION",
        system_state_version=7,
        effective_constraints_hash="d" * 64,
        requested_quantity=Decimal("100"),
        exit_reason="USER_REQUEST",
        decision_outcome="ALLOW",
        payload=payload,
        payload_hash=canonical_sha256(payload),
        created_at=NOW,
    )


def test_reduction_evidence_round_trips_by_identity_and_position(
    pg_connection: object,
) -> None:
    position = _position()
    record = _reduction()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(position, expected_version=None)
        tx.reduction_authority.append(record)

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert tx.reduction_authority.get(record.reduction_id) == record
        assert tx.reduction_authority.for_position(position.identifier) == (record,)


def test_reduction_evidence_is_append_once_and_conflicts_fail_closed(
    pg_connection: object,
) -> None:
    record = _reduction()
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(_position(), expected_version=None)
        tx.reduction_authority.append(record)

    with pytest.raises(IntegrityViolationError):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.reduction_authority.append(record)

    conflicting_payload = {**record.payload, "exit_reason": "HARD_STOP"}
    conflicting = replace(
        record,
        exit_reason="HARD_STOP",
        payload=conflicting_payload,
        payload_hash=canonical_sha256(conflicting_payload),
    )
    with pytest.raises(IntegrityViolationError):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.reduction_authority.append(conflicting)


def test_reduction_evidence_rejects_invalid_position_and_hash(
    pg_connection: object,
) -> None:
    with pytest.raises(IntegrityViolationError):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.reduction_authority.append(_reduction(position_id="missing-position"))

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(_position(), expected_version=None)
    with pytest.raises(IntegrityViolationError, match="payload hash mismatch"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.reduction_authority.append(replace(_reduction(), payload_hash="e" * 64))


def test_reduction_evidence_allows_sequential_position_versions(
    pg_connection: object,
) -> None:
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(_position(), expected_version=None)
        tx.reduction_authority.append(_reduction())
    current = _position(version=2)
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(current, expected_version=1)
        tx.reduction_authority.append(_reduction("reduction-2", position_version=current.version))
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        records = tx.reduction_authority.for_position(current.identifier)
    assert [record.position_version for record in records] == [1, 2]


def test_reduction_evidence_participates_in_transaction_rollback(
    pg_connection: object,
) -> None:
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(_position(), expected_version=None)

    with pytest.raises(RuntimeError, match="injected failure"):
        with PostgresTransaction(pg_connection, close_connection=False) as tx:
            tx.reduction_authority.append(_reduction())
            raise RuntimeError("injected failure")

    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        assert tx.reduction_authority.get("reduction-1") is None


def test_reduction_evidence_is_database_immutable(pg_connection: object) -> None:
    with PostgresTransaction(pg_connection, close_connection=False) as tx:
        tx.positions.save(_position(), expected_version=None)
        tx.reduction_authority.append(_reduction())

    with pytest.raises(Exception, match="immutable"):
        pg_connection.execute(
            "UPDATE position_reduction_authority_evidence "
            "SET decision_outcome='DENY' WHERE reduction_id='reduction-1'"
        )
    pg_connection.rollback()


def test_entry_evidence_candidate_binding_remains_not_null(pg_connection: object) -> None:
    row = pg_connection.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name='risk_decision_evidence' AND column_name='candidate_id'"
    ).fetchone()
    assert row == ("NO",)
