"""Manual paper fill seeding, available to tests only.

The production ``PaperBrokerAdapter`` deliberately has no way to write
settlement state directly: an autonomous runtime that can mint its own fills can
manufacture the appearance of executed authority. Settlement is supposed to come
from the canonical paper execution result and nothing else.

Durability tests need to force intermediate states (partial fills, fills
recorded after a simulated restart), so that capability lives here, outside the
production package. Importing this module from ``ats.trading_runtime`` fails by
design, and a source-scanning guard in
``tests/contract/trading_runtime`` keeps it that way.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from ats.contracts.common import UTCDateTime
from ats.trading_runtime.broker import OrderStatus


class _SeedablePaperBroker(Protocol):
    """Structural view of just the state tests are allowed to rewrite."""

    _orders: dict[str, OrderStatus]
    _requested_quantities: dict[str, Decimal]


def seed_fill(
    broker: Any,
    order_id: str,
    average_price: Decimal,
    filled_quantity: Decimal,
    now: UTCDateTime,
) -> None:
    """Force a known settlement state onto an already-submitted order.

    Mirrors what ``PaperBrokerAdapter`` used to do for itself, but reaches into
    the adapter's private state from test code only. Nothing in
    ``backend/src`` calls this.
    """
    view: _SeedablePaperBroker = broker  # type: ignore[assignment]
    existing = view._orders.get(order_id)
    if existing is None:
        return
    view._orders[order_id] = OrderStatus(
        order_id=existing.order_id,
        status=(
            "FILLED" if filled_quantity == view._requested_quantities[order_id] else "PARTIALLY_FILLED"
        ),
        filled_quantity=filled_quantity,
        average_price=average_price,
        updated_at=now,
        idempotency_key=existing.idempotency_key,
    )


__all__ = ["seed_fill"]
