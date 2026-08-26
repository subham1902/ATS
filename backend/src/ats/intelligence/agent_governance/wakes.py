"""Bounded material-event wake coalescing; ordinary ticks never enter this seam."""

from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta

from .models import MaterialWakeEvent


class MaterialWakeCoalescer:
    def __init__(self, *, maximum_pending: int = 64, deduplication_window: timedelta) -> None:
        if maximum_pending <= 0 or deduplication_window.total_seconds() < 0:
            raise ValueError("wake bounds are invalid")
        self._maximum_pending = maximum_pending
        self._window = deduplication_window
        self._pending: OrderedDict[tuple[str, str], MaterialWakeEvent] = OrderedDict()

    def submit(self, event: MaterialWakeEvent) -> bool:
        key = (event.kind.value, event.scope)
        previous = self._pending.get(key)
        if previous is not None and event.occurred_at - previous.occurred_at <= self._window:
            if event.occurred_at >= previous.occurred_at:
                self._pending[key] = event
            return False
        self._pending[key] = event
        self._pending.move_to_end(key)
        while len(self._pending) > self._maximum_pending:
            self._pending.popitem(last=False)
        return True

    def drain(self) -> tuple[MaterialWakeEvent, ...]:
        events = tuple(self._pending.values())
        self._pending.clear()
        return events

    @property
    def pending_count(self) -> int:
        return len(self._pending)


__all__ = ["MaterialWakeCoalescer"]
