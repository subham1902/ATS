"""Internal ATS Stream Hub for Client WebSocket Fan-Out.

Handles:
1. Multi-client fan-out (dashboard, market tab, AI panel, multiple browser tabs)
   without multiplying upstream broker connections.
2. Filtered dispatch based on client subscriptions (instrument, timeframe, channels).
3. Typed, versioned envelopes avoiding credential leakage.
4. Non-blocking async dispatch with backpressure protection.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ats.market.live.candle_builder import LiveCandle
from fastapi import WebSocket

logger = logging.getLogger("ats.market.live.stream_hub")

SCHEMA_VERSION = "ats.market.v1"


@dataclass
class ClientSubscription:
    websocket: WebSocket
    instrument_keys: set[str] = field(default_factory=lambda: {"*"})
    intervals: set[str] = field(default_factory=lambda: {"1m", "5m"})
    channels: set[str] = field(
        default_factory=lambda: {"candle", "quote", "depth", "oi", "feed_health", "market_status"}
    )
    connected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    messages_sent: int = 0
    errors: int = 0


class StreamHub:
    """Central fan-out hub for browser WebSockets and internal consumers."""

    def __init__(self) -> None:
        self._clients: dict[WebSocket, ClientSubscription] = {}
        self._lock = asyncio.Lock()
        self.total_messages_broadcast: int = 0
        self.total_dropped_messages: int = 0

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, websocket: WebSocket) -> ClientSubscription:
        async with self._lock:
            sub = ClientSubscription(websocket=websocket)
            self._clients[websocket] = sub
            logger.info(
                "Client connected to StreamHub. Total active clients: %d", len(self._clients)
            )
            return sub

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._clients:
                del self._clients[websocket]
                logger.info(
                    "Client disconnected from StreamHub. Total active clients: %d",
                    len(self._clients),
                )

    async def handle_client_message(self, websocket: WebSocket, text: str) -> None:
        """Processes client control messages (subscribe, unsubscribe, ping)."""
        try:
            data = json.loads(text)
        except Exception:
            await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
            return

        action = data.get("action")
        sub = self._clients.get(websocket)
        if not sub:
            return

        if action == "ping":
            await websocket.send_text(
                json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "type": "pong",
                    "time": datetime.now(UTC).isoformat(),
                })
            )
        elif action == "subscribe":
            inst = data.get("instrument_key")
            interval = data.get("interval")
            channels = data.get("channels")
            if inst:
                sub.instrument_keys.add(inst)
            if interval:
                sub.intervals.add(interval)
            if channels and isinstance(channels, list):
                sub.channels.update(channels)

            await websocket.send_text(
                json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "type": "subscribed",
                    "instrument_keys": list(sub.instrument_keys),
                    "intervals": list(sub.intervals),
                    "channels": list(sub.channels),
                })
            )
        elif action == "unsubscribe":
            inst = data.get("instrument_key")
            if inst and inst in sub.instrument_keys:
                sub.instrument_keys.remove(inst)
            await websocket.send_text(
                json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "type": "unsubscribed",
                    "instrument_key": inst,
                })
            )

    async def broadcast_envelope(
        self,
        envelope: dict[str, Any],
        channel: str,
        instrument_key: str | None = None,
        interval: str | None = None,
    ) -> None:
        """Broadcasts a typed envelope to all matching client subscriptions."""
        if not self._clients:
            return

        payload_str = json.dumps(envelope)
        self.total_messages_broadcast += 1

        dead_clients: list[WebSocket] = []
        tasks = []

        for ws, sub in list(self._clients.items()):
            # Check channel filter
            if channel not in sub.channels and "*" not in sub.channels:
                continue

            # Check instrument filter
            if (
                instrument_key
                and "*" not in sub.instrument_keys
                and instrument_key not in sub.instrument_keys
            ):
                continue

            # Check interval filter for candle events
            if interval and "*" not in sub.intervals and interval not in sub.intervals:
                continue

            async def _send_to_client(target_ws: WebSocket, target_sub: ClientSubscription) -> None:
                try:
                    # 200ms timeout per client to prevent one slow/stuck client from blocking others
                    await asyncio.wait_for(target_ws.send_text(payload_str), timeout=0.2)
                    target_sub.messages_sent += 1
                except TimeoutError:
                    self.total_dropped_messages += 1
                    target_sub.errors += 1
                    logger.warning("Dropped message to slow WebSocket client")
                except Exception as ex:
                    dead_clients.append(target_ws)
                    logger.debug("Failed sending to client: %s", ex)

            tasks.append(_send_to_client(ws, sub))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    if ws in self._clients:
                        del self._clients[ws]

    async def broadcast_candle(self, candle: LiveCandle, is_closed: bool = False) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "type": "candle_closed" if is_closed else "candle_update",
            "source": candle.source,
            "provider": "upstox",
            "instrument_key": candle.instrument_key,
            "interval": candle.interval,
            "is_derived": candle.is_derived,
            "time": candle.time_iso,
            "source_time": candle.time_iso,
            "ingest_time": datetime.now(UTC).isoformat(),
            "bar": {
                "time": candle.time_iso,
                "bucket_start_epoch": candle.bucket_start_epoch,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "open_interest": candle.open_interest,
                "final": candle.final,
                "volume_status": candle.volume_status,
                "tick_count": candle.tick_count,
            },
        }
        await self.broadcast_envelope(
            envelope=envelope,
            channel="candle",
            instrument_key=candle.instrument_key,
            interval=candle.interval,
        )

    async def broadcast_quote(self, instrument_key: str, quote_data: dict[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "type": "quote",
            "source": "BROKER",
            "provider": "upstox",
            "instrument_key": instrument_key,
            "time": datetime.now(UTC).isoformat(),
            "quote": quote_data,
        }
        await self.broadcast_envelope(
            envelope=envelope, channel="quote", instrument_key=instrument_key
        )

    async def broadcast_depth(self, instrument_key: str, depth_data: dict[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "type": "depth",
            "source": "BROKER",
            "provider": "upstox",
            "instrument_key": instrument_key,
            "time": datetime.now(UTC).isoformat(),
            "depth": depth_data,
        }
        await self.broadcast_envelope(
            envelope=envelope, channel="depth", instrument_key=instrument_key
        )

    async def broadcast_oi(self, instrument_key: str, oi_data: dict[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "type": "oi",
            "source": "BROKER",
            "provider": "upstox",
            "instrument_key": instrument_key,
            "time": datetime.now(UTC).isoformat(),
            "oi": oi_data,
        }
        await self.broadcast_envelope(
            envelope=envelope, channel="oi", instrument_key=instrument_key
        )

    async def broadcast_feed_health(self, health_data: dict[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "type": "feed_health",
            "source": "ATS",
            "time": datetime.now(UTC).isoformat(),
            "health": health_data,
        }
        await self.broadcast_envelope(envelope=envelope, channel="feed_health")


# Global singleton instance
hub = StreamHub()
