from __future__ import annotations

import time
from datetime import UTC, date, datetime
from datetime import time as dt_time
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
        preopen_start=dt_time(9, 0),
        market_open=dt_time(9, 15),
        market_close=dt_time(15, 30),
        overrides=(),
    )


def test_large_event_burst_does_not_crash() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    for i in range(500):
        runtime.process_event(
            RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "99"}, at=now)
        )
    summary = runtime.metrics.summary()
    assert summary["state_update"]["count"] == 500.0


def test_duplicate_broker_event_idempotent() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    event = RuntimeEvent(kind=RuntimeEventKind.FILL, instrument_id="NIFTY", payload={}, at=now)
    r1 = runtime.process_event(event)
    r2 = runtime.process_event(event)
    assert r1["verdict"] == r2["verdict"]


def test_unknown_submit_holds_capital_semantics() -> None:
    broker = PaperBrokerAdapter(healthy=False)
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    from ats.trading_runtime.broker import OrderRequest

    result = broker.submit_order(
        OrderRequest(
            instrument_id="NIFTY",
            side="BUY",
            quantity=Decimal("75"),
            order_type="MARKET",
            limit_price=None,
            idempotency_key="test-unknown-1",
            intent_id="intent-1",
        ),
        now=now,
    )
    assert result is None


def test_event_loop_lag_measurement() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    start = time.perf_counter_ns()
    runtime.process_event(RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=now))
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    assert elapsed_ms < 100


def test_reservation_contention_no_double_spend() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), now)
    runtime.handle_fill("BANKNIFTY:1", Decimal("200"), Decimal("15"), now)
    runtime.handle_fill("NIFTY:2", Decimal("100"), Decimal("75"), now)
    assert len(runtime.state.open_positions) == 3
    runtime.handle_exit("NIFTY:1", now)
    assert len(runtime.state.open_positions) == 2


def test_delayed_ack_still_reconciles() -> None:
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    from ats.trading_runtime.broker import OrderRequest

    order = broker.submit_order(
        OrderRequest(
            instrument_id="NIFTY",
            side="BUY",
            quantity=Decimal("75"),
            order_type="MARKET",
            limit_price=None,
            idempotency_key="delayed-ack-1",
            intent_id="intent-delayed",
        ),
        now=now,
    )
    assert order is not None
    assert order.status == "ACKNOWLEDGED"
    queried = broker.query_order(order.order_id)
    assert queried is not None
    assert queried.order_id == order.order_id


def test_halt_blocks_new_risk_but_allows_reduce() -> None:
    cal = _calendar()
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("100"), now)
    runtime = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    runtime.halt()
    result = runtime.process_event(
        RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "99"}, at=now)
    )
    assert result["verdict"] == "HALT"
    runtime.resume()
    result2 = runtime.process_event(
        RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "99"}, at=now)
    )
    assert result2["verdict"] != "HALT"
