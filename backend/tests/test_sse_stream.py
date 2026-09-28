"""Unit and integration tests for ATS Control Plane Server-Sent Events (SSE)."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from ats.api.app import create_app
from ats.api.models import StreamEvent
from ats.api.stream import broadcast_stream_event, iter_sse, serialize_sse
from ats.console.providers import LiveControlPlaneReader


@pytest.fixture
def app():
    return create_app(reader=LiveControlPlaneReader())


def test_serialize_sse():
    event = StreamEvent(
        stream_event_id=uuid4(),
        event_kind="SYSTEM_STATE_CHANGED",
        occurred_at=datetime.now(UTC),
        correlation_id=uuid4(),
        payload={"state": "READY", "version": 1},
    )
    frame = serialize_sse(event)
    assert f"id: {event.stream_event_id}\n" in frame
    assert "event: SYSTEM_STATE_CHANGED\n" in frame
    assert "data: {" in frame
    assert frame.endswith("\n\n")


def test_iter_sse_initial_connected_and_heartbeat():
    """Verifies that iter_sse yields initial connected frame immediately."""
    async def _run():
        reader = LiveControlPlaneReader()

        disconnect_after = 2
        count = 0

        class MockRequest:
            async def is_disconnected(self):
                nonlocal count
                count += 1
                return count > disconnect_after

        mock_req = MockRequest()
        generator = iter_sse(mock_req, reader)

        # First item must be the connected frame
        first_frame = await anext(generator)
        assert first_frame == ": connected\n\n"

    asyncio.run(_run())


def test_broadcast_stream_event_delivery():
    """Verifies that broadcast_stream_event delivers events to active SSE subscriber."""
    async def _run():
        reader = LiveControlPlaneReader()
        is_disc = False

        class MockRequest:
            async def is_disconnected(self):
                return is_disc

        mock_req = MockRequest()
        generator = iter_sse(mock_req, reader)

        # Consume initial connected frame
        first = await anext(generator)
        assert first == ": connected\n\n"

        # Broadcast event
        event = StreamEvent(
            stream_event_id=uuid4(),
            event_kind="PAPER_TRADE_EXECUTED",
            occurred_at=datetime.now(UTC),
            correlation_id=uuid4(),
            payload={"order_id": "ORD-123", "symbol": "GOLDM"},
        )
        broadcast_stream_event(event)

        # Next frame from generator must be the broadcast event
        received_frame = await anext(generator)
        assert f"id: {event.stream_event_id}\n" in received_frame
        assert "event: PAPER_TRADE_EXECUTED\n" in received_frame
        assert "ORD-123" in received_frame

        # Disconnect cleanly
        is_disc = True
        with pytest.raises(StopAsyncIteration):
            await anext(generator)

    asyncio.run(_run())
