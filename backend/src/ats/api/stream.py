"""Read-only, non-durable Server-Sent Events projection."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from starlette.requests import Request

from ats.observability.operator_provider import OperatorIntelligenceProvider

from .models import StreamEvent
from .providers import ControlPlaneReader


def serialize_sse(event: StreamEvent) -> str:
    """Serialize one validated UI stream event without domain-event mutation."""
    return (
        f"id: {event.stream_event_id}\n"
        f"event: {event.event_kind}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


async def iter_sse(request: Request, reader: ControlPlaneReader) -> AsyncIterator[str]:
    """Yield the current non-replayable projection and keep alive until disconnect."""
    for event in reader.stream_events():
        if await request.is_disconnected():
            return
        yield serialize_sse(event)
    while not await request.is_disconnected():
        await asyncio.sleep(2.0)


async def iter_operator_sse(
    request: Request,
    provider: OperatorIntelligenceProvider,
) -> AsyncIterator[str]:
    """Forward canonical material events without back-pressuring their producers."""
    async for event in provider.stream():
        if await request.is_disconnected():
            return
        yield serialize_sse(event)


__all__ = ["iter_operator_sse", "iter_sse", "serialize_sse"]
