"""Deterministic fixtures for every frozen A03 event payload."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ats.contracts.domain.types import (
    AdvisoryOutcome,
    AutonomyLevel,
    DataQualityState,
    ExitReason,
    ForecastStatus,
    LossState,
    PaperOrderType,
    RiskOutcome,
    Side,
)
from ats.contracts.events import (
    EVENT_REGISTRY,
    AutonomyGrantedPayload,
    CandidateCreatedPayload,
    EventEnvelope,
    EventPayload,
    EventType,
    ExitIntentCreatedPayload,
    FeaturesReadyPayload,
    ForecastReadyPayload,
    MarketSnapshotReadyPayload,
    OrderIntentCreatedPayload,
    PaperOrderAcceptedPayload,
    PaperOrderFilledPayload,
    PaperOrderPartiallyFilledPayload,
    PaperOrderRejectedPayload,
    PolicyActivatedPayload,
    PolicyDraftedPayload,
    PolicyValidatedPayload,
    PositionClosedPayload,
    PositionOpenedPayload,
    PositionUpdatedPayload,
    ReconciliationCompletedPayload,
    ReconciliationFailedPayload,
    ReconciliationStartedPayload,
    RiskEvaluatedPayload,
    SupervisorEvaluatedPayload,
    SystemHaltedPayload,
    TradeReviewReadyPayload,
    create_event,
)
from ats.contracts.ids import fixture_id

NOW = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(minutes=5)
HASH_A = "a" * 64
HASH_B = "b" * 64
TRACE_ID = "0123456789abcdef0123456789abcdef"


def uid(name: str):  # type: ignore[no-untyped-def]
    return fixture_id(f"a03:{name}")


def make_payloads() -> dict[EventType, EventPayload]:
    return {
        EventType.MARKET_SNAPSHOT_READY: MarketSnapshotReadyPayload(
            snapshot_id=uid("snapshot"),
            instrument_id="RELIANCE",
            timeframe="5m",
            sequence=1,
            quality_state=DataQualityState.GOOD,
            payload_hash=HASH_A,
        ),
        EventType.FEATURES_READY: FeaturesReadyPayload(
            feature_bundle_id=uid("features"),
            snapshot_id=uid("snapshot"),
            feature_version="1.0.0",
            quality_flags=(),
            input_hash=HASH_A,
        ),
        EventType.FORECAST_READY: ForecastReadyPayload(
            forecast_id=uid("forecast"),
            feature_bundle_id=uid("features"),
            model_id="kronos",
            model_version="1.0.0",
            horizon_bars=12,
            status=ForecastStatus.READY,
            payload_hash=HASH_B,
        ),
        EventType.POLICY_DRAFTED: PolicyDraftedPayload(
            draft_id=uid("draft"),
            source_instruction_hash=HASH_A,
            requested_autonomy=AutonomyLevel.A2,
            executable=False,
            issue_codes=(),
        ),
        EventType.POLICY_VALIDATED: PolicyValidatedPayload(
            policy_id=uid("policy"),
            policy_version=1,
            validation_result="VALID",
            validation_report_hash=HASH_B,
            issue_codes=(),
        ),
        EventType.POLICY_ACTIVATED: PolicyActivatedPayload(
            policy_id=uid("policy"),
            policy_version=1,
            activation_mode="A2_PAPER",
            actor_subject="operator:test",
            activated_at=NOW,
        ),
        EventType.CANDIDATE_CREATED: CandidateCreatedPayload(
            candidate_id=uid("candidate"),
            snapshot_id=uid("snapshot"),
            forecast_id=uid("forecast"),
            confidence_id=uid("confidence"),
            policy_id=uid("policy"),
            policy_version=1,
        ),
        EventType.RISK_EVALUATED: RiskEvaluatedPayload(
            risk_decision_id=uid("risk-decision"),
            risk_facts_id=uid("risk-facts"),
            decision=RiskOutcome.ALLOW,
            loss_state=LossState.NORMAL,
            reason_codes=(),
        ),
        EventType.SUPERVISOR_EVALUATED: SupervisorEvaluatedPayload(
            advisory_id=uid("advisory"),
            packet_id=uid("packet"),
            recommendation=AdvisoryOutcome.APPROVE,
            model_id="supervisor",
            model_version="1.0.0",
            reason_codes=(),
        ),
        EventType.AUTONOMY_GRANTED: AutonomyGrantedPayload(
            token_id=uid("token"),
            scope="A2_PAPER",
            policy_id=uid("policy"),
            policy_version=1,
            risk_decision_id=uid("risk-decision"),
            advisory_id=uid("advisory"),
            expires_at=LATER,
            nonce="nonce-001",
        ),
        EventType.ORDER_INTENT_CREATED: OrderIntentCreatedPayload(
            intent_id=uid("intent"),
            instrument_id="RELIANCE",
            side=Side.BUY,
            quantity=Decimal("2"),
            order_type=PaperOrderType.MARKET,
            token_id=uid("token"),
            idempotency_key="intent-key-001",
        ),
        EventType.PAPER_ORDER_ACCEPTED: PaperOrderAcceptedPayload(
            paper_order_id=uid("paper-order"),
            intent_id=uid("intent"),
            status="ACCEPTED",
            broker_model_version="1.0.0",
            accepted_at=NOW,
        ),
        EventType.PAPER_ORDER_REJECTED: PaperOrderRejectedPayload(
            paper_order_id=uid("paper-order-rejected"),
            intent_id=uid("intent-2"),
            status="REJECTED",
            rejection_reason="fixture rejection",
            updated_at=NOW,
        ),
        EventType.PAPER_ORDER_PARTIALLY_FILLED: PaperOrderPartiallyFilledPayload(
            paper_order_id=uid("paper-order"),
            fill_id=uid("fill-1"),
            fill_quantity=Decimal("1"),
            cumulative_quantity=Decimal("1"),
            remaining_quantity=Decimal("1"),
        ),
        EventType.PAPER_ORDER_FILLED: PaperOrderFilledPayload(
            paper_order_id=uid("paper-order"),
            fill_id=uid("fill-2"),
            fill_quantity=Decimal("1"),
            cumulative_quantity=Decimal("2"),
            status="FILLED",
        ),
        EventType.POSITION_OPENED: PositionOpenedPayload(
            position_id=uid("position"),
            portfolio_id=uid("portfolio"),
            instrument_id="RELIANCE",
            opening_fill_id=uid("fill-1"),
            position_version=1,
        ),
        EventType.POSITION_UPDATED: PositionUpdatedPayload(
            position_id=uid("position"),
            position_version=2,
            last_fill_id=uid("fill-2"),
            net_quantity=Decimal("2"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("12.50"),
        ),
        EventType.EXIT_INTENT_CREATED: ExitIntentCreatedPayload(
            exit_intent_id=uid("exit-intent"),
            position_id=uid("position"),
            position_version=2,
            reason=ExitReason.TARGET,
            quantity=Decimal("2"),
            idempotency_key="exit-key-001",
        ),
        EventType.POSITION_CLOSED: PositionClosedPayload(
            position_id=uid("position"),
            position_version=3,
            closing_fill_id=uid("fill-close"),
            realized_pnl=Decimal("25.00"),
            closed_at=LATER,
        ),
        EventType.RECONCILIATION_STARTED: ReconciliationStartedPayload(
            reconciliation_id=uid("reconciliation"),
            scope="paper",
            started_at=NOW,
            prior_system_state="STARTING",
        ),
        EventType.RECONCILIATION_COMPLETED: ReconciliationCompletedPayload(
            reconciliation_id=uid("reconciliation"),
            checked_orders=2,
            checked_fills=2,
            checked_positions=1,
            differences=0,
            completed_at=LATER,
        ),
        EventType.RECONCILIATION_FAILED: ReconciliationFailedPayload(
            reconciliation_id=uid("reconciliation-failed"),
            difference_count=1,
            reason_codes=("POSITION_MISMATCH",),
            failed_at=LATER,
        ),
        EventType.SYSTEM_HALTED: SystemHaltedPayload(
            halt_id=uid("halt"),
            reason_codes=("RECONCILIATION_FAILED",),
            prior_state="RECONCILING",
            halted_at=LATER,
            manual_clear_required=True,
        ),
        EventType.TRADE_REVIEW_READY: TradeReviewReadyPayload(
            review_id=uid("review"),
            position_id=uid("position"),
            policy_id=uid("policy"),
            policy_version=1,
            reviewer_model_id="reviewer",
            payload_hash=HASH_B,
        ),
    }


def make_event(event_type: EventType, *, sequence: int = 1) -> EventEnvelope:
    entry = EVENT_REGISTRY[(event_type, 1)]
    return create_event(
        event_id=uid(f"event:{event_type.value}"),
        event_type=event_type,
        aggregate_id=uid(f"aggregate:{entry.aggregate}"),
        correlation_id=uid("correlation"),
        sequence=sequence,
        occurred_at=NOW,
        recorded_at=NOW,
        producer=entry.producer,
        payload=make_payloads()[event_type],
        trace_id=TRACE_ID,
    )


def make_golden_chain() -> tuple[EventEnvelope, ...]:
    payloads = make_payloads()
    candidate_aggregate = uid("aggregate:candidate")
    intent_aggregate = uid("aggregate:intent")
    correlation = uid("golden-correlation")
    kinds = (
        EventType.CANDIDATE_CREATED,
        EventType.RISK_EVALUATED,
        EventType.SUPERVISOR_EVALUATED,
        EventType.AUTONOMY_GRANTED,
        EventType.ORDER_INTENT_CREATED,
    )
    events: list[EventEnvelope] = []
    for index, event_type in enumerate(kinds):
        aggregate = candidate_aggregate if index < 4 else intent_aggregate
        sequence = index + 1 if index < 4 else 1
        event = create_event(
            event_id=uid(f"golden-event:{index + 1}"),
            event_type=event_type,
            aggregate_id=aggregate,
            correlation_id=correlation,
            sequence=sequence,
            occurred_at=NOW + timedelta(seconds=index),
            recorded_at=NOW + timedelta(seconds=index, milliseconds=10),
            producer=EVENT_REGISTRY[(event_type, 1)].producer,
            payload=payloads[event_type],
            trace_id=TRACE_ID,
            causation_id=events[-1].event_id if events else None,
        )
        events.append(event)
    return tuple(events)
