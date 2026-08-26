from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import (
    RuntimeConfig,
    RuntimeEvent,
    RuntimeEventKind,
    TradingRuntime,
)
from ats.trading_runtime.hwm import HWMState, ProfitProtectionState
from ats.trading_runtime.modes import TradingMode


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


def test_safe_mode_position_cap() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    feed.set_mark("NIFTY", Decimal("103"), now)

    # In SAFE mode, max_concurrent_positions = 1
    runtime = TradingRuntime(
        config=RuntimeConfig(calendar=cal, mode=TradingMode.SAFE),
        market_feed=feed,
        broker=broker,
    )
    # Fill 1 position
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("25"), now)

    # Attempting to enter another position on new bar is blocked
    event = RuntimeEvent(
        kind=RuntimeEventKind.BAR,
        instrument_id="NIFTY",
        payload={"previous_close": "100"},
        at=now,
    )
    result = runtime.process_event(event)
    assert "mode_blocked" in result
    assert "MODE_MAX_CONCURRENT_POSITIONS" in result["mode_blocked"]


def test_hwm_drawdown_deescalation_to_safe() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    feed.set_mark("NIFTY", Decimal("103"), now)

    runtime = TradingRuntime(
        config=RuntimeConfig(calendar=cal, mode=TradingMode.AGGRESSIVE),
        market_feed=feed,
        broker=broker,
    )
    # Simulate HWM state with drawdown mode_hint = SAFE
    runtime.state.hwm_state = HWMState(
        session_start_equity=Decimal("100000"),
        peak_equity=Decimal("100000"),
        current_equity=Decimal("95000"),
        drawdown_fraction=Decimal("0.05"),
        peak_profit=Decimal("0"),
        giveback_from_peak=Decimal("5000"),
        profit_protection=ProfitProtectionState.NONE,
        mode_hint=TradingMode.SAFE,
    )
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("25"), now)

    # De-escalated to SAFE, so max positions = 1 (blocked from entering 2nd position)
    event = RuntimeEvent(
        kind=RuntimeEventKind.BAR,
        instrument_id="NIFTY",
        payload={"previous_close": "100"},
        at=now,
    )
    result = runtime.process_event(event)
    assert "mode_blocked" in result
    assert "MODE_MAX_CONCURRENT_POSITIONS" in result["mode_blocked"]
    assert runtime.state.mode_state is not None
    assert runtime.state.mode_state.effective == TradingMode.SAFE
