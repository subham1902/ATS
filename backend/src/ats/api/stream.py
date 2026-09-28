"""Read-only, non-durable Server-Sent Events projection.

The projection is non-replayable and non-durable: no event history is
reconstructed and a reconnect starts from the current snapshot rather than a
resumed offset. The channel deliberately stays open after the snapshot, because
a stream that closes forced the console into a reconnect poll loop and made a
genuinely live channel indistinguishable from a dead one.

The market-data channel is separate and lives in :mod:`ats.console.market_router`;
this module only serves the control-plane projection.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from starlette.requests import Request

from .models import StreamEvent
from .providers import ControlPlaneReader

logger = logging.getLogger(__name__)

# Keep-alive cadence in seconds. Frequent heartbeats prevent reverse proxy
# buffering timeouts and notify client of active channel status.
HEARTBEAT_SECONDS = 5.0

# Active SSE subscriber queues
_SSE_SUBSCRIBERS: set[asyncio.Queue[StreamEvent]] = set()


def broadcast_stream_event(event: StreamEvent) -> None:
    """Broadcast a control-plane event to all currently connected SSE streams."""
    for queue in list(_SSE_SUBSCRIBERS):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


def serialize_sse(event: StreamEvent) -> str:
    """Serialize one validated UI stream event without domain-event mutation."""

    return (
        f"id: {event.stream_event_id}\n"
        f"event: {event.event_kind}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


async def iter_sse(request: Request, reader: ControlPlaneReader) -> AsyncIterator[str]:
    """Yield snapshot events then maintain persistent SSE channel with heartbeats and events."""
    # 1. Emit any initial snapshot events
    for event in reader.stream_events():
        if await request.is_disconnected():
            return
        yield serialize_sse(event)

    # 2. Register subscriber queue BEFORE yielding connected confirmation
    queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=200)
    _SSE_SUBSCRIBERS.add(queue)
    try:
        yield ": connected\n\n"

        # 3. Enter persistent subscriber loop
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                yield serialize_sse(event)
            except TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
    except (asyncio.CancelledError, GeneratorExit):
        pass
    except Exception as exc:
        logger.debug("SSE stream terminated: %s", exc)
    finally:
        _SSE_SUBSCRIBERS.discard(queue)


__all__ = ["broadcast_stream_event", "iter_sse", "serialize_sse"]
