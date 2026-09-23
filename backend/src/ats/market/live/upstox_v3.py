"""Upstox V3 Live Market Data Worker.

Connects to the official Upstox Market Data Feed V3 WebSocket,
decodes binary Protobuf payloads, enforces the provider state machine,
appends raw events to the journal, publishes to MarketDataFabric,
drives the IncrementalCandleEngine, and fans out to StreamHub.

Safety Invariants:
1. READ-ONLY: Never invokes or exposes any order write endpoint.
2. Ephemeral URI: Authorizes a fresh one-time WSS endpoint on every connect/reconnect.
3. No Token Leak: Never logs, persists, or exposes the bearer token or authorized URL.
4. Non-Blocking: Journal and client dispatch never block the upstream feed receiver loop.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from ats.market.fabric import MarketDataFabric
from ats.market.feeds.upstox_v3.config import (
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
)
from ats.market.feeds.upstox_v3.frames import subscribe_frame
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate
from ats.market.feeds.upstox_v3.protobuf_codec import UpstoxV3ProtobufDecoder
from ats.market.feeds.upstox_v3.transport import UpstoxV3FeedAuthorizer
from ats.market.live.candle_builder import IncrementalCandleEngine, LiveCandle
from ats.market.live.journal import MarketJournal
from ats.market.live.state import ProviderState, ProviderStateMachine
from ats.market.live.stream_hub import StreamHub
from ats.market.live.subscriptions import SubscriptionRegistry

logger = logging.getLogger("ats.market.live.upstox_v3")


class UpstoxV3LiveWorker:
    """Production-grade asynchronous background worker for Upstox V3 streaming."""

    def __init__(
        self,
        token: str,
        fabric: MarketDataFabric,
        candle_engine: IncrementalCandleEngine,
        journal: MarketJournal,
        hub: StreamHub,
        registry: Optional[SubscriptionRegistry] = None,
        primary_instrument: str = "MCX_FO|569003",
        mode: str = "full",
    ):
        self._token = token
        self.fabric = fabric
        self.candle_engine = candle_engine
        self.journal = journal
        self.hub = hub
        self.registry = registry or SubscriptionRegistry()
        self.primary_instrument = primary_instrument
        self.requested_mode = mode

        self.state_machine = ProviderStateMachine(provider="upstox")
        self.decoder = UpstoxV3ProtobufDecoder()

        # Telemetry & Observability counters
        self.events_received: int = 0
        self.frames_received: int = 0
        self.decode_errors: int = 0
        self.reconnect_count: int = 0
        self.last_tick_time: Optional[datetime] = None
        self.last_quote_time: Optional[datetime] = None
        self.last_depth_time: Optional[datetime] = None
        self.last_oi_time: Optional[datetime] = None
        self.last_ltp: Optional[float] = None
        self.last_bid: Optional[float] = None
        self.last_ask: Optional[float] = None
        self.last_volume: Optional[int] = None
        self.last_oi: Optional[int] = None

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._current_ws = None

        # Register primary subscription
        self.registry.subscribe(
            instrument_key=self.primary_instrument,
            mode=self.requested_mode,
            consumer_id="ats_primary_chart",
        )

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="ats_upstox_v3_worker")
        logger.info("UpstoxV3LiveWorker background task started for %s", self.primary_instrument)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self.state_machine.transition(ProviderState.STOPPED, reason="Operator stop requested")
        if self._current_ws:
            try:
                await self._current_ws.close()
            except Exception:
                pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.journal.stop()
        logger.info("UpstoxV3LiveWorker stopped cleanly")

    async def _run_loop(self) -> None:
        """Main resilient supervision loop with bounded backoff and fresh authorization."""
        backoff_seconds = 1.0
        max_backoff = 30.0

        while self._running:
            try:
                # Step 1: Authorization
                self.state_machine.transition(
                    ProviderState.AUTHORIZING,
                    reason="Acquiring single-use authorized websocket URI",
                )
                from pydantic import SecretStr
                auth = UpstoxFeedAuthorization(bearer_token=SecretStr(self._token))
                authorizer = UpstoxV3FeedAuthorizer(auth)
                ws_uri = await asyncio.to_thread(authorizer.authorize_feed)

                # Step 2: Connection
                self.state_machine.transition(
                    ProviderState.CONNECTING,
                    reason="Initiating upstream WSS handshake",
                )
                async with ws_connect(
                    ws_uri,
                    open_timeout=10,
                    close_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._current_ws = ws
                    self.state_machine.transition(
                        ProviderState.CONNECTED,
                        reason="WSS transport connected",
                    )
                    backoff_seconds = 1.0  # Reset backoff on successful connect

                    # Step 3: Subscription
                    sub_frame = subscribe_frame(
                        guid="ats_worker_sub",
                        mode=FeedMode.FULL if self.requested_mode == "full" else FeedMode.LTPC,
                        instrument_keys=(self.primary_instrument,),
                    )
                    await ws.send(sub_frame.encode("utf-8"))

                    self.state_machine.transition(
                        ProviderState.SNAPSHOT_PENDING,
                        reason="Subscription sent, awaiting initial feed frame",
                    )
                    self.candle_engine.reset_volume_tracking()

                    # Step 4: Stream Consumption
                    async for message in ws:
                        if not self._running:
                            break
                        if isinstance(message, bytes):
                            self._handle_binary_frame(message)
                        elif isinstance(message, str):
                            logger.debug("Received text frame: %s", message[:100])

            except asyncio.CancelledError:
                break
            except ConnectionClosed as cc:
                self.reconnect_count += 1
                logger.warning("Upstox WebSocket closed: %s. Reconnecting...", cc)
                self.state_machine.transition(
                    ProviderState.DEGRADED,
                    reason=f"Transport closed: {cc.code}",
                )
            except Exception as ex:
                self.reconnect_count += 1
                logger.error("Upstox worker error: %s", ex, exc_info=True)
                self.state_machine.transition(
                    ProviderState.RECONNECTING,
                    reason=f"Exception: {type(ex).__name__}",
                )

            if self._running:
                jitter = random.uniform(0.1, 0.5)
                wait_time = min(backoff_seconds + jitter, max_backoff)
                logger.info("Backoff %0.1fs before next Upstox reconnection attempt", wait_time)
                await asyncio.sleep(wait_time)
                backoff_seconds = min(backoff_seconds * 2, max_backoff)

    def _handle_binary_frame(self, frame: bytes) -> None:
        """Decodes protobuf frame, updates fabric, candle engine, and hub."""
        now = datetime.now(UTC)
        self.frames_received += 1

        try:
            updates = self.decoder.decode(frame, received_at=now)
        except Exception as ex:
            self.decode_errors += 1
            logger.warning("Protobuf decode error on %d byte frame: %s", len(frame), ex)
            return

        if not updates:
            return

        # Advance state to STREAMING on first decoded updates
        if self.state_machine.state in (ProviderState.SNAPSHOT_PENDING, ProviderState.CONNECTED):
            self.state_machine.transition(
                ProviderState.STREAMING,
                reason="First decoded feed updates processed successfully",
            )

        for update in updates:
            self.events_received += 1
            inst = update.instrument_key

            # Non-blocking journal append
            self.journal.record(update)

            # 1. Update fabric for historical & read models
            self.fabric.publish(update)

            # 2. Extract values
            ltp = float(update.last_traded_price) if update.last_traded_price else 0.0
            if ltp > 0:
                self.last_ltp = ltp
                self.last_tick_time = now
            if update.bid_price:
                self.last_bid = float(update.bid_price)
                self.last_quote_time = now
            if update.ask_price:
                self.last_ask = float(update.ask_price)
            if update.volume is not None:
                self.last_volume = update.volume
            if update.open_interest is not None:
                self.last_oi = update.open_interest
                self.last_oi_time = now

            obs_epoch = (
                update.exchange_timestamp.timestamp()
                if update.exchange_timestamp
                else now.timestamp()
            )

            # 3. Drive Incremental Candle Engine
            candle_events = self.candle_engine.on_observation(
                ltp=ltp,
                timestamp_epoch=obs_epoch,
                vtt=update.volume,
                oi=update.open_interest,
                source="BROKER",
            )

            # 4. Asynchronously broadcast candle updates to StreamHub
            for evt_type, candle in candle_events:
                is_closed = (evt_type == "closed")
                asyncio.create_task(
                    self.hub.broadcast_candle(candle, is_closed=is_closed)
                )

            # 5. Broadcast Quote
            quote_payload = {
                "instrument_key": inst,
                "ltp": ltp,
                "bid": self.last_bid,
                "ask": self.last_ask,
                "volume": self.last_volume,
                "open_interest": self.last_oi,
                "exchange_timestamp": update.exchange_timestamp.isoformat() if update.exchange_timestamp else now.isoformat(),
            }
            asyncio.create_task(self.hub.broadcast_quote(inst, quote_payload))

            # 6. Broadcast Depth if provided
            if update.market_depth:
                self.last_depth_time = now
                depth_payload = {
                    "bids": [{"price": float(lvl.price), "quantity": lvl.quantity} for lvl in update.market_depth.buy_levels],
                    "asks": [{"price": float(lvl.price), "quantity": lvl.quantity} for lvl in update.market_depth.sell_levels],
                }
                asyncio.create_task(self.hub.broadcast_depth(inst, depth_payload))

            # 7. Broadcast OI if provided
            if update.open_interest is not None:
                oi_payload = {
                    "open_interest": update.open_interest,
                    "open_interest_change": update.open_interest_change,
                }
                asyncio.create_task(self.hub.broadcast_oi(inst, oi_payload))

    def get_telemetry(self) -> Dict[str, Any]:
        """Provides full observability without exposing credentials."""
        now = datetime.now(UTC)
        quote_age_ms = int((now - self.last_quote_time).total_seconds() * 1000) if self.last_quote_time else None
        trade_age_ms = int((now - self.last_tick_time).total_seconds() * 1000) if self.last_tick_time else None
        depth_age_ms = int((now - self.last_depth_time).total_seconds() * 1000) if self.last_depth_time else None
        oi_age_ms = int((now - self.last_oi_time).total_seconds() * 1000) if self.last_oi_time else None

        return {
            "provider": "upstox",
            "provider_state": self.state_machine.state.value,
            "instrument_key": self.primary_instrument,
            "subscription_mode": self.requested_mode,
            "events_received": self.events_received,
            "frames_received": self.frames_received,
            "decode_errors": self.decode_errors,
            "reconnect_count": self.reconnect_count,
            "last_ltp": self.last_ltp,
            "last_bid": self.last_bid,
            "last_ask": self.last_ask,
            "last_volume": self.last_volume,
            "last_open_interest": self.last_oi,
            "quote_age_ms": quote_age_ms,
            "trade_age_ms": trade_age_ms,
            "depth_age_ms": depth_age_ms,
            "oi_age_ms": oi_age_ms,
            "active_stream_clients": self.hub.client_count,
            "journal_memory_depth": self.journal.memory_depth,
            "journal_overflow_count": self.journal.overflow_count,
        }
