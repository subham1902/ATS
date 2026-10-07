"""Synchronous O(1) latest-intelligence reads; refresh remains outside the hot path."""

from __future__ import annotations

from typing import Literal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import DataQualityState

from .models import IntelligenceCacheRead, IntelligenceStaleness, MarketIntelligenceSnapshot


class MarketIntelligenceCache:
    def __init__(self) -> None:
        self._latest: dict[Literal["XAUUSD"], MarketIntelligenceSnapshot] = {}

    def update(self, snapshot: MarketIntelligenceSnapshot) -> bool:
        previous = self._latest.get(snapshot.underlying)
        if previous is not None:
            if snapshot.data_cutoff < previous.data_cutoff:
                raise ValueError("intelligence data_cutoff regression")
            if snapshot.as_of_time < previous.as_of_time:
                raise ValueError("intelligence as_of_time regression")
            if snapshot == previous:
                return False
        self._latest[snapshot.underlying] = snapshot
        return True

    def read(self, *, underlying: Literal["XAUUSD"], at_time: UTCDateTime) -> IntelligenceCacheRead:
        snapshot = self._latest.get(underlying)
        if snapshot is None:
            return IntelligenceCacheRead(status=IntelligenceStaleness.UNKNOWN, snapshot=None)
        if at_time < snapshot.as_of_time:
            raise ValueError("intelligence read time precedes snapshot")
        if at_time >= snapshot.valid_until or snapshot.quality is not DataQualityState.GOOD:
            return IntelligenceCacheRead(status=IntelligenceStaleness.STALE, snapshot=snapshot)
        return IntelligenceCacheRead(status=IntelligenceStaleness.VALID, snapshot=snapshot)


__all__ = ["MarketIntelligenceCache"]
