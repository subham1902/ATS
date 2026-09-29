from __future__ import annotations

import asyncio

from ats.api.stream import iter_sse, serialize_sse

from tests.unit.api.fixtures import make_api_fixture


class DisconnectRequest:
    """Disconnect verdict for ``iter_sse``.

    ``disconnected`` short-circuits every check. Otherwise the request stays
    connected for the first ``polls - 1`` checks and reports a disconnection
    from the ``polls``-th onward, which is how a test says "read what you need,
    then stop". ``iter_sse`` has no natural end: after the snapshot it
    heartbeats forever, so a test that never disconnects does not finish, it
    hangs until pytest-timeout kills it.
    """

    def __init__(self, disconnected: bool, *, polls: int = 1) -> None:
        self.disconnected = disconnected
        self._remaining = polls

    async def is_disconnected(self) -> bool:
        if self.disconnected:
            return True
        self._remaining -= 1
        return self._remaining <= 0


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
        # Two polls: one for the snapshot event, one to end the keep-alive
        # loop. An unbounded request never returns, so this test used to hang
        # for the full 120 s timeout instead of asserting anything.
        return [item async for item in iter_sse(DisconnectRequest(False, polls=2), x["reader"])]

    rendered = asyncio.run(consume())
    assert len(rendered) == 2
    assert str(x["stream_event"].stream_event_id) in rendered[0]
    assert rendered[1] == ": connected\n\n"
