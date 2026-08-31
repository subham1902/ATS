"""Provider-neutral broker adapter protocol — execution + market data separation.

``PaperBrokerAdapter`` routes order submissions through the canonical
``ats.execution.paper`` broker so that runtime adapters never reimplement the
fill/cost algorithm (slippage, fees, taxes, partial fills, rejection).
Autonomous operation must not depend on the manual ``seed_fill`` primitive;
it exists only as a test/debug escape hatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import ExitIntent, Fill, OrderIntent, PaperOrder, Position
from ats.contracts.domain.types import (
    PaperOrderType,
    Side,
)
from ats.execution.paper.broker import (
    submit_paper_order,
)
from ats.execution.paper.models import (
    PaperExecutionPolicy,
    PaperMarketFacts,
)
from ats.kernel.types import KernelResult
from ats.market.derivatives.contract_master import DerivativeInstrument
from ats.trading_runtime.lot_size import LotSizeError, LotSizeRegistry

from .position_monitor import MonitoredPosition


class BrokerHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OrderRequest:
    instrument_id: str
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None
    idempotency_key: str
    intent_id: str


@dataclass(frozen=True)
class OrderStatus:
    order_id: str
    status: str
    filled_quantity: Decimal
    average_price: Decimal | None
    updated_at: UTCDateTime
    idempotency_key: str


@dataclass(frozen=True)
class PositionSnapshot:
    instrument_id: str
    quantity: Decimal
    average_price: Decimal
    mark_price: Decimal


class MarketDataFeed(Protocol):
    def latest_mark(self, instrument_id: str) -> Decimal | None: ...

    def data_fresh(self, instrument_id: str, *, now: UTCDateTime, max_age_ms: int) -> bool: ...

    def is_healthy(self) -> bool: ...


class ExecutionBroker(Protocol):
    def submit_order(self, request: OrderRequest, *, now: UTCDateTime) -> OrderStatus | None: ...

    def query_order(self, order_id: str) -> OrderStatus | None: ...

    def cancel_order(self, order_id: str, *, now: UTCDateTime) -> OrderStatus | None: ...

    def query_open_orders(self) -> tuple[OrderStatus, ...]: ...

    def query_positions(self) -> tuple[PositionSnapshot, ...]: ...

    def health(self) -> BrokerHealth: ...

    def is_healthy(self) -> bool: ...


class InMemoryMarketFeed:
    def __init__(self) -> None:
        self._marks: dict[str, tuple[Decimal, UTCDateTime]] = {}
        self._healthy = True

    def set_mark(self, instrument_id: str, price: Decimal, at: UTCDateTime) -> None:
        self._marks[instrument_id] = (price, at)

    def latest_mark(self, instrument_id: str) -> Decimal | None:
        entry = self._marks.get(instrument_id)
        return None if entry is None else entry[0]

    def data_fresh(self, instrument_id: str, *, now: UTCDateTime, max_age_ms: int) -> bool:
        entry = self._marks.get(instrument_id)
        if entry is None:
            return False
        _, at = entry
        age_ms = int((now - at).total_seconds() * 1000)
        return 0 <= age_ms <= max_age_ms

    def is_healthy(self) -> bool:
        return self._healthy

    def set_healthy(self, healthy: bool) -> None:
        self._healthy = healthy


class PaperBrokerAdapter:
    """Thin adapter wrapping existing ats.execution.paper broker for runtime use."""

    def __init__(
        self,
        *,
        healthy: bool = True,
        lot_size_registry: LotSizeRegistry | None = None,
        base_slippage_ticks: int = 0,
        tick_size: Decimal = Decimal("0.05"),
        policy: PaperExecutionPolicy | None = None,
        instrument: DerivativeInstrument | None = None,
    ) -> None:
        self._healthy = healthy
        self._lot_size_registry = lot_size_registry
        self._base_slippage_ticks = base_slippage_ticks
        self._tick_size = tick_size
        self._policy = policy
        self._instrument = instrument
        self._orders: dict[str, OrderStatus] = {}
        self._requested_quantities: dict[str, Decimal] = {}
        self._positions: dict[str, PositionSnapshot] = {}
        self._pending_fills: dict[str, list[Fill]] = {}
        self._pending_exit_fills: dict[str, list[Fill]] = {}

    def health(self) -> BrokerHealth:
        return BrokerHealth.HEALTHY if self._healthy else BrokerHealth.UNHEALTHY

    def is_healthy(self) -> bool:
        return self._healthy

    def apply_slippage(self, price: Decimal, side: str) -> Decimal:
        """Apply realistic slippage (in ticks) to a requested limit/market price."""
        if self._base_slippage_ticks <= 0:
            return price
        slippage_amt = Decimal(self._base_slippage_ticks) * self._tick_size
        if side.upper() in ("BUY", "LONG"):
            return price + slippage_amt
        return max(Decimal("0.05"), price - slippage_amt)

    def submit_order(
        self,
        request: OrderRequest,
        *,
        now: UTCDateTime,
        market_facts: PaperMarketFacts | None = None,
        authorization: KernelResult | None = None,
    ) -> OrderStatus | None:
        if not self._healthy:
            return None
        if self._lot_size_registry is not None:
            try:
                self._lot_size_registry.validate_quantity(request.instrument_id, request.quantity)
            except LotSizeError:
                return None
        order_id = f"paper-{request.idempotency_key}"
        if order_id in self._orders:
            return self._orders[order_id]
        status = OrderStatus(
            order_id=order_id,
            status="ACKNOWLEDGED",
            filled_quantity=Decimal("0"),
            average_price=None,
            updated_at=now,
            idempotency_key=request.idempotency_key,
        )
        self._orders[order_id] = status
        self._requested_quantities[order_id] = request.quantity

        if market_facts is not None and authorization is not None:
            intent = self._build_order_intent(request, now, market_facts)
            result = submit_paper_order(
                intent=intent,
                authorization=authorization,
                instrument=self._require_instrument(),
                market=market_facts,
                policy=self._require_policy(),
                evaluation_time=now,
            )
            self._orders[order_id] = self._order_status_from_result(
                order_id, result.order, now
            )
            if result.fills:
                self._pending_fills[order_id] = list(result.fills)
        return self._orders[order_id]

    def submit_exit(
        self,
        *,
        request: OrderRequest,
        intent: ExitIntent,
        position: Position,
        now: UTCDateTime,
        market_facts: PaperMarketFacts | None = None,
        authorization: KernelResult | None = None,
    ) -> OrderStatus | None:
        if not self._healthy:
            return None
        order_id = f"paper-exit-{request.idempotency_key}"
        if order_id in self._orders:
            return self._orders[order_id]
        status = OrderStatus(
            order_id=order_id,
            status="ACKNOWLEDGED",
            filled_quantity=Decimal("0"),
            average_price=None,
            updated_at=now,
            idempotency_key=request.idempotency_key,
        )
        self._orders[order_id] = status
        self._requested_quantities[order_id] = request.quantity
        if market_facts is not None and authorization is not None:
            from ats.execution.paper.broker import submit_paper_exit

            result = submit_paper_exit(
                intent=intent,
                position=position,
                authorization=authorization,
                instrument=self._require_instrument(),
                market=market_facts,
                policy=self._require_policy(),
                evaluation_time=now,
            )
            self._orders[order_id] = self._order_status_from_result(
                order_id, result.order, now
            )
            if result.fills:
                self._pending_exit_fills[order_id] = list(result.fills)
        return self._orders[order_id]

    def consume_fills(self, order_id: str) -> tuple[Fill, ...]:
        fills = self._pending_fills.pop(order_id, [])
        return tuple(fills)

    def consume_exit_fills(self, order_id: str) -> tuple[Fill, ...]:
        fills = self._pending_exit_fills.pop(order_id, [])
        return tuple(fills)

    def _build_order_intent(
        self, request: OrderRequest, now: UTCDateTime, market: PaperMarketFacts
    ) -> OrderIntent:
        instrument = self._require_instrument()
        intent = OrderIntent(
            schema_version="1.0",
            intent_id=UUID(request.intent_id) if request.intent_id else UUID(int=0),
            instrument_id=request.instrument_id,
            side=Side(request.side.upper()),
            quantity=request.quantity,
            order_type=_paper_order_type(request.order_type),
            entry_conditions=(),
            limit_price=_as_decimal(request.limit_price),
            stop_price=None,
            target_price=market.ask or market.bid or Decimal("0"),
            maximum_permitted_loss=instrument.lot_size * instrument.tick_size * 10,
            expected_reward=instrument.lot_size * instrument.tick_size * 10,
            policy_id=UUID(int=1),
            policy_version=1,
            forecast_id=UUID(int=2),
            risk_decision_id=UUID(int=3),
            supervisor_advisory_id=UUID(int=4),
            autonomy_token_id=UUID(int=5),
            idempotency_key=request.idempotency_key,
            created_at=now,
            payload_hash="0" * 64,
        )
        from ats.contracts.domain.hashing import compute_payload_hash

        return intent.model_copy(update={"payload_hash": compute_payload_hash(intent)})

    def _order_status_from_result(
        self, order_id: str, result: PaperOrder | None, now: UTCDateTime
    ) -> OrderStatus:
        existing = self._orders[order_id]
        if result is None:
            return existing
        from ats.contracts.domain.types import PaperOrderStatus

        if result.status is PaperOrderStatus.REJECTED:
            return OrderStatus(
                order_id=order_id,
                status="REJECTED",
                filled_quantity=Decimal("0"),
                average_price=None,
                updated_at=now,
                idempotency_key=existing.idempotency_key,
            )
        if result.status is PaperOrderStatus.FILLED:
            return OrderStatus(
                order_id=order_id,
                status="FILLED",
                filled_quantity=result.filled_quantity,
                average_price=result.average_fill_price,
                updated_at=now,
                idempotency_key=existing.idempotency_key,
            )
        if result.status is PaperOrderStatus.PARTIALLY_FILLED:
            return OrderStatus(
                order_id=order_id,
                status="PARTIALLY_FILLED",
                filled_quantity=result.filled_quantity,
                average_price=result.average_fill_price,
                updated_at=now,
                idempotency_key=existing.idempotency_key,
            )
        return existing

    def _require_instrument(self) -> DerivativeInstrument:
        if self._instrument is None:
            raise RuntimeError("PaperBrokerAdapter requires instrument for canonical fills")
        return self._instrument

    def _require_policy(self) -> PaperExecutionPolicy:
        if self._policy is None:
            raise RuntimeError("PaperBrokerAdapter requires policy for canonical fills")
        return self._policy

    def query_order(self, order_id: str) -> OrderStatus | None:
        return self._orders.get(order_id)

    def cancel_order(self, order_id: str, *, now: UTCDateTime) -> OrderStatus | None:
        existing = self._orders.get(order_id)
        if existing is None:
            return None
        updated = OrderStatus(
            order_id=existing.order_id,
            status="CANCELLED",
            filled_quantity=existing.filled_quantity,
            average_price=existing.average_price,
            updated_at=now,
            idempotency_key=existing.idempotency_key,
        )
        self._orders[order_id] = updated
        return updated

    def query_open_orders(self) -> tuple[OrderStatus, ...]:
        ack = "ACKNOWLEDGED"
        part = "PARTIALLY_FILLED"
        return tuple(v for v in self._orders.values() if v.status in (ack, part))

    def query_positions(self) -> tuple[PositionSnapshot, ...]:
        return tuple(self._positions.values())

    def seed_fill(
        self, order_id: str, average_price: Decimal, filled_quantity: Decimal, now: UTCDateTime
    ) -> None:
        existing = self._orders.get(order_id)
        if existing is None:
            return
        self._orders[order_id] = OrderStatus(
            order_id=existing.order_id,
            status=(
                "FILLED"
                if filled_quantity == self._requested_quantities[order_id]
                else "PARTIALLY_FILLED"
            ),
            filled_quantity=filled_quantity,
            average_price=average_price,
            updated_at=now,
            idempotency_key=existing.idempotency_key,
        )

    def monitored_positions(self) -> tuple[MonitoredPosition, ...]:
        return ()


__all__ = [
    "BrokerHealth",
    "ExecutionBroker",
    "InMemoryMarketFeed",
    "MarketDataFeed",
    "OrderRequest",
    "OrderStatus",
    "PaperBrokerAdapter",
    "PositionSnapshot",
]


def _paper_order_type(value: str) -> PaperOrderType:
    return PaperOrderType(value.upper())


def _as_decimal(value: Decimal | None) -> Decimal | None:
    return value
