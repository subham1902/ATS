"""Unit and integration tests for MarketDataFabric and market distribution endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ats.console.app import create_console_app
from ats.market.fabric import (
    BarInterval,
    MarketDataFabric,
    PublishOutcome,
)
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate, UpdateKind
from fastapi.testclient import TestClient


def _make_update(
    instrument_key: str = "MCX_FO|569003",
    price: Decimal = Decimal("72500.00"),
    timestamp: datetime | None = None,
    volume: int = 150,
    open_interest: int = 1200,
) -> NormalizedFeedUpdate:
    ts = timestamp or datetime.now(UTC)
    return NormalizedFeedUpdate(
        instrument_key=instrument_key,
        kind=UpdateKind.INDEX,
        last_traded_price=price,
        exchange_timestamp=ts,
        received_at=ts,
        volume=volume,
        open_interest=open_interest,
    )



def test_fabric_publish_dedup_and_ooo() -> None:
    fabric = MarketDataFabric(source_label="UPSTOX_V3", authority_class="LIVE_FEED_ATTACHED")
    now = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)

    u1 = _make_update(price=Decimal("72500.00"), timestamp=now)
    outcome1 = fabric.publish(u1)
    assert outcome1 == PublishOutcome.ACCEPTED
    assert fabric.counters().accepted == 1

    # Duplicate tick (same key, same timestamp)
    outcome_dup = fabric.publish(u1)
    assert outcome_dup == PublishOutcome.DROPPED_DUPLICATE
    assert fabric.counters().dropped_duplicate == 1

    # Out of order tick (earlier timestamp)
    earlier = now - timedelta(seconds=10)
    u_ooo = _make_update(price=Decimal("72490.00"), timestamp=earlier)
    outcome_ooo = fabric.publish(u_ooo)
    assert outcome_ooo == PublishOutcome.DROPPED_OUT_OF_ORDER
    assert fabric.counters().dropped_out_of_order == 1

    # Later tick
    later = now + timedelta(seconds=5)
    u_later = _make_update(price=Decimal("72510.00"), timestamp=later)
    assert fabric.publish(u_later) == PublishOutcome.ACCEPTED
    assert fabric.counters().accepted == 2


class TestClock:
    __test__ = False
    def __init__(self, current_time: datetime) -> None:
        self._current_time = current_time

    def now(self) -> datetime:
        return self._current_time

    def advance(self, delta: timedelta) -> None:
        self._current_time += delta


def test_fabric_bar_assembly_5m_15m_1h() -> None:
    base_ts = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)
    clock = TestClock(base_ts + timedelta(seconds=100))
    fabric = MarketDataFabric(clock=clock)

    # Publish ticks within the same 5m bar
    t1 = _make_update(price=Decimal("100.0"), timestamp=base_ts, volume=10)
    t2 = _make_update(price=Decimal("105.0"), timestamp=base_ts + timedelta(seconds=30), volume=20)
    t3 = _make_update(price=Decimal("98.0"), timestamp=base_ts + timedelta(seconds=60), volume=30)
    t4 = _make_update(price=Decimal("102.0"), timestamp=base_ts + timedelta(seconds=90), volume=40)

    fabric.publish(t1)
    fabric.publish(t2)
    fabric.publish(t3)
    fabric.publish(t4)

    bars_5m = fabric.bars("MCX_FO|569003", BarInterval.M5)
    assert len(bars_5m) == 1
    current_5m = bars_5m[0]
    assert current_5m.open == Decimal("100.0")
    assert current_5m.high == Decimal("105.0")
    assert current_5m.low == Decimal("98.0")
    assert current_5m.close == Decimal("102.0")
    assert current_5m.volume == 40
    assert current_5m.tick_count == 4
    assert not current_5m.is_closed

    # Cross 5m boundary into next bar
    clock.advance(timedelta(seconds=210))
    t5 = _make_update(price=Decimal("103.0"), timestamp=base_ts + timedelta(seconds=305), volume=50)
    fabric.publish(t5)

    bars_5m_after = fabric.bars("MCX_FO|569003", BarInterval.M5)
    assert len(bars_5m_after) == 2
    assert bars_5m_after[0].is_closed
    assert bars_5m_after[0].close == Decimal("102.0")
    assert not bars_5m_after[1].is_closed
    assert bars_5m_after[1].open == Decimal("103.0")


    # Verify 15m and 1h bars encompass the moves
    bars_15m = fabric.bars("MCX_FO|569003", BarInterval.M15)
    assert len(bars_15m) == 1
    assert bars_15m[0].high == Decimal("105.0")
    assert bars_15m[0].low == Decimal("98.0")

    bars_1h = fabric.bars("MCX_FO|569003", BarInterval.H1)
    assert len(bars_1h) == 1
    assert bars_1h[0].high == Decimal("105.0")
    assert bars_1h[0].low == Decimal("98.0")


def test_market_api_endpoints() -> None:
    fabric = MarketDataFabric(source_label="TEST_UPSTOX")
    app = create_console_app(fabric=fabric)
    client = TestClient(app)

    # 1. Health endpoint
    res_health = client.get("/v1/market/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["attached"] is True
    assert health_data["source"] == "TEST_UPSTOX"

    # 2. Quote endpoint before any ticks
    res_quote_unresolved = client.get("/v1/market/quote")
    assert res_quote_unresolved.status_code == 200
    assert res_quote_unresolved.json()["state"] == "NO_FEED"

    # Publish a live tick
    now = datetime.now(UTC)
    tick = _make_update(instrument_key="MCX_FO|GOLDM", price=Decimal("72600.00"), timestamp=now)
    fabric.publish(tick)

    # Quote endpoint after tick
    res_quote = client.get("/v1/market/quote?instrument=MCX_FO|GOLDM")
    assert res_quote.status_code == 200
    quote_data = res_quote.json()
    assert quote_data["state"] == "LIVE"
    assert quote_data["last_price"] == "72600.00"

    # 3. Snapshot endpoint
    res_snap = client.get("/v1/market/snapshot?instrument=MCX_FO|GOLDM")
    assert res_snap.status_code == 200
    snap_data = res_snap.json()
    assert snap_data["state"] == "LIVE"
    assert snap_data["last_price"] == "72600.00"
    assert snap_data["market_session"] == "MCX_REGULAR"

    # 4. Candles endpoint (historical + live stitch)
    res_candles = client.get("/v1/market/candles?instrument=MCX_FO|GOLDM&interval=5m")
    assert res_candles.status_code == 200
    candles_data = res_candles.json()
    assert candles_data["state"] == "LIVE"
    assert len(candles_data["candles"]) > 0

    # 5. Runtime status endpoint returns 200 with truthful default
    res_runtime = client.get("/v1/runtime/status")
    assert res_runtime.status_code == 200
    runtime_data = res_runtime.json()
    assert runtime_data["session"]["phase"] == "CLOSED"
    assert runtime_data["feed_healthy"] is True
    assert runtime_data["broker_healthy"] is True
