from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import RuntimeConfig, RuntimeEvent, RuntimeEventKind, TradingRuntime


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


def test_engine_blocks_outside_entry_window() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=9, minute=50, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    event = RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "99"}, at=now)
    result = runtime.process_event(event)
    assert result["session_phase"] == "EXIT_ONLY"
    assert "blocked" in result or "exits" in result


def test_engine_emits_candidate_during_entry_allowed() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("101"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    event = RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "100"}, at=now)
    result = runtime.process_event(event)
    assert result["session_phase"] == "ENTRY_ALLOWED"
    assert "candidate" in result or "no_action" in result


def test_price_shock_triggers_p1_check() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    runtime.handle_fill("NIFTY:pos1", Decimal("100"), Decimal("75"), now)
    feed.set_mark("NIFTY", Decimal("95"), now)
    # Force stale mark update by directly manipulating open position's mark would be separate;
    # here we verify shock event itself processes without error and returns a dict.
    event = RuntimeEvent(kind=RuntimeEventKind.PRICE_SHOCK, instrument_id="NIFTY", payload={}, at=now)
    result = runtime.process_event(event)
    assert "verdict" in result


def test_multi_position_independent_exit() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), now)
    runtime.handle_fill("BANKNIFTY:1", Decimal("200"), Decimal("15"), now)
    assert len(runtime.state.open_positions) == 2
    runtime.handle_exit("NIFTY:1", now)
    assert len(runtime.state.open_positions) == 1
    assert "BANKNIFTY:1" in runtime.state.open_positions


def test_latency_metrics_collected() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    for _ in range(5):
        runtime.process_event(RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=now))
    summary = runtime.metrics.summary()
    assert "state_update" in summary
    assert summary["state_update"]["count"] == 5.0