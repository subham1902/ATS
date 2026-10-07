"""Provider-neutral broker adapter protocol — execution + market data separation.

``PaperBrokerAdapter`` routes order submissions through the canonical
``ats.execution.paper`` broker so that runtime adapters never reimplement the
fill/cost algorithm (slippage, fees, taxes, partial fills, rejection).

The adapter deliberately exposes no manual fill-injection. Writing settlement
state directly was previously possible via a ``seed_fill`` primitive; that
capability now lives outside the production adapter (see
``tests/integration/trading_runtime/paper_fill_seed.py``) so that autonomous
runtime operation cannot build its own fills.
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
from ats.market.domain import InstrumentMetadata
from ats.trading_runtime.lot_size import LotSizeError, LotSizeRegistry

from .position_monitor import MonitoredPosition


class UnboundOrderError(RuntimeError):
    """An order was submitted with no upstream provenance to bind it to.

    Raised rather than papered over: binding an intent to invented policy,
    forecast, risk-decision or token identities is how an unearned order comes
    to look authorized.
    """

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"order {idempotency_key!r} has no intent binding; "
            "cannot build an OrderIntent without real upstream evidence"
        )
        self.idempotency_key = idempotency_key


class BrokerHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OrderIntentBinding:
    """Upstream provenance that a submitted ``OrderIntent`` is bound to.

    Every identity here must reference evidence that **already exists**. The
    runtime may not mint any of them: an order that cannot be traced to a real
    policy, forecast, risk decision, advisory and autonomy token is not
    describable, and the caller must fail closed rather than invent them.

    Risk economics are supplied rather than derived, because a plausible-looking
    tick-derived product is an unearned input to Stage-2 sizing, not a
    measurement.
    """

    policy_id: UUID
    policy_version: int
    forecast_id: UUID
    risk_decision_id: UUID
    supervisor_advisory_id: UUID
    autonomy_token_id: UUID
    maximum_permitted_loss: Decimal
    expected_reward: Decimal
    target_price: Decimal | None = None
    stop_price: Decimal | None = None


@dataclass(frozen=True)
class OrderRequest:
    instrument_id: str
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None
    idempotency_key: str
    intent_id: str
    binding: OrderIntentBinding | None = None


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
        instrument: InstrumentMetadata | None = None,
    ) -> None:
        self._healthy = healthy
        self._lot_size_registry = lot_size_registry
        self._base_slippage_ticks = base_slippage_ticks
        self._tick_size = tick_size
        self._policy = policy
        self._instrument = instrument
        self._orders: dict[str, OrderStatus] = {}
        self._requested_quantities: dict[str, Decimal] = {}
        self._unbound_orders: int = 0
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
        # Entry orders are the ones that need upstream provenance: building an
        # OrderIntent is what mints policy/forecast/risk-decision identities, so
        # refusing here means none are ever fabricated. Exit submissions carry
        # their own authoritative ExitIntent/Position and never build one.
        builds_intent = market_facts is not None and authorization is not None
        if builds_intent and request.binding is None:
            self._unbound_orders += 1
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
            self._orders[order_id] = self._order_status_from_result(order_id, result.order, now)
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
            self._orders[order_id] = self._order_status_from_result(order_id, result.order, now)
            if result.fills:
                self._pending_exit_fills[order_id] = list(result.fills)
        return self._orders[order_id]

    def consume_fills(self, order_id: str) -> tuple[Fill, ...]:
        fills = self._pending_fills.pop(order_id, [])
        return tuple(fills)

    def consume_exit_fills(self, order_id: str) -> tuple[Fill, ...]:
        fills = self._pending_exit_fills.pop(order_id, [])
        return tuple(fills)

    @staticmethod
    def _resolve_target_price(binding: OrderIntentBinding, market: PaperMarketFacts) -> Decimal:
        """Reference price from the binding, else a real quote -- never invented.

        With neither an explicit target nor any market quote there is no price
        evidence, so the intent is unbuildable rather than defaulting to zero.
        """
        if binding.target_price is not None:
            return binding.target_price
        quote = market.ask or market.bid
        if quote is None:
            raise UnboundOrderError("missing target price and market quote")
        return quote

    def _build_order_intent(
        self, request: OrderRequest, now: UTCDateTime, market: PaperMarketFacts
    ) -> OrderIntent:
        binding = request.binding
        if binding is None:  # pragma: no cover - submit_order guards first
            raise UnboundOrderError(request.idempotency_key)
        intent = OrderIntent(
            schema_version="1.0",
            intent_id=UUID(request.intent_id),
            instrument_id=request.instrument_id,
            side=Side(request.side.upper()),
            quantity=request.quantity,
            order_type=_paper_order_type(request.order_type),
            entry_conditions=(),
            limit_price=_as_decimal(request.limit_price),
            stop_price=binding.stop_price,
            target_price=self._resolve_target_price(binding, market),
            maximum_permitted_loss=binding.maximum_permitted_loss,
            expected_reward=binding.expected_reward,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            forecast_id=binding.forecast_id,
            risk_decision_id=binding.risk_decision_id,
            supervisor_advisory_id=binding.supervisor_advisory_id,
            autonomy_token_id=binding.autonomy_token_id,
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

    def _require_instrument(self) -> InstrumentMetadata:
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
