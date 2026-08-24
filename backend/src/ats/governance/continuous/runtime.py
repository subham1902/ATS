"""Small asyncio event dispatcher; it never runs a trading loop or submits work externally."""

from __future__ import annotations

import asyncio

from ats.intelligence.advisory import (
    AdvisoryEvent,
    PositionAdvisoryProvider,
    append_advisory_event,
)

from .models import DispatchStatus, MarketEventDispatch
from .protocols import PositionContextReader


class ContinuousMarketGovernor:
    """Caller-owned queue for event-driven advisory interrupts between completed bars."""

    def __init__(
        self,
        *,
        context_reader: PositionContextReader,
        advisory_provider: PositionAdvisoryProvider,
    ) -> None:
        self._context_reader = context_reader
        self._advisory_provider = advisory_provider
        self._events: asyncio.Queue[AdvisoryEvent] = asyncio.Queue()

    async def publish(self, event: AdvisoryEvent) -> None:
        """Queue a typed observation; no market data, broker, or A04 operation occurs."""

        await self._events.put(event)

    async def dispatch_next(self) -> MarketEventDispatch:
        """Dispatch exactly one event, making lifecycle and ordering caller-observable."""

        event = await self._events.get()
        try:
            return self._dispatch(event)
        finally:
            self._events.task_done()

    def pending_count(self) -> int:
        return self._events.qsize()

    def _dispatch(self, event: AdvisoryEvent) -> MarketEventDispatch:
        if event.position_id is None:
            return MarketEventDispatch(
                status=DispatchStatus.IGNORED,
                event=event,
                proposal=None,
                reason_codes=("POSITION_CONTEXT_REQUIRED",),
            )
        context = self._context_reader.get(event.position_id)
        if context is None:
            return MarketEventDispatch(
                status=DispatchStatus.IGNORED,
                event=event,
                proposal=None,
                reason_codes=("POSITION_CONTEXT_NOT_FOUND",),
            )
        updated = append_advisory_event(context, event=event)
        proposal = self._advisory_provider.advise(context=updated, trigger=event)
        if proposal.position_id != event.position_id:
            return MarketEventDispatch(
                status=DispatchStatus.IGNORED,
                event=event,
                proposal=None,
                reason_codes=("ADVISORY_POSITION_MISMATCH",),
            )
        return MarketEventDispatch(
            status=DispatchStatus.DISPATCHED,
            event=event,
            proposal=proposal,
            reason_codes=("ADVISORY_INTERRUPT_DISPATCHED",),
        )


__all__ = ["ContinuousMarketGovernor"]
