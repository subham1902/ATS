from __future__ import annotations

from dataclasses import replace
from datetime import time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts import canonical_sha256
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import ExitReason
from ats.contracts.governance.types import ActionKind, RiskDirection
from ats.kernel.types import AutonomyTokenPolicy
from ats.market.calendar.models import SessionCalendar
from ats.persistence import IntegrityViolationError, connect_postgres
from ats.persistence.postgres import PostgresTransactionManager
from ats.persistence.types import ReductionAuthorityRecord
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import (
    RuntimeConfig,
    RuntimeEvent,
    RuntimeEventKind,
    TradingRuntime,
)
from ats.trading_runtime.position_authority import PositionAuthorityRecord, PositionAuthorityStore
from ats.trading_runtime.reduction_authority import (
    BeginReductionRequest,
    ReductionAuthorityError,
    ReductionAuthorityService,
)

from tests.unit.contracts.domain.fixtures import make_contracts
from tests.unit.kernel.fixtures import T0, _validated, make_kernel_fixture, uid

pytest_plugins = ("tests.integration.persistence.conftest",)


def _material(postgres_dsn: str):
    kernel = make_kernel_fixture()
    position = _validated(make_contracts()["Position"])
    authority_time = position.updated_at
    policy = _validated(
        kernel["policy"],
        policy_id=position.policy_id,
        policy_version=position.policy_version,
    )
    risk = _validated(
        kernel["risk_decision"],
        risk_decision_id=uid(930),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        decided_at=T0,
    )
    context = _validated(
        kernel["context"],
        governance_context_id=uid(931),
        action_subject_id=position.position_id,
        action_kind=ActionKind.CLOSE_POSITION,
        risk_direction=RiskDirection.REDUCE,
        candidate_id=None,
        candidate_version=None,
        position_thesis_id=uid(932),
        position_thesis_version=1,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        system_state_version=1,
        created_at=authority_time,
    )
    candidate = kernel["candidate"]
    advisory = kernel["advisory"]
    constraints = kernel["constraints"]
    manager = PostgresTransactionManager(lambda: connect_postgres(postgres_dsn))
    record = PositionAuthorityRecord(
        position=position,
        fills=(make_contracts()["Fill"],),
        entry_candidate_id=candidate.candidate_id,
        entry_candidate_hash=compute_payload_hash(candidate),
        entry_context_id=UUID("80000000-0000-0000-0000-000000000002"),
        entry_context_hash="b" * 64,
        entry_risk_decision_id=UUID("80000000-0000-0000-0000-000000000003"),
        entry_risk_decision_hash="c" * 64,
        entry_token_id=UUID("80000000-0000-0000-0000-000000000004"),
        entry_order_intent_id=UUID("80000000-0000-0000-0000-000000000005"),
        entry_order_intent_hash="d" * 64,
        reservation_id=UUID("80000000-0000-0000-0000-000000000006"),
        campaign_id=UUID("80000000-0000-0000-0000-000000000007"),
        campaign_version=1,
        entry_system_state_version=1,
        constraints_hash=canonical_sha256(constraints.model_dump(mode="json")),
    )
    request = BeginReductionRequest(
        reduction_id=uid(940),
        execution_id=uid(941),
        exit_intent_id=uid(942),
        exit_token_id=uid(943),
        position_id=position.position_id,
        expected_snapshot_version=1,
        requested_quantity=abs(position.net_quantity),
        reason=ExitReason.RISK,
        idempotency_key="reduction:position-1:v1:full:risk",
        context=context,
        risk_decision=risk,
        policy=policy,
        historical_candidate=candidate,
        advisory=advisory,
        entry_constraints=constraints,
        current_constraints=constraints,
        capital_basis=kernel["basis"],
        execution_safety=kernel["safety"],
        current_system_state_version=1,
        issued_at=authority_time,
        expires_at=authority_time + timedelta(minutes=1),
        nonce="fresh-reduction-nonce-not-persisted",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=120_000),
    )
    return manager, record, request


def test_begin_reduction_commits_complete_authority_atomically(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)

    result = ReductionAuthorityService(manager).begin_reduction(request)

    assert result.execution.state.value == "SUBMITTING"
    with manager.transaction() as transaction:
        evidence = transaction.reduction_authority.get(str(request.reduction_id))
        order = transaction.order_authority.get_by_idempotency_key(request.idempotency_key)
        token = transaction.tokens.get(str(request.exit_token_id))
        position = transaction.positions.get(str(request.position_id))
    assert evidence is not None
    assert evidence.position_id == str(request.position_id)
    assert evidence.payload["governance_context"]["candidate_id"] is None
    assert order is not None and order.payload["validation_result"] == "ALLOW"
    assert token is not None and token.consumed_at == request.issued_at
    assert "fresh-reduction-nonce-not-persisted" not in str(order.payload)
    assert position is not None and position.payload["reductions"][0]["state"] == "SUBMITTING"


def test_begin_reduction_is_idempotent_without_second_token(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    service = ReductionAuthorityService(manager)
    first = service.begin_reduction(request)
    second = service.begin_reduction(request)
    assert second.reduction_id == first.reduction_id
    with manager.transaction() as transaction:
        assert len(transaction.reduction_authority.for_position(str(request.position_id))) == 1
        assert transaction.positions.get(str(request.position_id)).version == 2


def test_reduction_insert_conflict_rolls_back_token_order_and_position(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    conflict_payload = {
        "reduction_id": str(request.reduction_id),
        "position_id": str(request.position_id),
        "position_version": record.position.version,
        "position_evidence_hash": record.position.payload_hash,
        "governance_context_id": str(request.context.governance_context_id),
        "governance_context_payload_hash": request.context.payload_hash,
        "risk_decision_id": str(request.risk_decision.risk_decision_id),
        "risk_decision_payload_hash": request.risk_decision.payload_hash,
        "risk_direction": "REDUCE",
        "action_kind": request.context.action_kind.value,
        "system_state_version": 1,
        "effective_constraints_hash": canonical_sha256(
            request.current_constraints.model_dump(mode="json")
        ),
        "requested_quantity": str(request.requested_quantity),
        "exit_reason": "STOP",
        "decision_outcome": "ALLOW",
    }
    with manager.transaction() as transaction:
        transaction.reduction_authority.append(
            ReductionAuthorityRecord(
                reduction_id=str(request.reduction_id),
                position_id=str(request.position_id),
                position_version=record.position.version,
                position_evidence_hash=record.position.payload_hash,
                governance_context_id=str(request.context.governance_context_id),
                governance_context_payload_hash=request.context.payload_hash,
                risk_decision_id=str(request.risk_decision.risk_decision_id),
                risk_decision_payload_hash=request.risk_decision.payload_hash,
                action_kind=request.context.action_kind.value,
                system_state_version=1,
                effective_constraints_hash=canonical_sha256(
                    request.current_constraints.model_dump(mode="json")
                ),
                requested_quantity=request.requested_quantity,
                exit_reason="STOP",
                decision_outcome="ALLOW",
                payload=conflict_payload,
                payload_hash=canonical_sha256(conflict_payload),
                created_at=T0,
            )
        )

    with pytest.raises(IntegrityViolationError):
        ReductionAuthorityService(manager).begin_reduction(request)
    with manager.transaction() as transaction:
        assert transaction.tokens.get(str(request.exit_token_id)) is None
        assert transaction.order_authority.get_by_idempotency_key(request.idempotency_key) is None
        assert transaction.positions.get(str(request.position_id)).version == 1


def test_denied_or_stale_reduction_leaves_no_partial_authority(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    stale = request.__class__(**{**request.__dict__, "expected_snapshot_version": 2})
    with pytest.raises(ReductionAuthorityError, match="stale"):
        ReductionAuthorityService(manager).begin_reduction(stale)
    with manager.transaction() as transaction:
        assert transaction.tokens.get(str(request.exit_token_id)) is None
        assert transaction.reduction_authority.get(str(request.reduction_id)) is None
        assert transaction.order_authority.get_by_idempotency_key(request.idempotency_key) is None


class _LostSubmissionResultBroker(PaperBrokerAdapter):
    def submit_order(self, request, *, now):  # type: ignore[no-untyped-def]
        super().submit_order(request, now=now)
        return None


def test_unknown_submission_recovers_fixed_order_without_resubmit(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    service = ReductionAuthorityService(manager)
    authorized = service.begin_reduction(request)
    broker = _LostSubmissionResultBroker()
    unknown = service.submit(authorized, broker=broker, submitted_at=request.issued_at)
    assert unknown.state.value == "SUBMITTED_UNACKNOWLEDGED"

    restarted = ReductionAuthorityService(manager)
    recovered = restarted.recover_pending()
    assert len(recovered) == 1
    assert recovered[0].execution.state.value == "SUBMITTED_UNACKNOWLEDGED"
    reconciled = restarted.reconcile(
        request.reduction_id,
        broker=broker,
        reconciled_at=request.issued_at + timedelta(seconds=1),
    )
    assert reconciled.state.value == "ACKNOWLEDGED"
    with manager.transaction() as transaction:
        assert transaction.tokens.get(str(request.exit_token_id)).consumed_at == request.issued_at
        assert len(transaction.reduction_authority.for_position(str(request.position_id))) == 1


def test_partial_fill_restart_and_duplicate_full_fill_are_exactly_once(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    service = ReductionAuthorityService(manager)
    authorized = service.begin_reduction(request)
    broker = PaperBrokerAdapter()
    acknowledged = service.submit(authorized, broker=broker, submitted_at=request.issued_at)
    assert acknowledged.state.value == "ACKNOWLEDGED"
    order_id = f"paper-{request.idempotency_key}"
    broker.seed_fill(
        order_id,
        Decimal("101"),
        Decimal("4"),
        request.issued_at + timedelta(seconds=1),
    )
    partial = service.reconcile(
        request.reduction_id,
        broker=broker,
        reconciled_at=request.issued_at + timedelta(seconds=1),
    )
    assert partial.state.value == "PARTIALLY_FILLED"

    restarted = ReductionAuthorityService(manager)
    recovered = restarted.recover_pending()
    assert recovered[0].execution.state.value == "PARTIALLY_FILLED"
    with manager.transaction() as transaction:
        snapshot = transaction.positions.get(str(request.position_id))
    assert snapshot.payload["position"]["net_quantity"] == "6"
    assert snapshot.payload["reductions"][0]["remaining_quantity"] == "6"

    broker.seed_fill(
        order_id,
        Decimal("102"),
        Decimal("10"),
        request.issued_at + timedelta(seconds=2),
    )
    closed = restarted.reconcile(
        request.reduction_id,
        broker=broker,
        reconciled_at=request.issued_at + timedelta(seconds=2),
    )
    assert closed.state.value == "CLOSED"
    duplicate = restarted.reconcile(
        request.reduction_id,
        broker=broker,
        reconciled_at=request.issued_at + timedelta(seconds=3),
    )
    assert duplicate.state.value == "CLOSED"
    with manager.transaction() as transaction:
        snapshot = transaction.positions.get(str(request.position_id))
    assert snapshot.state == "CLOSED"
    assert snapshot.payload["position"]["net_quantity"] == "0"
    assert snapshot.payload["position"]["version"] == record.position.version + 2


def _runtime(
    manager: PostgresTransactionManager,
    requests: dict[str, BeginReductionRequest],
    broker: PaperBrokerAdapter,
) -> TradingRuntime:
    at = next(iter(requests.values())).issued_at
    calendar = SessionCalendar(
        calendar_id="D077-TEST",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(at.date(),),
        preopen_start=time(0, 0),
        market_open=time(0, 1),
        market_close=time(23, 59),
        overrides=(),
    )

    def factory(position_id, at, reason_codes, source):  # type: ignore[no-untyped-def]
        _ = (reason_codes, source)
        request = requests[position_id]
        return replace(
            request,
            issued_at=at,
            expires_at=at + timedelta(minutes=1),
        )

    return TradingRuntime(
        config=RuntimeConfig(calendar=calendar),
        market_feed=InMemoryMarketFeed(),
        broker=broker,
        reduction_authority=ReductionAuthorityService(manager),
        reduction_request_factory=factory,
        durable_positions=PositionAuthorityStore(manager),
    )


def test_trading_runtime_dashboard_exit_uses_durable_reduction_path(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    broker = PaperBrokerAdapter()
    runtime = _runtime(manager, {str(request.position_id): request}, broker)
    result = runtime.request_exit(str(request.position_id), request.issued_at, source="DASHBOARD")
    assert result["accepted"] and result["authorized"]
    assert result["execution_state"] == "ACKNOWLEDGED"
    assert str(request.position_id) in runtime.state.open_positions
    order_id = f"paper-{request.idempotency_key}"
    broker.seed_fill(
        order_id,
        Decimal("101"),
        request.requested_quantity,
        request.issued_at + timedelta(seconds=1),
    )
    reconciled = runtime.reconcile_exit(
        str(request.position_id), request.issued_at + timedelta(seconds=1)
    )
    assert reconciled["execution_state"] == "CLOSED"
    assert str(request.position_id) not in runtime.state.open_positions


def test_trading_runtime_automatic_exit_uses_same_durable_reduction_path(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, record, request = _material(postgres_dsn)
    PositionAuthorityStore(manager).persist_open(record)
    broker = PaperBrokerAdapter()
    runtime = _runtime(manager, {str(request.position_id): request}, broker)
    position_id = str(request.position_id)
    runtime.state.open_positions[position_id] = replace(
        runtime.state.open_positions[position_id], thesis_healthy=False
    )
    runtime.market_feed.set_mark(
        record.position.instrument_id, record.position.mark_price, request.issued_at
    )
    result = runtime.process_event(
        RuntimeEvent(
            kind=RuntimeEventKind.THESIS_INVALIDATED,
            instrument_id=record.position.instrument_id,
            payload={},
            at=request.issued_at,
        )
    )
    assert result["exits"][0]["position_id"] == position_id
    assert runtime.state.pending_exits[position_id].authorized
    assert runtime.state.pending_exits[position_id].execution_state == "ACKNOWLEDGED"


def test_runtime_flatten_uses_distinct_authority_per_durable_position(
    postgres_dsn: str, pg_connection: object
) -> None:
    _ = pg_connection
    manager, first_record, first_request = _material(postgres_dsn)
    second_position = _validated(
        first_record.position,
        position_id=uid(970),
        instrument_id="BANKNIFTY-TEST-ONLY",
    )
    second_advisory = _validated(first_request.advisory, advisory_id=uid(978))
    second_candidate = _validated(
        first_request.historical_candidate,
        candidate_id=uid(979),
        instrument_id=second_position.instrument_id,
        advisory_id=second_advisory.advisory_id,
    )
    second_record = replace(
        first_record,
        position=second_position,
        reservation_id=uid(971),
        entry_candidate_id=second_candidate.candidate_id,
        entry_candidate_hash=compute_payload_hash(second_candidate),
    )
    second_context = _validated(
        first_request.context,
        governance_context_id=uid(972),
        action_subject_id=second_position.position_id,
    )
    second_risk = _validated(
        first_request.risk_decision,
        risk_decision_id=uid(973),
    )
    second_request = replace(
        first_request,
        reduction_id=uid(974),
        execution_id=uid(975),
        exit_intent_id=uid(976),
        exit_token_id=uid(977),
        position_id=second_position.position_id,
        context=second_context,
        risk_decision=second_risk,
        historical_candidate=second_candidate,
        advisory=second_advisory,
        idempotency_key="reduction:banknifty:v1:full:flatten",
    )
    store = PositionAuthorityStore(manager)
    store.persist_open(first_record)
    store.persist_open(second_record)
    broker = PaperBrokerAdapter()
    runtime = _runtime(
        manager,
        {
            str(first_request.position_id): first_request,
            str(second_request.position_id): second_request,
        },
        broker,
    )
    results = runtime.request_flatten(first_request.issued_at, source="DASHBOARD")
    assert len(results) == 2
    assert all(result["authorized"] for result in results)
    assert {result["reduction_id"] for result in results} == {
        str(first_request.reduction_id),
        str(second_request.reduction_id),
    }
    broker.seed_fill(
        f"paper-{first_request.idempotency_key}",
        Decimal("101"),
        first_request.requested_quantity,
        first_request.issued_at + timedelta(seconds=1),
    )
    runtime.reconcile_exit(
        str(first_request.position_id), first_request.issued_at + timedelta(seconds=1)
    )
    assert len(runtime.state.open_positions) == 1
    broker.seed_fill(
        f"paper-{second_request.idempotency_key}",
        Decimal("202"),
        second_request.requested_quantity,
        second_request.issued_at + timedelta(seconds=2),
    )
    runtime.reconcile_exit(
        str(second_request.position_id), second_request.issued_at + timedelta(seconds=2)
    )
    assert runtime.state.open_positions == {}
    with manager.transaction() as transaction:
        first_evidence = transaction.reduction_authority.get(str(first_request.reduction_id))
        second_evidence = transaction.reduction_authority.get(str(second_request.reduction_id))
    assert first_evidence.governance_context_id != second_evidence.governance_context_id
    assert first_evidence.risk_decision_id != second_evidence.risk_decision_id
