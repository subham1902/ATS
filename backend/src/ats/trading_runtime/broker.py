"""Provider-neutral broker adapter protocol — execution + market data separation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from ats.contracts.common import UTCDateTime

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

    def __init__(self, *, healthy: bool = True) -> None:
        self._healthy = healthy
        self._orders: dict[str, OrderStatus] = {}
        self._requested_quantities: dict[str, Decimal] = {}
        self._positions: dict[str, PositionSnapshot] = {}

    def health(self) -> BrokerHealth:
        return BrokerHealth.HEALTHY if self._healthy else BrokerHealth.UNHEALTHY

    def is_healthy(self) -> bool:
        return self._healthy

    def submit_order(self, request: OrderRequest, *, now: UTCDateTime) -> OrderStatus | None:
        if not self._healthy:
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
        return status

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
