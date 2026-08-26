from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import (
    RuntimeConfig,
    RuntimeEvent,
    RuntimeEventKind,
    TradingRuntime,
)
from ats.trading_runtime.position_monitor import (
    MonitoredPosition,
    PositionMonitorConfig,
    update_mark,
)


def _calendar() -> SessionCalendar:
    return SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def test_update_mark_pure_function() -> None:
    now = datetime.now(UTC)
    pos = MonitoredPosition(
        position_id="NIFTY:1",
        instrument_id="NIFTY",
        entry_price=Decimal("100"),
        current_mark=Decimal("100"),
        quantity=Decimal("25"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        peak_pnl=Decimal("0"),
        current_stop=None,
        trailing_stop=None,
        time_held_minutes=0,
        entry_thesis_ref=None,
        thesis_healthy=True,
        data_fresh=True,
        last_event="FILL",
        capital_at_risk=Decimal("2500"),
        entry_at=now,
    )

    t1 = now + timedelta(minutes=10)
    updated = update_mark(pos, mark=Decimal("110"), at=t1)
    assert updated.current_mark == Decimal("110")
    assert updated.unrealized_pnl == Decimal("250")  # (110 - 100) * 25
    assert updated.peak_pnl == Decimal("250")
    assert updated.time_held_minutes == 10
    assert updated.last_event == "MARK_UPDATE"

    # Further mark drop keeps peak_pnl
    t2 = now + timedelta(minutes=15)
    dropped = update_mark(updated, mark=Decimal("105"), at=t2)
    assert dropped.current_mark == Decimal("105")
    assert dropped.unrealized_pnl == Decimal("125")
    assert dropped.peak_pnl == Decimal("250")
    assert dropped.time_held_minutes == 15


def test_engine_live_mark_update_triggers_exit() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(
        config=RuntimeConfig(
            calendar=cal,
            position_monitor=PositionMonitorConfig(hard_loss_fraction=Decimal("0.02")),
        ),
        market_feed=feed,
        broker=broker,
    )
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("25"), now)
    assert runtime.state.open_positions["NIFTY:1"].current_mark == Decimal("100")

    # Feed price drops to 95 (5% loss, exceeding 2% hard stop)
    t1 = now + timedelta(minutes=1)
    feed.set_mark("NIFTY", Decimal("95"), t1)
    event = RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=t1)
    result = runtime.process_event(event)

    assert "exits" in result
    assert result["exits"][0]["position_id"] == "NIFTY:1"
    assert "HARD_LOSS_BREACH" in result["exits"][0]["reasons"]
