"""Atomic, position-bound authority start for A2 paper reductions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

from ats.contracts import canonical_sha256
from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import (
    ExitIntent,
    Position,
    RiskDecision,
    StrategyPolicy,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import ExitReason, PaperOrderType, PositionStatus, RiskOutcome
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate
from ats.contracts.governance.types import EffectiveConstraintSet, RiskDirection
from ats.execution.lifecycle import (
    ExecutionLifecycle,
    ExecutionState,
    create_execution,
    transition_execution,
)
from ats.kernel.order_guard import validate_exit_intent
from ats.kernel.reduction import construct_reduction_token, validate_reduction_eligibility
from ats.kernel.types import (
    AutonomyTokenPolicy,
    ExecutionSafetyFacts,
    ExitEvaluationFacts,
    KernelOutcome,
    RiskCapitalBasis,
)
from ats.persistence import IntegrityViolationError, Transaction, TransactionManager
from ats.persistence.types import (
    AuditRecord,
    OrderAuthorityRecord,
    ReductionAuthorityRecord,
    StateSnapshot,
)

from .broker import ExecutionBroker, OrderRequest, OrderStatus
from .position_authority import PositionAuthorityIntegrityError, PositionAuthorityRecord

_EXECUTION_AUDIT_NAMESPACE = UUID("df4bf7c2-b5bd-5c71-a3d7-64e262941f07")
_PAPER_ORDER_NAMESPACE = UUID("0232991a-f4d0-5cc7-a835-cb76e581dd09")
_REDUCTION_FILL_NAMESPACE = UUID("d397c780-7530-55cf-8c82-b9d11f5af0cc")
_TERMINAL_REDUCTION_STATES = frozenset({"CANCELLED", "CLOSED", "FILLED", "REJECTED"})


class ReductionAuthorityError(RuntimeError):
    """A reduction could not obtain or persist executable authority."""


@dataclass(frozen=True)
class BeginReductionRequest:
    reduction_id: UUID
    execution_id: UUID
    exit_intent_id: UUID
    exit_token_id: UUID
    position_id: UUID
    expected_snapshot_version: int
    requested_quantity: Decimal
    reason: ExitReason
    idempotency_key: str
    context: GovernanceContext
    risk_decision: RiskDecision
    policy: StrategyPolicy
    historical_candidate: OpportunityCandidate
    advisory: SupervisorAdvisory
    entry_constraints: EffectiveConstraintSet
    current_constraints: EffectiveConstraintSet
    capital_basis: RiskCapitalBasis | None
    execution_safety: ExecutionSafetyFacts
    current_system_state_version: int
    issued_at: UTCDateTime
    expires_at: UTCDateTime
    nonce: str
    token_policy: AutonomyTokenPolicy
    order_type: PaperOrderType = PaperOrderType.MARKET
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None


@dataclass(frozen=True)
class AuthorizedReduction:
    reduction_id: UUID
    exit_intent: ExitIntent
    execution: ExecutionLifecycle
    snapshot_version: int


class _TransactionExecutionJournal:
    def __init__(self, transaction: Transaction) -> None:
        self._transaction = transaction

    def append(self, lifecycle: ExecutionLifecycle) -> None:
        preimage = lifecycle.model_dump(mode="python", exclude={"payload_hash"})
        if canonical_sha256(preimage) != lifecycle.payload_hash:
            raise IntegrityViolationError("execution lifecycle payload hash mismatch")
        payload = lifecycle.model_dump(mode="python")
        self._transaction.audit.append(
            AuditRecord(
                audit_id=str(
                    uuid5(
                        _EXECUTION_AUDIT_NAMESPACE,
                        f"{lifecycle.execution_id}:{lifecycle.version}",
                    )
                ),
                event_id=None,
                actor_type="SYSTEM",
                actor_id="A2_PAPER_REDUCTION_FSM",
                action=f"EXECUTION_{lifecycle.state.value}",
                object_type="EXECUTION_LIFECYCLE",
                object_id=str(lifecycle.execution_id),
                payload=payload,
                record_hash=canonical_sha256(payload),
                occurred_at=lifecycle.updated_at,
                trace_id=str(lifecycle.execution_id),
            )
        )

    def recover_latest(self, execution_id: UUID) -> ExecutionLifecycle | None:
        records = self._transaction.audit.for_object("EXECUTION_LIFECYCLE", str(execution_id))
        if not records:
            return None
        return ExecutionLifecycle.model_validate_json(
            json.dumps(max(records, key=lambda item: item.occurred_at).payload)
        )


class ReductionAuthorityService:
    """Starts a reduction only when its complete authority chain commits atomically."""

    def __init__(self, transactions: TransactionManager) -> None:
        self._transactions = transactions

    def begin_reduction(self, request: BeginReductionRequest) -> AuthorizedReduction:
        with self._transactions.transaction() as transaction:
            existing = transaction.order_authority.get_by_idempotency_key(request.idempotency_key)
            if existing is not None:
                return self._recover_existing(transaction, request, existing.payload)

            snapshot = transaction.positions.get(str(request.position_id))
            if snapshot is None:
                raise ReductionAuthorityError("position authority record is missing")
            self._verify_snapshot(snapshot, request.expected_snapshot_version)
            position_record = PositionAuthorityRecord.from_payload(snapshot.payload)
            position = position_record.position
            self._verify_entry_lineage(position_record, request)
            context = self._construct_context(request)
            reductions = list(snapshot.payload.get("reductions", []))
            unresolved = any(
                str(item.get("state")) not in _TERMINAL_REDUCTION_STATES
                for item in reductions
                if isinstance(item, dict)
            )
            eligibility = validate_reduction_eligibility(
                position=position,
                context=context,
                policy=request.policy,
                entry_constraints=request.entry_constraints,
                current_constraints=request.current_constraints,
                capital_basis=request.capital_basis,
                requested_quantity=request.requested_quantity,
                execution_safety=request.execution_safety,
                current_system_state_version=request.current_system_state_version,
                unresolved_reduction_exists=unresolved,
                evaluation_time=request.issued_at,
            )
            if eligibility.outcome is not KernelOutcome.ALLOW:
                raise ReductionAuthorityError(
                    "reduction eligibility denied: "
                    + ",".join(code.value for code in eligibility.reason_codes)
                )
            risk_decision = self._construct_risk_decision(request, eligibility)
            self._verify_fresh_authority(request, context, risk_decision)
            token = construct_reduction_token(
                eligibility=eligibility,
                token_id=request.exit_token_id,
                historical_candidate=request.historical_candidate,
                policy=request.policy,
                risk_decision=risk_decision,
                advisory=request.advisory,
                context=context,
                issued_at=request.issued_at,
                expires_at=request.expires_at,
                nonce=request.nonce,
                token_policy=request.token_policy,
            )
            intent_values: dict[str, Any] = {
                "schema_version": "1.0",
                "exit_intent_id": request.exit_intent_id,
                "position_id": position.position_id,
                "position_version": position.version,
                "reason": request.reason,
                "quantity": request.requested_quantity,
                "order_type": request.order_type,
                "limit_price": request.limit_price,
                "stop_price": request.stop_price,
                "risk_decision_id": risk_decision.risk_decision_id,
                "autonomy_token_id": token.token_id,
                "idempotency_key": request.idempotency_key,
                "created_at": request.issued_at,
            }
            intent = ExitIntent.model_validate(
                {**intent_values, "payload_hash": canonical_sha256(intent_values)}
            )
            exit_validation = validate_exit_intent(
                intent,
                token=token,
                candidate=request.historical_candidate,
                position=position,
                context=context,
                exit_facts=ExitEvaluationFacts(reducible_quantity=abs(position.net_quantity)),
                execution_safety=request.execution_safety,
                evaluation_time=request.issued_at,
                current_system_state_version=request.current_system_state_version,
            )
            if exit_validation.outcome is not KernelOutcome.ALLOW:
                raise ReductionAuthorityError(
                    "exit intent validation denied: "
                    + ",".join(code.value for code in exit_validation.reason_codes)
                )

            journal = _TransactionExecutionJournal(transaction)
            execution = create_execution(
                execution_id=request.execution_id,
                intent_id=intent.exit_intent_id,
                reservation_id=position_record.reservation_id,
                autonomy_token_id=token.token_id,
                idempotency_key=request.idempotency_key,
                instrument_id=position.instrument_id,
                created_at=request.issued_at,
                journal=journal,
            )
            for target in (
                ExecutionState.AUTHORIZED,
                ExecutionState.RESERVED,
                ExecutionState.SUBMITTING,
            ):
                execution = transition_execution(
                    execution,
                    target=target,
                    updated_at=request.issued_at,
                    journal=journal,
                    reason_codes=(f"REDUCTION_{target.value}",),
                )

            transaction.tokens.issue(token)
            transaction.tokens.consume(
                str(token.token_id),
                evaluated_at=request.issued_at,
                candidate_id=str(token.candidate_id),
                policy_id=str(token.policy_id),
                policy_version=token.policy_version,
                risk_decision_id=str(token.risk_decision_id),
                advisory_id=str(token.advisory_id),
                system_state_version=token.system_state_version,
            )

            context_payload = context.model_dump(mode="json")
            risk_payload = risk_decision.model_dump(mode="json")
            reduction_payload = {
                "reduction_id": str(request.reduction_id),
                "position_id": str(position.position_id),
                "position_version": position.version,
                "position_evidence_hash": position.payload_hash,
                "governance_context_id": str(context.governance_context_id),
                "governance_context_payload_hash": context.payload_hash,
                "risk_decision_id": str(risk_decision.risk_decision_id),
                "risk_decision_payload_hash": risk_decision.payload_hash,
                "risk_direction": "REDUCE",
                "action_kind": context.action_kind.value,
                "system_state_version": request.current_system_state_version,
                "effective_constraints_hash": canonical_sha256(
                    request.current_constraints.model_dump(mode="json")
                ),
                "requested_quantity": str(request.requested_quantity),
                "exit_reason": request.reason.value,
                "decision_outcome": eligibility.outcome.value,
                "governance_context": context_payload,
                "risk_decision": risk_payload,
            }
            transaction.reduction_authority.append(
                ReductionAuthorityRecord(
                    reduction_id=str(request.reduction_id),
                    position_id=str(position.position_id),
                    position_version=position.version,
                    position_evidence_hash=position.payload_hash,
                    governance_context_id=str(context.governance_context_id),
                    governance_context_payload_hash=context.payload_hash,
                    risk_decision_id=str(risk_decision.risk_decision_id),
                    risk_decision_payload_hash=risk_decision.payload_hash,
                    action_kind=context.action_kind.value,
                    system_state_version=request.current_system_state_version,
                    effective_constraints_hash=canonical_sha256(
                        request.current_constraints.model_dump(mode="json")
                    ),
                    requested_quantity=request.requested_quantity,
                    exit_reason=request.reason.value,
                    decision_outcome=eligibility.outcome.value,
                    payload=reduction_payload,
                    payload_hash=canonical_sha256(reduction_payload),
                    created_at=request.issued_at,
                )
            )
            order_payload = {
                "reduction_id": str(request.reduction_id),
                "position_id": str(position.position_id),
                "token_id": str(token.token_id),
                "token_consumed_at": request.issued_at.isoformat(),
                "exit_intent": intent.model_dump(mode="json"),
                "exit_intent_payload_hash": intent.payload_hash,
                "validation_result": "ALLOW",
                "execution": execution.model_dump(mode="json"),
                "execution_id": str(execution.execution_id),
                "provider_order_lookup_key": f"paper-{request.idempotency_key}",
                "submission_started_at": request.issued_at.isoformat(),
            }
            transaction.order_authority.append(
                OrderAuthorityRecord(
                    authority_id=str(request.exit_intent_id),
                    idempotency_key=request.idempotency_key,
                    token_id=str(token.token_id),
                    external_state="NOT_SUBMITTED",
                    payload=order_payload,
                    payload_hash=canonical_sha256(order_payload),
                    recorded_at=request.issued_at,
                )
            )
            reductions.append(
                {
                    "reduction_id": str(request.reduction_id),
                    "execution_id": str(execution.execution_id),
                    "exit_intent_id": str(intent.exit_intent_id),
                    "idempotency_key": request.idempotency_key,
                    "requested_quantity": str(request.requested_quantity),
                    "filled_quantity": "0",
                    "remaining_quantity": str(request.requested_quantity),
                    "state": execution.state.value,
                    "external_state": "NOT_SUBMITTED",
                    "last_fill_ids": [],
                    "execution": execution.model_dump(mode="json"),
                }
            )
            updated_payload = {**snapshot.payload, "reductions": reductions}
            updated_snapshot = StateSnapshot(
                identifier=snapshot.identifier,
                version=snapshot.version + 1,
                state=snapshot.state,
                payload=updated_payload,
                payload_hash=canonical_sha256(updated_payload),
                updated_at=request.issued_at,
                external_state="NOT_SUBMITTED",
            )
            transaction.positions.save(
                updated_snapshot, expected_version=request.expected_snapshot_version
            )
        return AuthorizedReduction(
            reduction_id=request.reduction_id,
            exit_intent=intent,
            execution=execution,
            snapshot_version=updated_snapshot.version,
        )

    @staticmethod
    def _verify_snapshot(snapshot: StateSnapshot, expected_version: int) -> None:
        if canonical_sha256(snapshot.payload) != snapshot.payload_hash:
            raise PositionAuthorityIntegrityError("position state payload hash mismatch")
        if snapshot.version != expected_version or snapshot.state != "OPEN":
            raise ReductionAuthorityError("position version is stale or position is not open")

    @staticmethod
    def _verify_entry_lineage(
        record: PositionAuthorityRecord, request: BeginReductionRequest
    ) -> None:
        if (
            record.position.position_id != request.position_id
            or record.position.payload_hash != compute_payload_hash(record.position)
            or record.entry_candidate_id != request.historical_candidate.candidate_id
            or record.entry_candidate_hash != compute_payload_hash(request.historical_candidate)
            or record.constraints_hash
            != canonical_sha256(request.entry_constraints.model_dump(mode="json"))
        ):
            raise PositionAuthorityIntegrityError("entry authority lineage mismatch")

    @staticmethod
    def _construct_context(request: BeginReductionRequest) -> GovernanceContext:
        if request.context.payload_hash != compute_payload_hash(request.context):
            raise ReductionAuthorityError("REDUCE context template hash mismatch")
        values = request.context.model_dump(mode="python", exclude={"payload_hash"})
        values.update(
            {
                "action_subject_id": request.position_id,
                "risk_direction": RiskDirection.REDUCE,
                "candidate_id": None,
                "candidate_version": None,
                "system_state_version": request.current_system_state_version,
                "policy_id": request.policy.policy_id,
                "policy_version": request.policy.policy_version,
                "resolved_constraints": request.current_constraints,
                "created_at": request.issued_at,
            }
        )
        return GovernanceContext.model_validate(
            {**values, "payload_hash": canonical_sha256(values)}
        )

    @staticmethod
    def _construct_risk_decision(request: BeginReductionRequest, eligibility: Any) -> RiskDecision:
        if request.risk_decision.payload_hash != compute_payload_hash(request.risk_decision):
            raise ReductionAuthorityError("reduction risk template hash mismatch")
        values = request.risk_decision.model_dump(mode="python", exclude={"payload_hash"})
        values.update(
            {
                "decision": RiskOutcome.ALLOW,
                "policy_id": request.policy.policy_id,
                "policy_version": request.policy.policy_version,
                "snapshot_sequence": request.current_system_state_version,
                "reason_codes": tuple(code.value for code in eligibility.reason_codes),
                "decided_at": request.issued_at,
            }
        )
        return RiskDecision.model_validate({**values, "payload_hash": canonical_sha256(values)})

    @staticmethod
    def _verify_fresh_authority(
        request: BeginReductionRequest,
        context: GovernanceContext,
        risk_decision: RiskDecision,
    ) -> None:
        if (
            context.payload_hash != compute_payload_hash(context)
            or risk_decision.payload_hash != compute_payload_hash(risk_decision)
            or risk_decision.decision is not RiskOutcome.ALLOW
            or context.risk_direction is not RiskDirection.REDUCE
            or context.system_state_version != request.current_system_state_version
            or context.action_subject_id != request.position_id
        ):
            raise ReductionAuthorityError("fresh reduction authority binding mismatch")

    @staticmethod
    def _recover_existing(
        transaction: Transaction,
        request: BeginReductionRequest,
        payload: dict[str, Any],
    ) -> AuthorizedReduction:
        if payload.get("reduction_id") != str(request.reduction_id):
            raise ReductionAuthorityError("idempotency key is bound to another reduction")
        intent = ExitIntent.model_validate_json(json.dumps(payload["exit_intent"]))
        execution = ExecutionLifecycle.model_validate_json(json.dumps(payload["execution"]))
        snapshot = transaction.positions.get(str(request.position_id))
        if snapshot is None:
            raise ReductionAuthorityError("idempotent reduction position is missing")
        return AuthorizedReduction(
            reduction_id=request.reduction_id,
            exit_intent=intent,
            execution=execution,
            snapshot_version=snapshot.version,
        )

    def submit(
        self,
        authorized: AuthorizedReduction,
        *,
        broker: ExecutionBroker,
        submitted_at: UTCDateTime,
    ) -> ExecutionLifecycle:
        """Submit once after durability; ambiguous prior attempts are reconciled."""
        with self._transactions.transaction() as transaction:
            snapshot, index, workflow, position = self._load_workflow(
                transaction, str(authorized.reduction_id)
            )
            lifecycle = self._workflow_lifecycle(workflow)
            if lifecycle.state is not ExecutionState.SUBMITTING:
                return lifecycle
            order = transaction.order_authority.get_by_idempotency_key(
                str(workflow["idempotency_key"])
            )
            if order is None:
                raise PositionAuthorityIntegrityError("order authority evidence is missing")
            intent = ExitIntent.model_validate_json(json.dumps(order.payload["exit_intent"]))
            request = OrderRequest(
                instrument_id=position.instrument_id,
                side="SELL" if position.net_quantity > 0 else "BUY",
                quantity=intent.quantity,
                order_type=intent.order_type.value,
                limit_price=intent.limit_price,
                idempotency_key=intent.idempotency_key,
                intent_id=str(intent.exit_intent_id),
            )
        result = broker.submit_order(request, now=submitted_at)
        return self.record_submission_result(
            authorized.reduction_id, result=result, recorded_at=submitted_at
        )

    def record_submission_result(
        self,
        reduction_id: UUID,
        *,
        result: OrderStatus | None,
        recorded_at: UTCDateTime,
    ) -> ExecutionLifecycle:
        with self._transactions.transaction() as transaction:
            snapshot, index, workflow, position = self._load_workflow(
                transaction, str(reduction_id)
            )
            lifecycle = self._workflow_lifecycle(workflow)
            if lifecycle.state is not ExecutionState.SUBMITTING:
                return lifecycle
            if result is None:
                updated = transition_execution(
                    lifecycle,
                    target=ExecutionState.SUBMITTED_UNACKNOWLEDGED,
                    updated_at=recorded_at,
                    journal=_TransactionExecutionJournal(transaction),
                    reason_codes=("PAPER_SUBMISSION_UNKNOWN",),
                )
                self._save_workflow(
                    transaction,
                    snapshot,
                    index,
                    workflow,
                    lifecycle=updated,
                    external_state="UNKNOWN",
                    updated_at=recorded_at,
                )
                return updated
            return self._apply_known_status(
                transaction,
                snapshot,
                index,
                workflow,
                position,
                lifecycle,
                result,
                recorded_at,
            )
        raise AssertionError("transaction exited without a submission result")

    def reconcile(
        self,
        reduction_id: UUID,
        *,
        broker: ExecutionBroker,
        reconciled_at: UTCDateTime,
    ) -> ExecutionLifecycle:
        """Query the fixed order identity; never submit an ambiguous workflow."""
        with self._transactions.transaction() as transaction:
            snapshot, index, workflow, position = self._load_workflow(
                transaction, str(reduction_id)
            )
            lifecycle = self._workflow_lifecycle(workflow)
            order = transaction.order_authority.get_by_idempotency_key(
                str(workflow["idempotency_key"])
            )
            if order is None:
                raise PositionAuthorityIntegrityError("order authority evidence is missing")
            lookup_key = str(order.payload["provider_order_lookup_key"])
        result = broker.query_order(lookup_key)
        with self._transactions.transaction() as transaction:
            snapshot, index, workflow, position = self._load_workflow(
                transaction, str(reduction_id)
            )
            lifecycle = self._workflow_lifecycle(workflow)
            if lifecycle.state not in {
                ExecutionState.SUBMITTING,
                ExecutionState.SUBMITTED_UNACKNOWLEDGED,
                ExecutionState.RECONCILING,
                ExecutionState.ACKNOWLEDGED,
                ExecutionState.PARTIALLY_FILLED,
            }:
                return lifecycle
            if result is None:
                if lifecycle.state is ExecutionState.SUBMITTING:
                    target = ExecutionState.SUBMITTED_UNACKNOWLEDGED
                elif lifecycle.state in {
                    ExecutionState.SUBMITTED_UNACKNOWLEDGED,
                    ExecutionState.RECONCILING,
                }:
                    target = ExecutionState.RECONCILING
                else:
                    target = ExecutionState.RECONCILING
                updated = transition_execution(
                    lifecycle,
                    target=target,
                    updated_at=reconciled_at,
                    journal=_TransactionExecutionJournal(transaction),
                    reason_codes=("PAPER_RECONCILIATION_UNKNOWN",),
                )
                self._save_workflow(
                    transaction,
                    snapshot,
                    index,
                    workflow,
                    lifecycle=updated,
                    external_state="UNKNOWN",
                    updated_at=reconciled_at,
                )
                return updated
            return self._apply_known_status(
                transaction,
                snapshot,
                index,
                workflow,
                position,
                lifecycle,
                result,
                reconciled_at,
            )
        raise AssertionError("transaction exited without a reconciliation result")

    def recover_pending(self) -> tuple[AuthorizedReduction, ...]:
        recovered: list[AuthorizedReduction] = []
        with self._transactions.transaction() as transaction:
            snapshots = transaction.positions.list_by_state("OPEN")
            for snapshot in snapshots:
                self._verify_snapshot_hash(snapshot)
                for workflow in snapshot.payload.get("reductions", []):
                    if not isinstance(workflow, dict):
                        raise PositionAuthorityIntegrityError("invalid reduction projection")
                    if str(workflow.get("state")) in _TERMINAL_REDUCTION_STATES:
                        continue
                    order = transaction.order_authority.get_by_idempotency_key(
                        str(workflow["idempotency_key"])
                    )
                    if order is None:
                        raise PositionAuthorityIntegrityError(
                            "pending reduction has no order authority"
                        )
                    reduction_id = UUID(str(workflow["reduction_id"]))
                    evidence = transaction.reduction_authority.get(str(reduction_id))
                    if evidence is None:
                        raise PositionAuthorityIntegrityError(
                            "pending reduction has no reduction authority"
                        )
                    recovered.append(
                        AuthorizedReduction(
                            reduction_id=reduction_id,
                            exit_intent=ExitIntent.model_validate_json(
                                json.dumps(order.payload["exit_intent"])
                            ),
                            execution=self._workflow_lifecycle(workflow),
                            snapshot_version=snapshot.version,
                        )
                    )
        return tuple(recovered)

    def _apply_known_status(
        self,
        transaction: Transaction,
        snapshot: StateSnapshot,
        index: int,
        workflow: dict[str, Any],
        position: Position,
        lifecycle: ExecutionLifecycle,
        result: OrderStatus,
        recorded_at: UTCDateTime,
    ) -> ExecutionLifecycle:
        target = {
            "ACKNOWLEDGED": ExecutionState.ACKNOWLEDGED,
            "REJECTED": ExecutionState.REJECTED,
            "CANCELLED": ExecutionState.CANCELLED,
            "PARTIALLY_FILLED": ExecutionState.PARTIALLY_FILLED,
            "FILLED": ExecutionState.FILLED,
        }.get(result.status)
        if target is None:
            raise ReductionAuthorityError(f"unsupported paper order status {result.status}")
        if lifecycle.state is target and result.filled_quantity == Decimal(
            str(workflow["filled_quantity"])
        ):
            return lifecycle
        updated = transition_execution(
            lifecycle,
            target=target,
            updated_at=recorded_at,
            journal=_TransactionExecutionJournal(transaction),
            paper_order_id=uuid5(_PAPER_ORDER_NAMESPACE, result.order_id),
            reason_codes=(f"PAPER_{result.status}",),
        )
        current_filled = Decimal(str(workflow["filled_quantity"]))
        delta = result.filled_quantity - current_filled
        if delta < 0:
            raise ReductionAuthorityError("cumulative fill quantity moved backwards")
        requested = Decimal(str(workflow["requested_quantity"]))
        if result.filled_quantity > requested or delta > abs(position.net_quantity):
            raise ReductionAuthorityError("paper fill would over-close the position")
        if delta > 0:
            if result.average_price is None:
                raise ReductionAuthorityError("filled paper order has no average price")
            fill_id = uuid5(
                _REDUCTION_FILL_NAMESPACE,
                f"{result.order_id}:{result.filled_quantity}:{result.average_price}",
            )
            fill_key = str(fill_id)
            applied = list(workflow.get("last_fill_ids", []))
            if fill_key in applied:
                return lifecycle
            applied.append(fill_key)
            sign = Decimal("1") if position.net_quantity > 0 else Decimal("-1")
            remaining_open = position.net_quantity - sign * delta
            realized_delta = (result.average_price - position.average_entry_price) * delta * sign
            closed = remaining_open == 0
            values = position.model_dump(mode="python", exclude={"payload_hash"})
            values.update(
                {
                    "net_quantity": remaining_open,
                    "mark_price": result.average_price,
                    "realized_pnl": position.realized_pnl + realized_delta,
                    "unrealized_pnl": Decimal("0") if closed else position.unrealized_pnl,
                    "updated_at": recorded_at,
                    "closed_at": recorded_at if closed else None,
                    "status": PositionStatus.CLOSED if closed else PositionStatus.REDUCED,
                    "version": position.version + 1,
                    "last_fill_id": fill_id,
                }
            )
            position = Position.model_validate({**values, "payload_hash": canonical_sha256(values)})
            workflow["last_fill_ids"] = applied
            workflow["filled_quantity"] = str(result.filled_quantity)
            workflow["remaining_quantity"] = str(requested - result.filled_quantity)
        workflow["provider_order_id"] = result.order_id
        state = updated.state
        if state in {ExecutionState.REJECTED, ExecutionState.CANCELLED}:
            updated = transition_execution(
                updated,
                target=ExecutionState.CLOSED,
                updated_at=recorded_at,
                journal=_TransactionExecutionJournal(transaction),
                reason_codes=("REDUCTION_TERMINAL_NO_FILL",),
            )
        elif state is ExecutionState.FILLED:
            if Decimal(str(workflow["remaining_quantity"])) != 0:
                raise ReductionAuthorityError("FILLED status has remaining reduction quantity")
            updated = transition_execution(
                updated,
                target=ExecutionState.CLOSED,
                updated_at=recorded_at,
                journal=_TransactionExecutionJournal(transaction),
                reason_codes=("REDUCTION_FILLED",),
            )
        self._save_workflow(
            transaction,
            snapshot,
            index,
            workflow,
            lifecycle=updated,
            external_state="REJECTED" if result.status == "REJECTED" else "CONFIRMED",
            updated_at=recorded_at,
            position=position,
        )
        return updated

    @staticmethod
    def _workflow_lifecycle(workflow: dict[str, Any]) -> ExecutionLifecycle:
        return ExecutionLifecycle.model_validate_json(json.dumps(workflow["execution"]))

    @classmethod
    def _load_workflow(
        cls, transaction: Transaction, reduction_id: str
    ) -> tuple[StateSnapshot, int, dict[str, Any], Position]:
        evidence = transaction.reduction_authority.get(reduction_id)
        if evidence is None:
            raise ReductionAuthorityError("reduction authority evidence is missing")
        snapshot = transaction.positions.get(evidence.position_id)
        if snapshot is None:
            raise PositionAuthorityIntegrityError("reduction position is missing")
        cls._verify_snapshot_hash(snapshot)
        record = PositionAuthorityRecord.from_payload(snapshot.payload)
        reductions = snapshot.payload.get("reductions", [])
        for index, workflow in enumerate(reductions):
            if isinstance(workflow, dict) and workflow.get("reduction_id") == reduction_id:
                return snapshot, index, dict(workflow), record.position
        raise PositionAuthorityIntegrityError("reduction projection is missing")

    @staticmethod
    def _save_workflow(
        transaction: Transaction,
        snapshot: StateSnapshot,
        index: int,
        workflow: dict[str, Any],
        *,
        lifecycle: ExecutionLifecycle,
        external_state: str,
        updated_at: UTCDateTime,
        position: Position | None = None,
    ) -> StateSnapshot:
        reductions = list(snapshot.payload["reductions"])
        workflow["state"] = lifecycle.state.value
        workflow["external_state"] = external_state
        workflow["execution"] = lifecycle.model_dump(mode="json")
        reductions[index] = workflow
        payload = {**snapshot.payload, "reductions": reductions}
        if position is not None:
            payload["position"] = position.model_dump(mode="json")
        state = (
            "CLOSED"
            if position is not None and position.status is PositionStatus.CLOSED
            else "OPEN"
        )
        updated = StateSnapshot(
            identifier=snapshot.identifier,
            version=snapshot.version + 1,
            state=state,
            payload=payload,
            payload_hash=canonical_sha256(payload),
            updated_at=updated_at,
            external_state=external_state,
        )
        transaction.positions.save(updated, expected_version=snapshot.version)
        return updated

    @staticmethod
    def _verify_snapshot_hash(snapshot: StateSnapshot) -> None:
        if canonical_sha256(snapshot.payload) != snapshot.payload_hash:
            raise PositionAuthorityIntegrityError("position state payload hash mismatch")


__all__ = [
    "AuthorizedReduction",
    "BeginReductionRequest",
    "ReductionAuthorityError",
    "ReductionAuthorityService",
]
