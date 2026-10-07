"""Synthetic broker metadata for execution mechanics, never research evidence."""

from datetime import UTC, datetime
from decimal import Decimal

from ats.market.domain import InstrumentMetadata

AS_OF = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def instrument() -> InstrumentMetadata:
    return InstrumentMetadata(
        broker_symbol="XAUUSD.test",
        digits=2,
        point=Decimal("0.01"),
        tick_size=Decimal("0.05"),
        contract_size=Decimal("1"),
        volume_min=Decimal("65"),
        volume_max=Decimal("1800"),
        volume_step=Decimal("65"),
        trade_mode=4,
        as_of_time=AS_OF,
        source="MT5",
    )
