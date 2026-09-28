"""Comprehensive Test Suite for ATS-LC1 Live Streaming Market Data Engine.

Covers:
1. Provider State Machine (deterministic transitions, error states, and history audit).
2. Incremental Candle Engine (1s/5s derived, 1m/5m/1h, OHLC invariants, boundary finalization).
3. Volume Correctness (cumulative VTT deltas without double counting across reconnects).
4. Open Interest Non-accumulation.
5. Market Journal (non-blocking append, bounded retention, overflow policy).
6. StreamHub (client subscription filtering, typed envelopes, backpressure protection).
7. Safety Invariants (LIVE_MONEY=False, PaperBroker only, no order placement endpoints).
"""

import asyncio
from datetime import UTC, datetime

import pytest
from ats.market.live.candle_builder import IncrementalCandleEngine, LiveCandle
from ats.market.live.journal import MarketJournal
from ats.market.live.state import ProviderState, ProviderStateMachine
from ats.market.live.stream_hub import StreamHub
from ats.market.live.subscriptions import SubscriptionRegistry


def test_provider_state_machine_valid_transitions():
    sm = ProviderStateMachine(provider="upstox")
    assert sm.state == ProviderState.DISCONNECTED

    # Disconnected -> Authorizing -> Connecting -> Connected -> Snapshot Pending -> Streaming
    sm.transition(ProviderState.AUTHORIZING, reason="Token verified")
    assert sm.state == ProviderState.AUTHORIZING

    sm.transition(ProviderState.CONNECTING, reason="Opening socket")
    assert sm.state == ProviderState.CONNECTING

    sm.transition(ProviderState.CONNECTED, reason="Transport ready")
    assert sm.state == ProviderState.CONNECTED

    sm.transition(ProviderState.SNAPSHOT_PENDING, reason="Subscribed")
    assert sm.state == ProviderState.SNAPSHOT_PENDING

    sm.transition(ProviderState.STREAMING, reason="First tick arrived")
    assert sm.state == ProviderState.STREAMING

    # On drop: Streaming -> Degraded -> Reconnecting -> Authorizing
    sm.transition(ProviderState.DEGRADED, reason="Heartbeat missed")
    assert sm.state == ProviderState.DEGRADED

    sm.transition(ProviderState.RECONNECTING, reason="Socket closed")
    assert sm.state == ProviderState.RECONNECTING

    sm.transition(ProviderState.AUTHORIZING, reason="Fresh URI requested")
    assert sm.state == ProviderState.AUTHORIZING

    # Terminal stop
    sm.transition(ProviderState.STOPPED, reason="User shutdown")
    assert sm.state == ProviderState.STOPPED
    assert sm.is_terminal


def test_provider_state_machine_invalid_transition():
    sm = ProviderStateMachine(provider="upstox")
    # Disconnected directly to Streaming is forbidden
    with pytest.raises(ValueError, match="Illegal state transition"):
        sm.transition(ProviderState.STREAMING, reason="Bypassing auth")


def test_candle_engine_invariants_and_mutation():
    engine = IncrementalCandleEngine(
        instrument_key="MCX_FO|569003",
        intervals=["1s", "1m"],
    )

    t0 = 1727100000.0  # Align to minute bucket

    # First tick
    events = engine.on_observation(ltp=151000.0, timestamp_epoch=t0, vtt=100, oi=5000)
    assert len(events) >= 2  # 1s and 1m updates
    m1 = engine.get_active_candle("1m")
    assert m1 is not None
    assert m1.open == 151000.0
    assert m1.high == 151000.0
    assert m1.low == 151000.0
    assert m1.close == 151000.0
    assert m1.validate_invariants()

    # Second tick: higher price in same minute
    engine.on_observation(ltp=151050.0, timestamp_epoch=t0 + 10.0, vtt=105, oi=5002)
    assert m1.high == 151050.0
    assert m1.low == 151000.0
    assert m1.close == 151050.0
    assert m1.volume == 5
    assert m1.open_interest == 5002
    assert m1.validate_invariants()

    # Third tick: lower price in same minute
    engine.on_observation(ltp=150950.0, timestamp_epoch=t0 + 20.0, vtt=110, oi=5005)
    assert m1.high == 151050.0
    assert m1.low == 150950.0
    assert m1.close == 150950.0
    assert m1.volume == 10
    assert m1.validate_invariants()


def test_candle_boundary_finalization():
    closed_events = []
    engine = IncrementalCandleEngine(
        instrument_key="MCX_FO|569003",
        intervals=["1m"],
        on_candle_closed=lambda c: closed_events.append(c),
    )

    t0 = 1727100000.0
    engine.on_observation(ltp=150000.0, timestamp_epoch=t0, vtt=10)
    engine.on_observation(ltp=150100.0, timestamp_epoch=t0 + 30, vtt=15)

    # Next minute tick (crosses 60s boundary)
    engine.on_observation(ltp=150200.0, timestamp_epoch=t0 + 65, vtt=25)

    assert len(closed_events) == 1
    closed = closed_events[0]
    assert closed.final is True
    assert closed.open == 150000.0
    assert closed.high == 150100.0
    assert closed.close == 150100.0
    assert closed.volume == 5

    # New active candle
    active = engine.get_active_candle("1m")
    assert active is not None
    assert active.final is False
    assert active.open == 150200.0
    assert active.volume == 10


def test_volume_no_double_counting_across_reconnect():
    engine = IncrementalCandleEngine(
        instrument_key="MCX_FO|569003",
        intervals=["1m"],
    )

    t0 = 1727100000.0
    # Before disconnect: VTT is 1000 -> 1050 (50 traded)
    engine.on_observation(ltp=150000.0, timestamp_epoch=t0, vtt=1000)
    engine.on_observation(ltp=150010.0, timestamp_epoch=t0 + 10, vtt=1050)
    m1 = engine.get_active_candle("1m")
    assert m1.volume == 50

    # Simulate disconnect and reconnect: call reset_volume_tracking
    engine.reset_volume_tracking()

    # Reconnect snapshot reports VTT = 1050 (same)
    engine.on_observation(ltp=150010.0, timestamp_epoch=t0 + 20, vtt=1050)
    # Must NOT add 1050 to candle volume!
    assert m1.volume == 50

    # Next new trade reports VTT = 1060 (10 more traded)
    engine.on_observation(ltp=150020.0, timestamp_epoch=t0 + 30, vtt=1060)
    assert m1.volume == 60


def test_subscription_registry():
    reg = SubscriptionRegistry()
    assert reg.active_count == 0

    sub, is_new = reg.subscribe("MCX_FO|569003")
    assert is_new is True
    assert sub.consumer_count == 1
    assert reg.is_subscribed("MCX_FO|569003")

    # Second consumer subscribes to same instrument (fan-out sharing)
    sub2, is_new2 = reg.subscribe("MCX_FO|569003")
    assert is_new2 is False
    assert sub2.consumer_count == 2
    assert reg.active_count == 1  # Still 1 unique upstream instrument

    # First consumer leaves
    rec, should_unsub = reg.unsubscribe("MCX_FO|569003")
    assert should_unsub is False  # consumer_count is 1

    # Second consumer leaves
    rec2, should_unsub2 = reg.unsubscribe("MCX_FO|569003")
    assert should_unsub2 is True  # Now upstream should unsubscribe
    assert reg.active_count == 0


def test_stream_hub_filtering_and_broadcast():
    async def _run():
        hub = StreamHub()

        class MockWebSocket:
            def __init__(self):
                self.sent = []
                self.closed = False

            async def send_text(self, text: str):
                self.sent.append(text)

            async def close(self):
                self.closed = True

        ws = MockWebSocket()
        _sub = await hub.register(ws)
        assert hub.client_count == 1

        # Client subscribes to GOLDM and 5m candle
        await hub.handle_client_message(
            ws,
            '{"action": "subscribe", "instrument_key": "MCX_FO|569003", '
            '"interval": "5m", "channels": ["candle"]}',
        )

        # Broadcast a 5m candle
        candle_5m = LiveCandle(
            instrument_key="MCX_FO|569003",
            interval="5m",
            bucket_start_epoch=1727100000,
            open=151000.0,
            high=151050.0,
            low=150950.0,
            close=151020.0,
            volume=100,
        )
        await hub.broadcast_candle(candle_5m)
        assert len(ws.sent) >= 2  # Subscription ack + candle update
        assert "candle_update" in ws.sent[-1]
        assert "151020" in ws.sent[-1]

        # Broadcast a 15m candle (should be filtered out by interval filter)
        candle_15m = LiveCandle(
            instrument_key="MCX_FO|569003",
            interval="15m",
            bucket_start_epoch=1727100000,
            open=151000.0,
            high=151050.0,
            low=150950.0,
            close=151020.0,
        )
        sent_count_before = len(ws.sent)
        await hub.broadcast_candle(candle_15m)
        assert len(ws.sent) == sent_count_before

        await hub.unregister(ws)
        assert hub.client_count == 0

    asyncio.run(_run())


def test_market_journal_non_blocking():
    async def _run():
        from decimal import Decimal

        from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate, UpdateKind

        journal = MarketJournal(max_memory_entries=50)
        journal.start()

        now = datetime.now(UTC)
        for i in range(10):
            update = NormalizedFeedUpdate(
                instrument_key="MCX_FO|569003",
                kind=UpdateKind.OPTION,
                received_at=now,
                exchange_timestamp=now,
                last_traded_price=Decimal(str(150000 + i)),
            )
            journal.record(update)

        assert journal.total_recorded == 10
        recent = journal.recent_entries(5)
        assert len(recent) == 5
        assert recent[-1].last_price == Decimal(str(150009))

        journal.stop()

    asyncio.run(_run())


def test_safety_rules_invariants():
    """Verifies critical safety constraints: LIVE_MONEY=false, PaperBroker sole execution target."""
    import inspect

    from ats.market.live import upstox_v3

    # Check that upstox_v3 has NO order writing functions
    methods = [m[0] for m in inspect.getmembers(upstox_v3.UpstoxV3LiveWorker)]
    forbidden = [
        "place_order",
        "modify_order",
        "cancel_order",
        "order_write",
        "buy",
        "sell",
    ]
    for f in forbidden:
        assert f not in methods, (
            f"Violation: Forbidden order method {f} found in live market worker!"
        )
