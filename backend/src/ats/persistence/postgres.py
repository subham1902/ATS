"""Synchronous PostgreSQL repositories with explicit transaction ownership."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Callable, Sequence
from datetime import datetime
from types import TracebackType
from typing import Any, Literal, cast
from uuid import UUID

from ats.contracts.domain.models import AutonomyToken
from ats.contracts.domain.types import LossState
from ats.contracts.events.models import EventEnvelope, EventPayload, EventType
from ats.contracts.events.registry import EVENT_REGISTRY
from ats.contracts.hashing import canonical_sha256, canonicalize
from ats.events import ExternalSubmissionState, OutboxRecord, OutboxState
from ats.portfolio.persistence import (
    CapitalReservation,
    CapitalReservationRequest,
    CapitalReservationResult,
    CapitalReservationState,
    PortfolioCapitalAccount,
)

from .errors import (
    CapitalAccountNotFoundError,
    CapitalReservationStateError,
    DuplicateAggregateSequenceError,
    DuplicateCapitalReservationError,
    DuplicateEventIdError,
    DuplicateIdempotencyKeyError,
    InsufficientCapitalError,
    IntegrityViolationError,
    TokenConsumeError,
    TransactionConflictError,
    UnsupportedStoredEventError,
)
from .protocols import Connection, Cursor
from .types import AuditRecord, EvidenceRecord, OrderAuthorityRecord, StateSnapshot, StoredToken


def _json(value: object) -> str:
    return json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        loaded = json.loads(value)
    else:
        loaded = value
    if not isinstance(loaded, dict):
        raise IntegrityViolationError("stored JSON must be an object")
    return cast(dict[str, Any], loaded)


def _constraint(exc: BaseException) -> str | None:
    diag = getattr(exc, "diag", None)
    return cast(str | None, getattr(diag, "constraint_name", None))


def _translate_write_error(exc: BaseException) -> BaseException:
    constraint = _constraint(exc)
    if constraint == "event_records_pkey":
        return DuplicateEventIdError("duplicate event_id")
    if constraint == "event_records_aggregate_id_sequence_key":
        return DuplicateAggregateSequenceError("duplicate aggregate sequence")
    if constraint in {
        "outbox_records_idempotency_key_key",
        "order_authority_evidence_idempotency_key_key",
    }:
        return DuplicateIdempotencyKeyError("duplicate idempotency key")
    if constraint in {"capital_reservation_pkey", "capital_reservation_candidate_key"}:
        return DuplicateCapitalReservationError("duplicate capital reservation")
    if getattr(exc, "sqlstate", None) in {"40001", "40P01"}:
        return TransactionConflictError("transaction serialization conflict")
    return exc


def _execute(cursor: Cursor, query: str, params: Sequence[object]) -> None:
    try:
        cursor.execute(query, params)
    except BaseException as exc:
        translated = _translate_write_error(exc)
        if translated is exc:
            raise
        raise translated from exc


_EVENT_COLUMNS = (
    "event_id,event_type,event_version,aggregate_id,sequence,causation_id,correlation_id,"
    "occurred_at,recorded_at,producer,schema_version,payload,payload_hash,envelope,trace_id"
)


class PostgresEventStore:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, event: EventEnvelope) -> None:
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                """INSERT INTO event_records (
                    event_id,event_type,event_version,aggregate_id,sequence,causation_id,
                    correlation_id,occurred_at,recorded_at,producer,schema_version,payload,
                    payload_hash,envelope,trace_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s)""",
                (
                    str(event.event_id),
                    event.event_type.value,
                    event.event_version,
                    str(event.aggregate_id),
                    event.sequence,
                    None if event.causation_id is None else str(event.causation_id),
                    str(event.correlation_id),
                    event.occurred_at,
                    event.recorded_at,
                    event.producer,
                    event.schema_version,
                    _json(event.payload),
                    event.payload_hash,
                    _json(event),
                    str(event.trace_id),
                ),
            )
        finally:
            cursor.close()

    def _read(self, query: str, params: Sequence[object]) -> tuple[EventEnvelope, ...]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        result: list[EventEnvelope] = []
        for row in rows:
            event_type_text, version = str(row[1]), int(row[2])
            try:
                event_type = EventType(event_type_text)
                entry = EVENT_REGISTRY[(event_type, version)]
            except (KeyError, ValueError) as exc:
                raise UnsupportedStoredEventError(
                    f"unsupported stored event {event_type_text} version {version}"
                ) from exc
            payload_object = _mapping(row[11])
            if canonical_sha256(payload_object) != str(row[12]):
                raise IntegrityViolationError("stored event payload hash mismatch")
            if row[10] != "1.0":
                raise IntegrityViolationError("stored event schema version is invalid")
            try:
                payload = cast(
                    EventPayload, entry.payload_model.model_validate_json(_json(payload_object))
                )
                reconstructed = EventEnvelope(
                    event_id=UUID(str(row[0])),
                    event_type=event_type,
                    event_version=version,
                    aggregate_id=UUID(str(row[3])),
                    sequence=int(row[4]),
                    causation_id=None if row[5] is None else UUID(str(row[5])),
                    correlation_id=UUID(str(row[6])),
                    occurred_at=cast(datetime, row[7]),
                    recorded_at=cast(datetime, row[8]),
                    producer=str(row[9]),
                    schema_version="1.0",
                    payload=payload,
                    payload_hash=str(row[12]),
                    trace_id=str(row[14]),
                )
            except ValueError as exc:
                raise IntegrityViolationError("stored event envelope is invalid") from exc
            if canonicalize(reconstructed) != _mapping(row[13]):
                raise IntegrityViolationError("stored envelope does not match event columns")
            result.append(reconstructed)
        return tuple(result)

    def by_aggregate(self, aggregate_id: str) -> tuple[EventEnvelope, ...]:
        return self._read(
            f"SELECT {_EVENT_COLUMNS} FROM event_records WHERE aggregate_id=%s ORDER BY sequence",
            (aggregate_id,),
        )

    def by_correlation(self, correlation_id: str) -> tuple[EventEnvelope, ...]:
        return self._read(
            f"SELECT {_EVENT_COLUMNS} FROM event_records "
            "WHERE correlation_id=%s ORDER BY recorded_at,event_id",
            (correlation_id,),
        )

    def between(self, start: datetime, end: datetime) -> tuple[EventEnvelope, ...]:
        return self._read(
            f"SELECT {_EVENT_COLUMNS} FROM event_records "
            "WHERE recorded_at >= %s AND recorded_at < %s ORDER BY recorded_at,event_id",
            (start, end),
        )


def _outbox(row: Sequence[Any]) -> OutboxRecord:
    return OutboxRecord(
        outbox_id=str(row[0]),
        event_id=str(row[1]),
        topic=str(row[2]),
        idempotency_key=str(row[3]),
        payload=_mapping(row[4]),
        payload_hash=str(row[5]),
        state=OutboxState(str(row[6])),
        external_state=ExternalSubmissionState(str(row[7])),
        attempts=int(row[8]),
        available_at=cast(datetime, row[9]),
        created_at=cast(datetime, row[10]),
        locked_at=cast(datetime | None, row[11]),
        dispatched_at=cast(datetime | None, row[12]),
        last_error=cast(str | None, row[13]),
    )


_OUTBOX_COLUMNS = (
    "outbox_id,event_id,topic,idempotency_key,payload,payload_hash,state,external_state,"
    "attempts,available_at,created_at,locked_at,dispatched_at,last_error"
)
_OUTBOX_QUALIFIED_COLUMNS = ",".join(f"o.{column}" for column in _OUTBOX_COLUMNS.split(","))


class PostgresOutboxRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, record: OutboxRecord) -> None:
        if canonical_sha256(record.payload) != record.payload_hash:
            raise IntegrityViolationError("outbox payload hash mismatch")
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                "INSERT INTO outbox_records (outbox_id,event_id,topic,idempotency_key,payload,"
                "payload_hash,state,external_state,attempts,available_at,created_at,locked_at,"
                "dispatched_at,last_error) VALUES ("
                "%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    record.outbox_id,
                    record.event_id,
                    record.topic,
                    record.idempotency_key,
                    _json(record.payload),
                    record.payload_hash,
                    record.state.value,
                    record.external_state.value,
                    record.attempts,
                    record.available_at,
                    record.created_at,
                    record.locked_at,
                    record.dispatched_at,
                    record.last_error,
                ),
            )
        finally:
            cursor.close()

    def get_by_idempotency_key(self, key: str) -> OutboxRecord | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_OUTBOX_COLUMNS} FROM outbox_records WHERE idempotency_key=%s", (key,)
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        return None if row is None else _outbox(row)

    def claim_pending(self, *, limit: int, claimed_at: datetime) -> tuple[OutboxRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"""WITH selected AS (
                    SELECT outbox_id FROM outbox_records
                    WHERE state IN ('PENDING','FAILED') AND available_at <= %s
                    ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT %s
                ) UPDATE outbox_records o SET state='DISPATCHING',locked_at=%s,
                    attempts=o.attempts+1 FROM selected
                    WHERE o.outbox_id=selected.outbox_id
                    RETURNING {_OUTBOX_QUALIFIED_COLUMNS}""",
                (claimed_at, limit, claimed_at),
            )
            return tuple(_outbox(row) for row in cursor.fetchall())
        finally:
            cursor.close()

    def mark_dispatched(self, outbox_id: str, dispatched_at: datetime) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "UPDATE outbox_records SET state='DISPATCHED',external_state='CONFIRMED',"
                "dispatched_at=%s,locked_at=NULL,last_error=NULL WHERE outbox_id=%s",
                (dispatched_at, outbox_id),
            )
        finally:
            cursor.close()

    def mark_failed(self, outbox_id: str, *, error: str, retry_at: datetime, unknown: bool) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "UPDATE outbox_records SET state='FAILED',external_state=%s,available_at=%s,"
                "locked_at=NULL,last_error=%s WHERE outbox_id=%s",
                ("UNKNOWN" if unknown else "NOT_SUBMITTED", retry_at, error, outbox_id),
            )
        finally:
            cursor.close()

    def recover_stale_dispatches(self, *, claimed_before: datetime, retry_at: datetime) -> int:
        """Make committed-but-unacknowledged claims retryable without claiming delivery."""

        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "UPDATE outbox_records SET state='FAILED',external_state='UNKNOWN',"
                "available_at=%s,locked_at=NULL,last_error='stale dispatch recovered' "
                "WHERE state='DISPATCHING' AND locked_at < %s RETURNING outbox_id",
                (retry_at, claimed_before),
            )
            return len(cursor.fetchall())
        finally:
            cursor.close()


def _token(row: Sequence[Any]) -> StoredToken:
    return StoredToken(
        token_id=str(row[0]),
        candidate_id=str(row[1]),
        policy_id=str(row[2]),
        policy_version=int(row[3]),
        risk_decision_id=str(row[4]),
        advisory_id=str(row[5]),
        system_state_version=int(row[6]),
        scope=str(row[7]),
        issued_at=cast(datetime, row[8]),
        expires_at=cast(datetime, row[9]),
        consumed_at=cast(datetime | None, row[10]),
        payload_hash=str(row[11]),
    )


_TOKEN_COLUMNS = (
    "token_id,candidate_id,policy_id,policy_version,risk_decision_id,advisory_id,"
    "system_state_version,scope,issued_at,expires_at,consumed_at,payload_hash"
)


class PostgresTokenRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def issue(self, token: AutonomyToken) -> None:
        nonce_hash = hashlib.pbkdf2_hmac(
            "sha256", token.nonce.encode(), str(token.token_id).encode(), 120_000
        ).hex()
        safe_payload = token.model_dump(mode="json")
        safe_payload.pop("nonce")
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                """INSERT INTO autonomy_token_state (
                    token_id,candidate_id,policy_id,policy_version,risk_decision_id,advisory_id,
                    system_state_version,scope,issued_at,expires_at,consumed_at,nonce_hash,
                    payload_hash,token_payload
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    str(token.token_id),
                    str(token.candidate_id),
                    str(token.policy_id),
                    token.policy_version,
                    str(token.risk_decision_id),
                    str(token.advisory_id),
                    token.system_state_version,
                    token.scope,
                    token.issued_at,
                    token.expires_at,
                    token.consumed_at,
                    nonce_hash,
                    token.payload_hash,
                    _json(safe_payload),
                ),
            )
        finally:
            cursor.close()

    def get(self, token_id: str) -> StoredToken | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_TOKEN_COLUMNS} FROM autonomy_token_state WHERE token_id=%s", (token_id,)
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        return None if row is None else _token(row)

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
    ) -> StoredToken:
        if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"""UPDATE autonomy_token_state SET consumed_at=%s
                    WHERE token_id=%s AND consumed_at IS NULL AND expires_at > %s
                      AND candidate_id=%s AND policy_id=%s AND policy_version=%s
                      AND risk_decision_id=%s AND advisory_id=%s AND system_state_version=%s
                    RETURNING {_TOKEN_COLUMNS}""",
                (
                    evaluated_at,
                    token_id,
                    evaluated_at,
                    candidate_id,
                    policy_id,
                    policy_version,
                    risk_decision_id,
                    advisory_id,
                    system_state_version,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise TokenConsumeError("token absent, consumed, expired, or binding mismatch")
            return _token(row)
        finally:
            cursor.close()


class _EvidenceRepository:
    def __init__(self, connection: Connection, table: str, id_column: str) -> None:
        self._connection = connection
        self._table = table
        self._id_column = id_column

    def _get(self, identifier: str) -> EvidenceRecord | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {self._id_column},version,payload,payload_hash,recorded_at "
                f"FROM {self._table} WHERE {self._id_column}=%s "
                "ORDER BY version DESC LIMIT 1",
                (identifier,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        payload = _mapping(row[2])
        if canonical_sha256(payload) != str(row[3]):
            raise IntegrityViolationError(f"{self._table} payload hash mismatch")
        return EvidenceRecord(
            str(row[0]), int(row[1]), payload, str(row[3]), cast(datetime, row[4])
        )


class PostgresCandidateEvidenceRepository(_EvidenceRepository):
    def __init__(self, connection: Connection) -> None:
        super().__init__(connection, "candidate_evidence", "candidate_id")

    def append(self, evidence: EvidenceRecord) -> None:
        _append_evidence(self._connection, self._table, self._id_column, evidence, ())

    def get(self, candidate_id: str) -> EvidenceRecord | None:
        return self._get(candidate_id)


class PostgresRiskDecisionEvidenceRepository(_EvidenceRepository):
    def __init__(self, connection: Connection) -> None:
        super().__init__(connection, "risk_decision_evidence", "risk_decision_id")

    def append(self, evidence: EvidenceRecord, *, candidate_id: str) -> None:
        _append_evidence(
            self._connection,
            self._table,
            self._id_column,
            evidence,
            (("candidate_id", candidate_id), ("policy_version", evidence.version)),
        )

    def get(self, risk_decision_id: str) -> EvidenceRecord | None:
        return self._get(risk_decision_id)


class PostgresAdvisoryEvidenceRepository(_EvidenceRepository):
    def __init__(self, connection: Connection) -> None:
        super().__init__(connection, "advisory_evidence", "advisory_id")

    def append(self, evidence: EvidenceRecord, *, candidate_id: str, model_version: str) -> None:
        _append_evidence(
            self._connection,
            self._table,
            self._id_column,
            evidence,
            (("candidate_id", candidate_id), ("model_version", model_version)),
        )

    def get(self, advisory_id: str) -> EvidenceRecord | None:
        return self._get(advisory_id)


def _append_evidence(
    connection: Connection,
    table: str,
    id_column: str,
    evidence: EvidenceRecord,
    extra: Sequence[tuple[str, object]],
) -> None:
    if canonical_sha256(evidence.payload) != evidence.payload_hash:
        raise IntegrityViolationError(f"{table} payload hash mismatch")
    columns = [
        id_column,
        "version",
        *(name for name, _ in extra),
        "payload",
        "payload_hash",
        "recorded_at",
    ]
    values: list[object] = [
        evidence.identifier,
        evidence.version,
        *(value for _, value in extra),
        _json(evidence.payload),
        evidence.payload_hash,
        evidence.recorded_at,
    ]
    placeholders = ["%s"] * len(columns)
    placeholders[-3] = "%s::jsonb"
    cursor = connection.cursor()
    try:
        _execute(
            cursor,
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(placeholders)})",
            values,
        )
    finally:
        cursor.close()


class _StateRepository:
    def __init__(self, connection: Connection, table: str, id_column: str, external: bool) -> None:
        self._connection = connection
        self._table = table
        self._id_column = id_column
        self._external = external

    def save(self, snapshot: StateSnapshot, *, expected_version: int | None) -> None:
        if canonical_sha256(snapshot.payload) != snapshot.payload_hash:
            raise IntegrityViolationError(f"{self._table} payload hash mismatch")
        cursor = self._connection.cursor()
        try:
            if expected_version is None:
                columns = f"{self._id_column},version,state,payload,payload_hash,updated_at"
                params: tuple[object, ...] = (
                    snapshot.identifier,
                    snapshot.version,
                    snapshot.state,
                    _json(snapshot.payload),
                    snapshot.payload_hash,
                    snapshot.updated_at,
                )
                if self._external:
                    columns += ",external_state"
                    params += (snapshot.external_state or "NOT_SUBMITTED",)
                _execute(
                    cursor,
                    f"INSERT INTO {self._table} ({columns}) VALUES (%s,%s,%s,%s::jsonb,%s,%s"
                    + (",%s)" if self._external else ")"),
                    params,
                )
            else:
                external_sql = ",external_state=%s" if self._external else ""
                params_list: list[object] = [
                    snapshot.version,
                    snapshot.state,
                    _json(snapshot.payload),
                    snapshot.payload_hash,
                    snapshot.updated_at,
                ]
                if self._external:
                    params_list.append(snapshot.external_state or "NOT_SUBMITTED")
                params_list.extend([snapshot.identifier, expected_version])
                cursor.execute(
                    f"UPDATE {self._table} SET version=%s,state=%s,payload=%s::jsonb,"
                    f"payload_hash=%s,updated_at=%s{external_sql} "
                    f"WHERE {self._id_column}=%s AND version=%s RETURNING version",
                    params_list,
                )
                if cursor.fetchone() is None:
                    raise TransactionConflictError("state version conflict")
        finally:
            cursor.close()

    def get(self, identifier: str) -> StateSnapshot | None:
        external_column = ",external_state" if self._external else ""
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {self._id_column},version,state,payload,payload_hash,"
                f"updated_at{external_column} FROM {self._table} "
                f"WHERE {self._id_column}=%s",
                (identifier,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        payload = _mapping(row[3])
        if canonical_sha256(payload) != str(row[4]):
            raise IntegrityViolationError(f"{self._table} payload hash mismatch")
        return StateSnapshot(
            str(row[0]),
            int(row[1]),
            str(row[2]),
            payload,
            str(row[4]),
            cast(datetime, row[5]),
            None if not self._external else str(row[6]),
        )


class PostgresCampaignStateRepository(_StateRepository):
    def __init__(self, connection: Connection) -> None:
        super().__init__(connection, "campaign_state", "campaign_id", False)


class PostgresPositionRepository(_StateRepository):
    def __init__(self, connection: Connection) -> None:
        super().__init__(connection, "position_state", "position_id", True)


_CAPITAL_COLUMNS = (
    "portfolio_id,version,total_capital,deployable_capital,reserved_capital,used_capital,"
    "realized_pnl,unrealized_pnl,daily_loss,maximum_drawdown,loss_state,updated_at"
)
_RESERVATION_COLUMNS = (
    "reservation_id,portfolio_id,campaign_id,candidate_id,instrument_id,amount,state,"
    "created_at,updated_at"
)


def _capital_account(row: Sequence[Any]) -> PortfolioCapitalAccount:
    deployable = row[3]
    reserved = row[4]
    used = row[5]
    return PortfolioCapitalAccount(
        portfolio_id=UUID(str(row[0])),
        version=int(row[1]),
        total_capital=row[2],
        deployable_capital=deployable,
        reserved_capital=reserved,
        used_capital=used,
        available_capital=deployable - reserved - used,
        realized_pnl=row[6],
        unrealized_pnl=row[7],
        daily_loss=row[8],
        maximum_drawdown=row[9],
        loss_state=LossState(str(row[10])),
        updated_at=cast(datetime, row[11]),
    )


def _capital_reservation(row: Sequence[Any]) -> CapitalReservation:
    return CapitalReservation(
        reservation_id=UUID(str(row[0])),
        portfolio_id=UUID(str(row[1])),
        campaign_id=UUID(str(row[2])),
        candidate_id=UUID(str(row[3])),
        instrument_id=str(row[4]),
        amount=row[5],
        state=CapitalReservationState(str(row[6])),
        created_at=cast(datetime, row[7]),
        updated_at=cast(datetime, row[8]),
    )


class PostgresCapitalRepository:
    """Atomic capital reservation through a locked authoritative account row."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def create_account(self, account: PortfolioCapitalAccount) -> None:
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                f"INSERT INTO portfolio_capital_account ({_CAPITAL_COLUMNS}) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    str(account.portfolio_id),
                    account.version,
                    account.total_capital,
                    account.deployable_capital,
                    account.reserved_capital,
                    account.used_capital,
                    account.realized_pnl,
                    account.unrealized_pnl,
                    account.daily_loss,
                    account.maximum_drawdown,
                    account.loss_state.value,
                    account.updated_at,
                ),
            )
        finally:
            cursor.close()

    def get_account(self, portfolio_id: UUID) -> PortfolioCapitalAccount | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_CAPITAL_COLUMNS} FROM portfolio_capital_account "
                "WHERE portfolio_id=%s",
                (str(portfolio_id),),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        return None if row is None else _capital_account(row)

    def get_reservation(self, reservation_id: UUID) -> CapitalReservation | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM capital_reservation "
                "WHERE reservation_id=%s",
                (str(reservation_id),),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        return None if row is None else _capital_reservation(row)

    def reserve(self, request: CapitalReservationRequest) -> CapitalReservationResult:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_CAPITAL_COLUMNS} FROM portfolio_capital_account "
                "WHERE portfolio_id=%s FOR UPDATE",
                (str(request.portfolio_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise CapitalAccountNotFoundError("portfolio capital account does not exist")
            account = _capital_account(row)
            if account.loss_state in (LossState.COOLDOWN, LossState.HALTED):
                raise CapitalReservationStateError("loss state blocks new capital reservation")
            if request.amount > account.available_capital:
                raise InsufficientCapitalError("requested capital exceeds current availability")
            _execute(
                cursor,
                f"INSERT INTO capital_reservation ({_RESERVATION_COLUMNS}) "
                "VALUES (%s,%s,%s,%s,%s,%s,'RESERVED',%s,%s)",
                (
                    str(request.reservation_id),
                    str(request.portfolio_id),
                    str(request.campaign_id),
                    str(request.candidate_id),
                    request.instrument_id,
                    request.amount,
                    request.requested_at,
                    request.requested_at,
                ),
            )
            cursor.execute(
                "UPDATE portfolio_capital_account SET reserved_capital=reserved_capital+%s,"
                "version=version+1,updated_at=GREATEST(updated_at,%s) WHERE portfolio_id=%s "
                f"RETURNING {_CAPITAL_COLUMNS}",
                (request.amount, request.requested_at, str(request.portfolio_id)),
            )
            updated = cursor.fetchone()
            assert updated is not None
            reservation = CapitalReservation(
                reservation_id=request.reservation_id,
                portfolio_id=request.portfolio_id,
                campaign_id=request.campaign_id,
                candidate_id=request.candidate_id,
                instrument_id=request.instrument_id,
                amount=request.amount,
                state=CapitalReservationState.RESERVED,
                created_at=request.requested_at,
                updated_at=request.requested_at,
            )
            return CapitalReservationResult(
                reservation=reservation, account=_capital_account(updated)
            )
        finally:
            cursor.close()

    def commit(self, reservation_id: UUID, *, updated_at: datetime) -> CapitalReservationResult:
        return self._transition(
            reservation_id,
            updated_at=updated_at,
            expected=CapitalReservationState.RESERVED,
            target=CapitalReservationState.COMMITTED,
        )

    def release(self, reservation_id: UUID, *, updated_at: datetime) -> CapitalReservationResult:
        return self._transition(
            reservation_id,
            updated_at=updated_at,
            expected=None,
            target=CapitalReservationState.RELEASED,
        )

    def _transition(
        self,
        reservation_id: UUID,
        *,
        updated_at: datetime,
        expected: CapitalReservationState | None,
        target: CapitalReservationState,
    ) -> CapitalReservationResult:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM capital_reservation "
                "WHERE reservation_id=%s FOR UPDATE",
                (str(reservation_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise CapitalReservationStateError("capital reservation does not exist")
            reservation = _capital_reservation(row)
            if reservation.state is CapitalReservationState.RELEASED:
                raise CapitalReservationStateError("capital reservation is already released")
            if expected is not None and reservation.state is not expected:
                raise CapitalReservationStateError(
                    "capital reservation state transition is invalid"
                )
            if updated_at < reservation.updated_at:
                raise CapitalReservationStateError("reservation update timestamp moved backwards")
            cursor.execute(
                f"SELECT {_CAPITAL_COLUMNS} FROM portfolio_capital_account "
                "WHERE portfolio_id=%s FOR UPDATE",
                (str(reservation.portfolio_id),),
            )
            if cursor.fetchone() is None:
                raise CapitalAccountNotFoundError("portfolio capital account does not exist")
            if target is CapitalReservationState.COMMITTED:
                capital_sql = (
                    "reserved_capital=reserved_capital-%s,used_capital=used_capital+%s"
                )
                capital_params: tuple[object, ...] = (reservation.amount, reservation.amount)
            elif reservation.state is CapitalReservationState.RESERVED:
                capital_sql = "reserved_capital=reserved_capital-%s"
                capital_params = (reservation.amount,)
            else:
                capital_sql = "used_capital=used_capital-%s"
                capital_params = (reservation.amount,)
            cursor.execute(
                f"UPDATE portfolio_capital_account SET {capital_sql},version=version+1,"
                f"updated_at=%s WHERE portfolio_id=%s RETURNING {_CAPITAL_COLUMNS}",
                (*capital_params, updated_at, str(reservation.portfolio_id)),
            )
            updated_account = cursor.fetchone()
            assert updated_account is not None
            cursor.execute(
                "UPDATE capital_reservation SET state=%s,updated_at=%s "
                "WHERE reservation_id=%s RETURNING " + _RESERVATION_COLUMNS,
                (target.value, updated_at, str(reservation_id)),
            )
            updated_reservation = cursor.fetchone()
            assert updated_reservation is not None
            return CapitalReservationResult(
                reservation=_capital_reservation(updated_reservation),
                account=_capital_account(updated_account),
            )
        finally:
            cursor.close()


class PostgresOrderAuthorityRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, record: OrderAuthorityRecord) -> None:
        if canonical_sha256(record.payload) != record.payload_hash:
            raise IntegrityViolationError("order authority payload hash mismatch")
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                "INSERT INTO order_authority_evidence "
                "(authority_id,idempotency_key,token_id,external_state,payload,"
                "payload_hash,recorded_at) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)",
                (
                    record.authority_id,
                    record.idempotency_key,
                    record.token_id,
                    record.external_state,
                    _json(record.payload),
                    record.payload_hash,
                    record.recorded_at,
                ),
            )
        finally:
            cursor.close()

    def get_by_idempotency_key(self, key: str) -> OrderAuthorityRecord | None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "SELECT authority_id,idempotency_key,token_id,external_state,payload,"
                "payload_hash,recorded_at FROM order_authority_evidence "
                "WHERE idempotency_key=%s",
                (key,),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        payload = _mapping(row[4])
        if canonical_sha256(payload) != str(row[5]):
            raise IntegrityViolationError("order authority payload hash mismatch")
        return OrderAuthorityRecord(
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            payload,
            str(row[5]),
            cast(datetime, row[6]),
        )


class PostgresAuditRepository:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, record: AuditRecord) -> None:
        cursor = self._connection.cursor()
        try:
            _execute(
                cursor,
                "INSERT INTO audit_records "
                "(audit_id,event_id,actor_type,actor_id,action,object_type,object_id,"
                "payload,record_hash,occurred_at,trace_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                (
                    record.audit_id,
                    record.event_id,
                    record.actor_type,
                    record.actor_id,
                    record.action,
                    record.object_type,
                    record.object_id,
                    _json(record.payload),
                    record.record_hash,
                    record.occurred_at,
                    record.trace_id,
                ),
            )
        finally:
            cursor.close()

    def for_object(self, object_type: str, object_id: str) -> tuple[AuditRecord, ...]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "SELECT audit_id,event_id,actor_type,actor_id,action,object_type,object_id,"
                "payload,record_hash,occurred_at,trace_id FROM audit_records "
                "WHERE object_type=%s AND object_id=%s ORDER BY occurred_at,audit_id",
                (object_type, object_id),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return tuple(
            AuditRecord(
                str(r[0]),
                None if r[1] is None else str(r[1]),
                str(r[2]),
                str(r[3]),
                str(r[4]),
                str(r[5]),
                str(r[6]),
                _mapping(r[7]),
                str(r[8]),
                cast(datetime, r[9]),
                str(r[10]),
            )
            for r in rows
        )


class PostgresTransaction:
    """One explicit unit of work; repositories never commit independently."""

    def __init__(self, connection: Connection, *, close_connection: bool = True) -> None:
        self._connection = connection
        self._close_connection = close_connection
        self.events = PostgresEventStore(connection)
        self.outbox = PostgresOutboxRepository(connection)
        self.tokens = PostgresTokenRepository(connection)
        self.campaigns = PostgresCampaignStateRepository(connection)
        self.positions = PostgresPositionRepository(connection)
        self.capital = PostgresCapitalRepository(connection)
        self.candidates = PostgresCandidateEvidenceRepository(connection)
        self.risk_decisions = PostgresRiskDecisionEvidenceRepository(connection)
        self.advisories = PostgresAdvisoryEvidenceRepository(connection)
        self.order_authority = PostgresOrderAuthorityRepository(connection)
        self.audit = PostgresAuditRepository(connection)

    def __enter__(self) -> PostgresTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            if exc_type is None:
                try:
                    self._connection.commit()
                except BaseException as exc:
                    self._connection.rollback()
                    translated = _translate_write_error(exc)
                    if translated is exc:
                        raise
                    raise translated from exc
            else:
                self._connection.rollback()
        finally:
            if self._close_connection:
                self._connection.close()
        return False


class PostgresTransactionManager:
    def __init__(self, connection_factory: Callable[[], Connection]) -> None:
        self._connection_factory = connection_factory

    def transaction(self) -> PostgresTransaction:
        return PostgresTransaction(self._connection_factory())


def connect_postgres(dsn: str) -> Connection:
    """Connect through optional Psycopg 3; the DSN is supplied only by the caller."""

    try:
        psycopg = importlib.import_module("psycopg")
    except ImportError as exc:
        raise RuntimeError("connect_postgres requires psycopg 3") from exc
    return cast(Connection, psycopg.connect(dsn))


__all__ = [
    "PostgresCapitalRepository",
    "PostgresEventStore",
    "PostgresOutboxRepository",
    "PostgresTokenRepository",
    "PostgresTransaction",
    "PostgresTransactionManager",
    "connect_postgres",
]
