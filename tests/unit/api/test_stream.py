from __future__ import annotations

import asyncio

from ats.api.stream import iter_sse, serialize_sse

from tests.unit.api.fixtures import make_api_fixture


class DisconnectRequest:
    def __init__(self, disconnected: bool) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


def test_sse_serialization_is_typed_and_read_only() -> None:
    x = make_api_fixture()
    rendered = serialize_sse(x["stream_event"])
    assert rendered.startswith(f"id: {x['stream_event'].stream_event_id}\n")
    assert "event: RISK_EVALUATED\n" in rendered
    assert '"decision":"ALLOW"' in rendered
    assert "command" not in rendered.lower()


def test_sse_disconnect_stops_before_yielding() -> None:
    x = make_api_fixture()

    async def consume() -> list[str]:
        return [item async for item in iter_sse(DisconnectRequest(True), x["reader"])]

    assert asyncio.run(consume()) == []


def test_sse_connected_reader_preserves_provider_order() -> None:
    x = make_api_fixture()

    async def consume() -> list[str]:
        return [item async for item in iter_sse(DisconnectRequest(False), x["reader"])]

    rendered = asyncio.run(consume())
    assert len(rendered) == 1
    assert str(x["stream_event"].stream_event_id) in rendered[0]
