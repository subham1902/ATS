"""Per-key freshness latches with explicit FRESH/STALE/UNKNOWN/RESYNC_REQUIRED.

Semantics are deliberately conservative:

* Silence is never treated as proof that a price is unchanged. A latch ages
  out to STALE using both the provider exchange timestamp and the local
  receipt timestamp.
* Any disconnect marks every latch RESYNC_REQUIRED; only an explicit,
  complete reconciliation can clear it.
* Duplicate or out-of-order provider timestamps never silently advance state:
  exact duplicates are idempotent no-ops, and any other regression latches the
  key into RESYNC_REQUIRED.
"""

from __future__ import annotations

from ats.contracts.common import UTCDateTime
from ats.market.derivatives.providers.models import SourceFreshness

from .messages import NormalizedFeedUpdate

_SEVERITY = {
    SourceFreshness.FRESH: 0,
    SourceFreshness.UNKNOWN: 1,
    SourceFreshness.STALE: 2,
    SourceFreshness.RESYNC_REQUIRED: 3,
}


class LatchDecision:
    """Outcome of feeding one update into a latch."""

    __slots__ = ("applied", "duplicate", "regression")

    def __init__(self, *, applied: bool, duplicate: bool, regression: bool) -> None:
        self.applied = applied
        self.duplicate = duplicate
        self.regression = regression


class KeyFreshnessLatch:
    """One instrument key's freshness state machine."""

    def __init__(self, *, instrument_key: str, stale_after_ms: int) -> None:
        if isinstance(stale_after_ms, bool) or stale_after_ms <= 0:
            raise ValueError("stale_after_ms must be a positive integer")
        self._instrument_key = instrument_key
        self._stale_after_ms = stale_after_ms
        self._resync_required = False
        self._last_update: NormalizedFeedUpdate | None = None

    @property
    def instrument_key(self) -> str:
        return self._instrument_key

    @property
    def last_update(self) -> NormalizedFeedUpdate | None:
        return self._last_update

    def record(self, update: NormalizedFeedUpdate) -> LatchDecision:
        if update.instrument_key != self._instrument_key:
            raise ValueError("update belongs to a different instrument key")
        previous = self._last_update
        if previous is not None and _same_content(previous, update):
            return LatchDecision(applied=False, duplicate=True, regression=False)
        regression = False
        if previous is not None:
            previous_ordering = previous.provider_timestamp or previous.exchange_timestamp
            update_ordering = update.provider_timestamp or update.exchange_timestamp
            if (
                previous_ordering is not None
                and update_ordering is not None
                and update_ordering <= previous_ordering
            ):
                regression = True
            if update.received_at < previous.received_at:
                regression = True
        if regression:
            self._resync_required = True
        self._last_update = update
        return LatchDecision(applied=True, duplicate=False, regression=regression)

    def mark_resync_required(self) -> None:
        self._resync_required = True

    def complete_resync(self) -> None:
        """Clear the resync latch; freshness then re-derives from evidence."""

        if self._last_update is None:
            raise ValueError("cannot complete resync without any recorded update")
        self._resync_required = False

    def reconcile(self, update: NormalizedFeedUpdate, *, now: UTCDateTime) -> SourceFreshness:
        """Record one reconciliation update; clear resync only when evidence is fresh.

        The recorded evidence must prove freshness on its own merits before
        this latch may leave ``RESYNC_REQUIRED``: a future-dated, stale, or
        regressive snapshot keeps the latch unsafe.
        """

        decision = self.record(update)
        if decision.regression:
            return SourceFreshness.RESYNC_REQUIRED
        assert self._last_update is not None
        if self._violates_clock_or_age(now):
            return SourceFreshness.STALE
        self._resync_required = False
        return SourceFreshness.FRESH

    def evaluate(self, now: UTCDateTime) -> SourceFreshness:
        if self._resync_required:
            return SourceFreshness.RESYNC_REQUIRED
        if self._last_update is None:
            return SourceFreshness.UNKNOWN
        if self._violates_clock_or_age(now):
            return SourceFreshness.STALE
        return SourceFreshness.FRESH

    def _violates_clock_or_age(self, now: UTCDateTime) -> bool:
        assert self._last_update is not None
        if now < self._last_update.received_at:
            return True
        for source_timestamp in self._last_update.decision_critical_timestamps():
            if source_timestamp is None:
                return True
            if now < source_timestamp:
                return True
            if (now - source_timestamp).total_seconds() * 1000 > self._stale_after_ms:
                return True
        if (now - self._last_update.received_at).total_seconds() * 1000 > self._stale_after_ms:
            return True
        return False


class FeedFreshnessBoard:
    """Aggregate per-key latches for the whole subscription set."""

    def __init__(self) -> None:
        self._latches: dict[str, KeyFreshnessLatch] = {}

    def register(self, *, instrument_key: str, stale_after_ms: int) -> KeyFreshnessLatch:
        if instrument_key in self._latches:
            raise ValueError(f"latch for {instrument_key} already exists")
        latch = KeyFreshnessLatch(instrument_key=instrument_key, stale_after_ms=stale_after_ms)
        self._latches[instrument_key] = latch
        return latch

    def latch(self, instrument_key: str) -> KeyFreshnessLatch:
        try:
            return self._latches[instrument_key]
        except KeyError as exc:
            raise KeyError(f"no freshness latch for {instrument_key}") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._latches))

    def mark_all_resync_required(self) -> None:
        for latch in self._latches.values():
            latch.mark_resync_required()

    def evaluate(self, now: UTCDateTime) -> dict[str, SourceFreshness]:
        return {key: latch.evaluate(now) for key, latch in sorted(self._latches.items())}

    def aggregate(self, now: UTCDateTime) -> SourceFreshness:
        if not self._latches:
            return SourceFreshness.UNKNOWN
        return max(
            (latch.evaluate(now) for latch in self._latches.values()),
            key=lambda state: _SEVERITY[state],
        )


def _same_content(first: NormalizedFeedUpdate, second: NormalizedFeedUpdate) -> bool:
    """Provider content identity ignores local receipt metadata."""

    return first.model_dump(exclude={"received_at"}) == second.model_dump(exclude={"received_at"})


__all__ = ["FeedFreshnessBoard", "KeyFreshnessLatch", "LatchDecision"]
