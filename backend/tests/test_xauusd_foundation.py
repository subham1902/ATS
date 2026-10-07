"""Causal live/replay observations, unknown fields and honest terminal health."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.console.app import create_console_app
from ats.market.domain import UnsupportedInstrument, XauUsdDomain, require_xauusd
from ats.market.fabric import BarInterval, MarketDataFabric, PublishOutcome
from ats.market.metatrader.connector import FeedState, MetaTraderConnector
from ats.market.observations import MarketObservation, VolumeProvenance
from ats.trading_runtime.startup import preflight
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


class Clock:
    def now(self):
        return NOW


class FakeTransport:
    connected = True
    tick = {"time_msc": int(NOW.timestamp() * 1000), "bid": 2300, "ask": 2300.3}

    def initialize(self):
        return self.connected

    def symbol_info(self, symbol):
        return {
            "name": symbol,
            "digits": 2,
            "point": 0.01,
            "trade_tick_size": 0.01,
            "trade_contract_size": 100,
            "volume_min": 0.01,
            "volume_max": 100,
            "volume_step": 0.01,
            "trade_mode": 4,
        }

    def latest_tick(self, symbol):
        return self.tick

    def shutdown(self):
        pass


@pytest.mark.parametrize("symbol", ["EURUSD", "GBPUSD", "BTCUSD", "NIFTY", "GOLDM"])
def test_single_instrument(symbol):
    with pytest.raises(UnsupportedInstrument):
        require_xauusd(symbol)


def test_symbol_mapping_missing_fields_and_stale_health():
    source = FakeTransport()
    connector = MetaTraderConnector(XauUsdDomain(broker_symbol="GOLD"), source, clock=lambda: NOW)
    assert connector.connect()
    observation = connector.latest_tick()
    assert observation.canonical_symbol == "XAUUSD"
    assert observation.broker_symbol == "GOLD"
    assert observation.volume is observation.tick_volume is observation.real_volume is None
    assert observation.provenance == "BROKER_TICK_PROXY"
    assert connector.health()["state"] == "LIVE"
    connector.clock = lambda: NOW + timedelta(seconds=30)
    assert connector.health()["state"] == "STALE"
    connector.shutdown()
    assert connector.health()["state"] == "DISCONNECTED"
    assert connector.reconnect()


@pytest.mark.parametrize(
    "tick",
    [
        None,
        {"bid": -1},
        {"time": NOW.timestamp(), "bid": 2301, "ask": 2300},
        {"time": (NOW + timedelta(hours=3)).timestamp(), "bid": 2300},
    ],
)
def test_malformed_missing_future_ticks_stay_degraded(tick):
    source = FakeTransport()
    source.tick = tick
    connector = MetaTraderConnector(XauUsdDomain(), source, clock=lambda: NOW)
    assert connector.connect()
    assert connector.latest_tick() is None
    assert connector.health()["state"] == "DEGRADED"


def test_connection_failure_and_wrong_symbol():
    source = FakeTransport()
    source.connected = False
    connector = MetaTraderConnector(XauUsdDomain(), source)
    assert not connector.connect()
    assert connector.state == FeedState.ERROR
    source.connected = True
    source.symbol_info = lambda symbol: {"name": "EURUSD"}
    assert not connector.connect()


def test_tick_volume_never_becomes_real_volume():
    source = FakeTransport()
    source.tick = {**FakeTransport.tick, "tick_volume": 20}
    connector = MetaTraderConnector(XauUsdDomain(), source, clock=lambda: NOW)
    assert connector.connect()
    tick = connector.latest_tick()
    assert tick.volume_provenance == VolumeProvenance.TICK_VOLUME
    assert tick.real_volume is None


def test_future_bar_rejection_is_atomic_and_replay_bar_is_not_a_tick():
    fabric = MarketDataFabric(clock=Clock())
    bar = MarketObservation(
        broker_symbol="XAUUSD",
        timestamp=NOW,
        received_at=NOW,
        source="DATASET",
        timeframe="5m",
        open=Decimal(2300),
        high=Decimal(2301),
        low=Decimal(2299),
        close=Decimal(2300),
    )
    with pytest.raises(ValueError, match="NOT_YET_AVAILABLE"):
        fabric.publish(bar)
    assert fabric.latest("XAUUSD") is None
    assert fabric.counters().accepted == 0
    assert fabric.bars("XAUUSD", BarInterval.M5) == ()
    closed = bar.model_copy(update={"timestamp": NOW - timedelta(minutes=5)})
    assert fabric.publish(closed) == PublishOutcome.ACCEPTED
    assert fabric.bars("XAUUSD", BarInterval.M5)[0].is_closed
    assert fabric.bars("XAUUSD", BarInterval.M1) == ()


def test_fabric_dedup_quote_bars_footprint_and_http():
    connector = MetaTraderConnector(XauUsdDomain(), FakeTransport(), clock=lambda: NOW)
    assert connector.connect()
    tick = connector.latest_tick()
    fabric = MarketDataFabric(clock=Clock())
    fabric.tick_size = connector.metadata.tick_size
    assert fabric.publish(tick) == PublishOutcome.ACCEPTED
    assert fabric.publish(tick) == PublishOutcome.DROPPED_DUPLICATE
    assert fabric.bars("XAUUSD", BarInterval.M5)[0].volume is None
    assert fabric.footprint()["provenance"] == "BROKER_TICK_PROXY"
    client = TestClient(create_console_app(fabric=fabric, connector=connector))
    quote = client.get("/v1/market/quote").json()
    assert quote["bid_price"] == "2300"
    assert quote["last_price"] is None
    assert quote["bid_quantity"] is None
    assert client.get("/v1/market/quote?instrument=EURUSD").status_code == 422


def test_offline_startup_preserves_paper_authority_and_ignores_old_credentials(monkeypatch):
    monkeypatch.setenv("ATS_OFFLINE_RESEARCH", "1")
    monkeypatch.setenv("ATS_UPSTOX_ACCESS_TOKEN", "irrelevant")
    report = preflight()
    assert report["canonical_symbol"] == "XAUUSD"
    assert report["provider"] == "MT5"
    assert report["execution_destination"] == "PaperBroker"
    monkeypatch.setenv("LIVE_MONEY", "TRUE")
    with pytest.raises(ValueError, match="PAPER_ONLY"):
        preflight()
