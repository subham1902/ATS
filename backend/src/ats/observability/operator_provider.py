"""Non-blocking observer store for operator-intelligence projections."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ats.api.models import StreamEvent
from ats.contracts.common import SystemClock
from ats.trading_runtime.runtime_provider import RuntimeProviderState

from .operator_intelligence import OperatorIntelligenceSnapshot, ProvenanceType
from .operator_projection import OperatorProjectionInput, build_operator_snapshot

MATERIAL_OPERATOR_EVENT_KINDS = frozenset(
    {
        "MARKET_SNAPSHOT_READY",
        "FEATURES_READY",
        "FORECAST_READY",
        "CANDIDATE_CREATED",
        "RISK_EVALUATED",
        "SUPERVISOR_EVALUATED",
        "POSITION_OPENED",
        "POSITION_UPDATED",
        "POSITION_CLOSED",
        "TRADE_REVIEW_READY",
        "SYSTEM_HALTED",
    }
)


class OperatorIntelligenceProvider:
    """Latest-value observer; event delivery is lossy and never trading-authoritative."""

    def __init__(self, source: OperatorProjectionInput | None = None) -> None:
        now = SystemClock().now()
        self._source = source or OperatorProjectionInput(
            as_of=now,
            data_cutoff=now,
            provenance=ProvenanceType.LIVE,
        )
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()

    def snapshot(self, runtime: RuntimeProviderState | None = None) -> OperatorIntelligenceSnapshot:
        return build_operator_snapshot(self._source, runtime=runtime)

    def observe(self, source: OperatorProjectionInput, event: StreamEvent) -> bool:
        """Publish after canonical processing; slow/full UI queues are dropped, never awaited."""
        if event.event_kind not in MATERIAL_OPERATOR_EVENT_KINDS:
            return False
        self._source = source
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A disconnected dashboard cannot back-pressure P0/P1.
                continue
        return True

    async def stream(self) -> AsyncIterator[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


__all__ = ["MATERIAL_OPERATOR_EVENT_KINDS", "OperatorIntelligenceProvider"]
