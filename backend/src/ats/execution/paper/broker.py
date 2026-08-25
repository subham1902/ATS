"""Pure derivative paper-broker mechanics; no live submission or I/O."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import ExitIntent, Fill, OrderIntent, PaperOrder, Position
from ats.contracts.domain.types import (
    DataQualityState,
    PaperOrderStatus,
    PaperOrderType,
    PositionStatus,
    Side,
)
from ats.kernel.types import KernelOutcome, KernelResult
from ats.market.derivatives.contract_master import DerivativeInstrument

from .errors import PaperExecutionError
from .models import (
    ObservedSubmissionState,
    PaperExecutionPolicy,
    PaperExecutionResult,
    PaperMarketFacts,
    PaperReconciliationResult,
    PaperSubmissionScenario,
    PaperSubmissionState,
    ReconciliationOutcome,
    SubmissionObservation,
)

_ORDER_NAMESPACE = UUID("c60ff528-ab0b-56f6-b025-7935694f7680")
_FILL_NAMESPACE = UUID("4423a19e-30bd-528b-a3ae-37c0d3653695")


def submit_paper_order(
    *,
    intent: OrderIntent,
    authorization: KernelResult,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: UTCDateTime,
) -> PaperExecutionResult:
    """Apply an already-completed A04 Stage-2 result to paper mechanics."""

    _validate_boundary(
        intent=intent,
        authorization=authorization,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    if market.scenario is PaperSubmissionScenario.TIMEOUT_UNKNOWN:
        return PaperExecutionResult(
            submission_state=PaperSubmissionState.UNKNOWN,
            order=None,
            fills=(),
            reason_codes=("SUBMISSION_STATE_UNKNOWN_RECONCILE_REQUIRED",),
        )
    order_id = uuid5(_ORDER_NAMESPACE, f"{intent.intent_id}:{intent.idempotency_key}")
    if market.scenario is PaperSubmissionScenario.REJECT:
        order = _order(
            order_id=order_id,
            intent=intent,
            status=PaperOrderStatus.REJECTED,
            filled_quantity=Decimal(0),
            average_fill_price=None,
            rejection_reason=market.rejection_reason,
            policy=policy,
            evaluation_time=evaluation_time,
            version=1,
        )
        return PaperExecutionResult(
            submission_state=PaperSubmissionState.REJECTED,
            order=order,
            fills=(),
            reason_codes=("PAPER_ORDER_REJECTED",),
        )
    accepted = _order(
        order_id=order_id,
        intent=intent,
        status=PaperOrderStatus.ACCEPTED,
        filled_quantity=Decimal(0),
        average_fill_price=None,
        rejection_reason=None,
        policy=policy,
        evaluation_time=evaluation_time,
        version=1,
    )
    order, fills = process_paper_order(
        order=accepted,
        intent=intent,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    return PaperExecutionResult(
        submission_state=PaperSubmissionState.ACKNOWLEDGED,
        order=order,
        fills=fills,
        reason_codes=("PAPER_ORDER_ACKNOWLEDGED",),
    )


def process_paper_order(
    *,
    order: PaperOrder,
    intent: OrderIntent,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: UTCDateTime,
) -> tuple[PaperOrder, tuple[Fill, ...]]:
    """Process one quote against an acknowledged order, at most once per version."""

    if order.intent_id != intent.intent_id or order.instrument_id != intent.instrument_id:
        raise PaperExecutionError("order/intent binding mismatch")
    if order.status not in (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED):
        raise PaperExecutionError("order is not fill-eligible")
    _validate_market_values(
        instrument_id=intent.instrument_id,
        side=intent.side,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    return _process_acknowledged_order(
        order=order,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )


def submit_paper_exit(
    *,
    intent: ExitIntent,
    position: Position,
    authorization: KernelResult,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: UTCDateTime,
) -> PaperExecutionResult:
    """Execute a deterministic reduction of a known long paper position."""

    if authorization.outcome is not KernelOutcome.ALLOW:
        raise PaperExecutionError("A04 Stage-2 ALLOW is required")
    if compute_payload_hash(intent) != intent.payload_hash:
        raise PaperExecutionError("exit intent payload hash mismatch")
    if compute_payload_hash(position) != position.payload_hash:
        raise PaperExecutionError("position payload hash mismatch")
    if (
        intent.position_id != position.position_id
        or intent.position_version != position.version
        or position.instrument_id != instrument.instrument_id
    ):
        raise PaperExecutionError("exit intent/position/contract binding mismatch")
    if position.status is PositionStatus.CLOSED or position.net_quantity <= 0:
        raise PaperExecutionError("position is not a reducible long position")
    if intent.quantity > position.net_quantity:
        raise PaperExecutionError("exit quantity exceeds known reducible position")
    if intent.quantity % instrument.lot_size != 0:
        raise PaperExecutionError("exit quantity must be an exact lot multiple")
    if (
        instrument.quantity_freeze_limit is not None
        and intent.quantity > instrument.quantity_freeze_limit
    ):
        raise PaperExecutionError("exit quantity exceeds contract freeze limit")
    for price in (intent.limit_price, intent.stop_price):
        if price is not None and price % instrument.tick_size != 0:
            raise PaperExecutionError("exit prices must align to the contract tick size")
    _validate_market_values(
        instrument_id=position.instrument_id,
        side=Side.SELL,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    if market.scenario is PaperSubmissionScenario.TIMEOUT_UNKNOWN:
        return PaperExecutionResult(
            submission_state=PaperSubmissionState.UNKNOWN,
            order=None,
            fills=(),
            reason_codes=("EXIT_SUBMISSION_STATE_UNKNOWN_RECONCILE_REQUIRED",),
        )
    order_id = uuid5(_ORDER_NAMESPACE, f"{intent.exit_intent_id}:{intent.idempotency_key}")
    order = PaperOrder(
        schema_version="1.0",
        paper_order_id=order_id,
        intent_id=intent.exit_intent_id,
        status=(
            PaperOrderStatus.REJECTED
            if market.scenario is PaperSubmissionScenario.REJECT
            else PaperOrderStatus.ACCEPTED
        ),
        instrument_id=position.instrument_id,
        side=Side.SELL,
        quantity=intent.quantity,
        order_type=intent.order_type,
        limit_price=intent.limit_price,
        stop_price=intent.stop_price,
        filled_quantity=Decimal(0),
        average_fill_price=None,
        rejection_reason=market.rejection_reason,
        broker_model_version=policy.broker_model_version,
        accepted_at=evaluation_time,
        updated_at=evaluation_time,
        idempotency_key=intent.idempotency_key,
        version=1,
    )
    if market.scenario is PaperSubmissionScenario.REJECT:
        return PaperExecutionResult(
            submission_state=PaperSubmissionState.REJECTED,
            order=order,
            fills=(),
            reason_codes=("PAPER_EXIT_REJECTED",),
        )
    order, fills = _process_acknowledged_order(
        order=order,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    return PaperExecutionResult(
        submission_state=PaperSubmissionState.ACKNOWLEDGED,
        order=order,
        fills=fills,
        reason_codes=("PAPER_EXIT_ACKNOWLEDGED",),
    )


def _process_acknowledged_order(
    *,
    order: PaperOrder,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: datetime,
) -> tuple[PaperOrder, tuple[Fill, ...]]:
    executable = _executable_price(order, market, instrument.tick_size, policy.slippage_ticks)
    if executable is None:
        return order, ()
    remaining = order.quantity - order.filled_quantity
    top_quantity = market.ask_quantity if order.side is Side.BUY else market.bid_quantity
    assert top_quantity is not None
    liquid = Decimal(top_quantity)
    lots = (min(remaining, liquid) / Decimal(instrument.lot_size)).to_integral_value(
        rounding=ROUND_FLOOR
    )
    fill_quantity = lots * Decimal(instrument.lot_size)
    if fill_quantity <= 0:
        return order, ()
    reference = market.ask if order.side is Side.BUY else market.bid
    assert reference is not None
    notional = executable * fill_quantity
    slippage = abs(executable - reference) * fill_quantity
    fill = Fill(
        schema_version="1.0",
        fill_id=uuid5(_FILL_NAMESPACE, f"{order.paper_order_id}:{order.version}"),
        paper_order_id=order.paper_order_id,
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=fill_quantity,
        price=executable,
        fees=notional * policy.fee_fraction,
        taxes=notional * policy.tax_fraction,
        slippage=slippage,
        cost_model_version=policy.cost_model_version,
        filled_at=evaluation_time,
        idempotency_key=f"{order.idempotency_key}:FILL:{order.version}",
        payload_hash="0" * 64,
    )
    fill = fill.model_copy(update={"payload_hash": compute_payload_hash(fill)})
    new_quantity = order.filled_quantity + fill_quantity
    previous_notional = (
        Decimal(0)
        if order.average_fill_price is None
        else order.average_fill_price * order.filled_quantity
    )
    average = (previous_notional + executable * fill_quantity) / new_quantity
    updated = order.model_copy(
        update={
            "status": (
                PaperOrderStatus.FILLED
                if new_quantity == order.quantity
                else PaperOrderStatus.PARTIALLY_FILLED
            ),
            "filled_quantity": new_quantity,
            "average_fill_price": average,
            "updated_at": evaluation_time,
            "version": order.version + 1,
        }
    )
    return updated, (fill,)


def cancel_paper_order(order: PaperOrder, *, cancelled_at: UTCDateTime) -> PaperOrder:
    if order.status not in (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED):
        raise PaperExecutionError("only open paper orders can be cancelled")
    if cancelled_at < order.updated_at:
        raise PaperExecutionError("cancellation time moved backwards")
    return order.model_copy(
        update={
            "status": PaperOrderStatus.CANCELLED,
            "updated_at": cancelled_at,
            "version": order.version + 1,
        }
    )


def reconcile_unknown_submission(
    *, intent: OrderIntent | ExitIntent, observation: SubmissionObservation
) -> PaperReconciliationResult:
    intent_id = intent.intent_id if isinstance(intent, OrderIntent) else intent.exit_intent_id
    instrument_id = intent.instrument_id if isinstance(intent, OrderIntent) else None
    if observation.state is ObservedSubmissionState.PRESENT:
        assert observation.order is not None
        if (
            observation.order.intent_id != intent_id
            or observation.order.idempotency_key != intent.idempotency_key
            or (instrument_id is not None and observation.order.instrument_id != instrument_id)
        ):
            raise PaperExecutionError("observed order does not match unknown intent")
        return PaperReconciliationResult(
            outcome=ReconciliationOutcome.CONFIRMED_PRESENT,
            order=observation.order,
            retry_permitted=False,
            reason_codes=("UNKNOWN_SUBMISSION_CONFIRMED_PRESENT",),
        )
    if observation.state is ObservedSubmissionState.ABSENT:
        return PaperReconciliationResult(
            outcome=ReconciliationOutcome.CONFIRMED_ABSENT,
            order=None,
            retry_permitted=False,
            reason_codes=("UNKNOWN_SUBMISSION_CONFIRMED_ABSENT",),
        )
    return PaperReconciliationResult(
        outcome=ReconciliationOutcome.STILL_UNKNOWN,
        order=None,
        retry_permitted=False,
        reason_codes=("SUBMISSION_STATE_STILL_UNKNOWN",),
    )


def _validate_boundary(
    *,
    intent: OrderIntent,
    authorization: KernelResult,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: datetime,
) -> None:
    if authorization.outcome is not KernelOutcome.ALLOW:
        raise PaperExecutionError("A04 Stage-2 ALLOW is required")
    if compute_payload_hash(intent) != intent.payload_hash:
        raise PaperExecutionError("order intent payload hash mismatch")
    if intent.side is not Side.BUY:
        raise PaperExecutionError("entry paper execution supports long options only")
    _validate_market_values(
        instrument_id=intent.instrument_id,
        side=intent.side,
        instrument=instrument,
        market=market,
        policy=policy,
        evaluation_time=evaluation_time,
    )
    if intent.quantity % instrument.lot_size != 0:
        raise PaperExecutionError("quantity must be an exact lot multiple")
    for price in (intent.limit_price, intent.stop_price):
        if price is not None and price % instrument.tick_size != 0:
            raise PaperExecutionError("order prices must align to the contract tick size")
    if (
        instrument.quantity_freeze_limit is not None
        and intent.quantity > instrument.quantity_freeze_limit
    ):
        raise PaperExecutionError("quantity exceeds contract freeze limit")


def _validate_market_values(
    *,
    instrument_id: str,
    side: Side,
    instrument: DerivativeInstrument,
    market: PaperMarketFacts,
    policy: PaperExecutionPolicy,
    evaluation_time: datetime,
) -> None:
    if not instrument.tradable or instrument_id != instrument.instrument_id:
        raise PaperExecutionError("intent/contract mismatch or contract not tradable")
    if market.instrument_id != instrument.instrument_id:
        raise PaperExecutionError("market/contract mismatch")
    if market.quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED):
        raise PaperExecutionError("market quality is unsafe")
    age = evaluation_time - market.quote_time
    age_ms = age.days * 86_400_000 + age.seconds * 1_000 + age.microseconds // 1_000
    if market.quote_time > evaluation_time or age_ms > policy.maximum_quote_age_ms:
        raise PaperExecutionError("market quote is stale or from the future")
    if side is Side.BUY:
        if market.ask is None or market.ask_quantity is None:
            raise PaperExecutionError("buy execution requires ask price and quantity")
    elif market.bid is None or market.bid_quantity is None:
        raise PaperExecutionError("sell execution requires bid price and quantity")


def _executable_price(
    order: PaperOrder,
    market: PaperMarketFacts,
    tick_size: Decimal,
    slippage_ticks: int,
) -> Decimal | None:
    reference = market.ask if order.side is Side.BUY else market.bid
    assert reference is not None
    slip = tick_size * slippage_ticks
    price = reference + slip if order.side is Side.BUY else reference - slip
    if price <= 0:
        return None
    if order.order_type is PaperOrderType.MARKET:
        return price
    assert order.limit_price is not None
    if order.order_type is PaperOrderType.STOP_LIMIT:
        assert order.stop_price is not None
        triggered = (
            reference >= order.stop_price
            if order.side is Side.BUY
            else reference <= order.stop_price
        )
        if not triggered:
            return None
    if order.side is Side.BUY and price > order.limit_price:
        return None
    if order.side is Side.SELL and price < order.limit_price:
        return None
    return price


def _order(
    *,
    order_id: UUID,
    intent: OrderIntent,
    status: PaperOrderStatus,
    filled_quantity: Decimal,
    average_fill_price: Decimal | None,
    rejection_reason: str | None,
    policy: PaperExecutionPolicy,
    evaluation_time: datetime,
    version: int,
) -> PaperOrder:
    return PaperOrder(
        schema_version="1.0",
        paper_order_id=order_id,
        intent_id=intent.intent_id,
        status=status,
        instrument_id=intent.instrument_id,
        side=intent.side,
        quantity=intent.quantity,
        order_type=intent.order_type,
        limit_price=intent.limit_price,
        stop_price=intent.stop_price,
        filled_quantity=filled_quantity,
        average_fill_price=average_fill_price,
        rejection_reason=rejection_reason,
        broker_model_version=policy.broker_model_version,
        accepted_at=evaluation_time,
        updated_at=evaluation_time,
        idempotency_key=intent.idempotency_key,
        version=version,
    )


__all__ = [
    "cancel_paper_order",
    "process_paper_order",
    "reconcile_unknown_submission",
    "submit_paper_exit",
    "submit_paper_order",
]
