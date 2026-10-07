"""Provider-neutral market-data fabric: single ingress and distribution point.

This module supplies the component that was missing between decoded provider
updates and every downstream consumer (HTTP read models, SSE, research
normalizers, paper runtime). Before it existed, a decoded
:class:`MarketObservation` had no path
out of the process.

Honesty rules encoded here and never relaxed:

* an out-of-order tick is DROPPED, never back-dated into a bar;
* a re-delivered tick is DROPPED as a duplicate, never double counted;
* a bar is exposed as ``is_closed`` only once its close time has passed;
* nothing here invents price, volume or open interest - absent fields stay
  ``None`` all the way to the UI.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING, Any

from ats.contracts.common import ClockProtocol, SystemClock
from ats.market.domain import require_xauusd
from ats.market.footprint import footprint_proxy
from ats.market.observations import MarketObservation as NormalizedFeedUpdate

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

LOGGER = logging.getLogger(__name__)

# UTC epoch alignment.
UTC_OFFSET_MINUTES = 0

# Bounded per-subscriber queue: a slow consumer loses its oldest pending update
# instead of stalling the ingress path for every other consumer.
SUBSCRIBER_QUEUE_SIZE = 512


class PublishOutcome(StrEnum):
    """Terminal disposition of one attempted publish."""

    ACCEPTED = "ACCEPTED"
    DROPPED_DUPLICATE = "DROPPED_DUPLICATE"
    DROPPED_OUT_OF_ORDER = "DROPPED_OUT_OF_ORDER"
    DROPPED_STALE = "DROPPED_STALE"


class BarInterval(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    D1 = "1d"

    @property
    def seconds(self) -> int:
        return {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}[self.value]


class _Bar:
    """Mutable working bar; only :class:`BarState` snapshots leave the fabric."""

    __slots__ = (
        "interval",
        "start",
        "close_ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_interest",
        "tick_count",
        "is_closed",
    )

    def __init__(self, interval: BarInterval, start: int, close_ts: int) -> None:
        self.interval = interval
        self.start = start
        self.close_ts = close_ts
        self.open: Decimal | None = None
        self.high: Decimal | None = None
        self.low: Decimal | None = None
        self.close: Decimal | None = None
        self.volume: Decimal | None = None
        self.open_interest: int | None = None
        self.tick_count = 0
        self.is_closed = False

    def apply(self, price: Decimal, volume: Decimal | None, open_interest: int | None) -> None:
        if self.open is None:
            self.open = price
        self.high = price if self.high is None else max(self.high, price)
        self.low = price if self.low is None else min(self.low, price)
        self.close = price
        self.tick_count += 1
        if volume is not None:
            # Sum observed broker volume; absent volume stays unknown.
            self.volume = volume if self.volume is None else self.volume + volume
        if open_interest is not None:
            self.open_interest = open_interest


def align_bar_start(epoch_seconds: float, interval_seconds: int, offset_minutes: int) -> int:
    """Floor an epoch second onto an interval boundary inside a fixed UTC offset."""

    offset = offset_minutes * 60
    return int((epoch_seconds + offset) // interval_seconds) * interval_seconds - offset


@dataclass(frozen=True, slots=True)
class BarSnapshot:
    """Immutable bar view handed to consumers; absent inputs stay ``None``."""

    interval: BarInterval
    bar_start_epoch: int
    bar_close_epoch: int
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: Decimal | None
    open_interest: int | None
    tick_count: int
    is_closed: bool

    @property
    def bar_start_utc(self) -> datetime:
        return datetime.fromtimestamp(self.bar_start_epoch, UTC)

    @property
    def bar_close_utc(self) -> datetime:
        return datetime.fromtimestamp(self.bar_close_epoch, UTC)


@dataclass(frozen=True, slots=True)
class FabricCounters:
    """Real disposition counts; used by health read models."""

    accepted: int
    dropped_duplicate: int
    dropped_out_of_order: int
    dropped_stale: int
    last_update_at: datetime | None


class FabricSubscription:
    """Queue-backed subscription.

    Deliberately a queue rather than a bare async generator: a consumer that
    times out while waiting must not cancel an ``anext`` coroutine, because that
    would close the generator. Waiting on ``queue.get`` is cancellation safe.
    """

    __slots__ = ("_fabric", "_queue", "_subscription_id")

    def __init__(
        self,
        fabric: MarketDataFabric,
        subscription_id: int,
        queue: asyncio.Queue[NormalizedFeedUpdate],
    ) -> None:
        self._fabric = fabric
        self._subscription_id = subscription_id
        self._queue = queue

    async def get(self, timeout: float) -> NormalizedFeedUpdate | None:
        """Return the next update, or ``None`` when the timeout elapses."""

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    def close(self) -> None:
        self._fabric.unsubscribe(self._subscription_id)


# NOTE: exactly one MarketDataFabric exists in this module, defined below. A
# second, shadowing definition previously sat here; it referenced undefined
# attributes (`_advance`, `threading`, `_closed_bars`) and was dead code. It was
# removed rather than repaired so ingress and bar truth have a single owner.


DEFAULT_HISTORY_LIMIT = 400


class MarketDataFabric:
    """Single ingress for decoded updates and single source of bar truth.

    Both the live chart and the research normalizer consume *this* object, so a
    live bar and a replayed bar cannot silently diverge.
    """

    def __init__(
        self,
        *,
        clock: ClockProtocol | None = None,
        source_label: str | None = None,
        authority_class: str = "LIVE_FEED_ATTACHED",
        # Age-based rejection is opt-in. Live attachments set it; replay or
        # historical normalization leaves it None so real history is not dropped
        # merely for being old. Freshness *display* is the read model's job.
        stale_after_seconds: float | None = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        alignment_offset_minutes: int = UTC_OFFSET_MINUTES,
    ) -> None:
        self._lock = RLock()
        self._clock = clock or SystemClock()
        self.source_label = source_label
        self.authority_class = authority_class
        self.stale_after_seconds = stale_after_seconds
        self.alignment_offset_minutes = alignment_offset_minutes
        self._history_limit = history_limit
        self._latest: dict[str, NormalizedFeedUpdate] = {}
        self._last_exchange_ts: dict[str, datetime] = {}
        self._recent_identities: deque[tuple[str, datetime, str]] = deque(maxlen=2000)
        self._identity_set: set[tuple[str, datetime, str]] = set()
        self._bars: dict[tuple[str, BarInterval], _Bar] = {}
        self._closed_bars: dict[tuple[str, BarInterval], deque[BarSnapshot]] = {}
        self._subscribers: dict[
            int, tuple[asyncio.AbstractEventLoop, asyncio.Queue[NormalizedFeedUpdate]]
        ] = {}
        self._next_subscriber_id = 1
        self.tick_size: Decimal | None = None
        self._observations: deque[NormalizedFeedUpdate] = deque(maxlen=10000)
        self._accepted = 0
        self._dropped_duplicate = 0
        self._dropped_out_of_order = 0
        self._dropped_stale = 0
        self._last_update_at: datetime | None = None

    def publish(
        self,
        update: NormalizedFeedUpdate,
        *,
        before_commit: Callable[[NormalizedFeedUpdate], None] | None = None,
    ) -> PublishOutcome:
        """Accept or reject one decoded update; never mutates history backwards."""

        with self._lock:
            observed = update.exchange_timestamp or update.received_at or self._clock.now()
            require_xauusd(update.instrument_key)
            if update.available_at > self._clock.now():
                raise ValueError("OBSERVATION_NOT_YET_AVAILABLE")
            if update.timeframe is not None:
                BarInterval(update.timeframe)
            identity = (
                update.instrument_key,
                observed,
                update.model_dump_json(exclude={"received_at"}),
            )
            if identity in self._identity_set:
                self._dropped_duplicate += 1
                return PublishOutcome.DROPPED_DUPLICATE
            previous = self._last_exchange_ts.get(update.instrument_key)
            if previous is not None and observed < previous:
                self._dropped_out_of_order += 1
                return PublishOutcome.DROPPED_OUT_OF_ORDER
            if self.stale_after_seconds is not None:
                age = (self._clock.now() - observed).total_seconds()
                if age > self.stale_after_seconds:
                    self._dropped_stale += 1
                    return PublishOutcome.DROPPED_STALE

            if before_commit is not None:
                before_commit(update)

            # Bound the dedup window. The deque evicts its oldest entry on append, so
            # the identity set must be pruned in step or it would grow without limit
            # and eventually reject genuinely new ticks.
            maxlen = self._recent_identities.maxlen
            if maxlen is not None and len(self._recent_identities) >= maxlen:
                self._identity_set.discard(self._recent_identities[0])
            self._identity_set.add(identity)
            self._recent_identities.append(identity)
            self._last_exchange_ts[update.instrument_key] = observed
            self._latest[update.instrument_key] = update
            self._accepted += 1
            if self._last_update_at is None or observed > self._last_update_at:
                self._last_update_at = observed
            self._observations.append(update)
            self._apply_to_bars(update, observed)
            for subscription_id, (loop, _) in tuple(self._subscribers.items()):
                if not loop.is_closed():
                    # asyncio queues belong to their consumer loop, never a polling thread.
                    loop.call_soon_threadsafe(self._deliver, subscription_id, update)
            return PublishOutcome.ACCEPTED

    def _deliver(self, subscription_id: int, update: NormalizedFeedUpdate) -> None:
        with self._lock:
            subscription = self._subscribers.get(subscription_id)
            if subscription is None:
                return
            queue = subscription[1]
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(update)

    def _bar_now_epoch(self) -> float:
        """Single clock read used to decide whether a bar boundary has passed."""

        return self._clock.now().timestamp()

    def _apply_to_bars(self, update: NormalizedFeedUpdate, observed: datetime) -> None:
        if update.timeframe is not None:
            interval = BarInterval(update.timeframe)
            if update.available_at > self._clock.now():
                raise ValueError("BAR_NOT_YET_AVAILABLE")
            key: tuple[str, BarInterval] = (update.canonical_symbol, interval)
            bar = BarSnapshot(
                interval,
                int(update.timestamp.timestamp()),
                int(update.available_at.timestamp()),
                update.open,
                update.high,
                update.low,
                update.close,
                update.volume,
                None,
                0,
                True,
            )
            self._closed_bars.setdefault(key, deque(maxlen=self._history_limit)).append(bar)
            return
        price = update.chart_price
        if price is None:
            return
        for interval in BarInterval:
            start = align_bar_start(
                observed.timestamp(), interval.seconds, self.alignment_offset_minutes
            )
            key = (update.instrument_key, interval)
            current = self._bars.get(key)
            if current is None:
                current = _Bar(interval, start, start + interval.seconds)
                self._bars[key] = current
            elif start > current.start:
                current.is_closed = True
                self._closed_bars.setdefault(key, deque(maxlen=self._history_limit)).append(
                    _snapshot(current)
                )
                current = _Bar(interval, start, start + interval.seconds)
                self._bars[key] = current
            elif start < current.start:
                # Out-of-order bar period: refuse rather than rewrite history.
                continue
            current.apply(price, update.volume, update.open_interest)

    def footprint(self) -> dict[str, Any]:
        with self._lock:
            # Price ladder precision comes from the terminal, never a guessed constant.
            if not self._observations:
                return {
                    "provenance": "BROKER_TICK_PROXY",
                    "levels": [],
                    "reason": "NO_OBSERVATIONS",
                }
            if self.tick_size is None:
                return {
                    "provenance": "BROKER_TICK_PROXY",
                    "levels": [],
                    "reason": "TICK_SIZE_METADATA_REQUIRED",
                }
            return footprint_proxy(self._observations, self.tick_size)

    def latest(self, instrument_key: str) -> NormalizedFeedUpdate | None:
        with self._lock:
            require_xauusd(instrument_key)
            return self._latest.get(instrument_key)

    def instrument_keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._latest))

    def counters(self) -> FabricCounters:
        with self._lock:
            return FabricCounters(
                accepted=self._accepted,
                dropped_duplicate=self._dropped_duplicate,
                dropped_out_of_order=self._dropped_out_of_order,
                dropped_stale=self._dropped_stale,
                last_update_at=self._last_update_at,
            )

    def bars(self, instrument_key: str, interval: BarInterval) -> tuple[BarSnapshot, ...]:
        """Closed bars followed by the working bar.

        The working bar is reported as closed the moment its close boundary has
        passed, so a stalled feed cannot leave a finished bar looking live.
        """

        with self._lock:
            require_xauusd(instrument_key)
            closed = tuple(self._closed_bars.get((instrument_key, interval), ()))
            current = self._bars.get((instrument_key, interval))
            if current is None:
                return closed
            return closed + (_snapshot(current, now_epoch=self._bar_now_epoch()),)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def clock(self) -> ClockProtocol:
        """Read-only clock accessor so read models age data consistently."""

        return self._clock

    def subscribe(self, maxsize: int = 512) -> FabricSubscription:
        with self._lock:
            subscription_id = self._next_subscriber_id
            self._next_subscriber_id += 1
            queue: asyncio.Queue[NormalizedFeedUpdate] = asyncio.Queue(maxsize=maxsize)
            self._subscribers[subscription_id] = (asyncio.get_running_loop(), queue)
            return FabricSubscription(self, subscription_id, queue)

    def unsubscribe(self, subscription_id: int) -> None:
        """Release a consumer; safe to call twice."""

        with self._lock:
            _ = self._subscribers.pop(subscription_id, None)

    @property
    def attached(self) -> bool:
        """True whenever this instance is wired into the app.

        The router binds a fabric only when one exists, so an existing instance
        means an attachment; ``source_label`` may still be ``None`` and is then
        reported as unknown rather than invented.
        """

        return True

    def attach(self, *, source_label: str | None, authority_class: str | None = None) -> None:
        """Record which provider/source now feeds this fabric."""

        with self._lock:
            self.source_label = source_label
            if authority_class is not None:
                self.authority_class = authority_class

    def publish_many(self, updates: Iterable[NormalizedFeedUpdate]) -> tuple[PublishOutcome, ...]:
        """Publish a batch in caller order; used for history warm-load."""

        return tuple(self.publish(update) for update in updates)


def _snapshot(bar: _Bar, *, now_epoch: float | None = None) -> BarSnapshot:
    is_closed = bar.is_closed or (now_epoch is not None and now_epoch >= bar.close_ts)
    return BarSnapshot(
        interval=bar.interval,
        bar_start_epoch=bar.start,
        bar_close_epoch=bar.close_ts,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        open_interest=bar.open_interest,
        tick_count=bar.tick_count,
        is_closed=is_closed,
    )


__all__ = [
    "UTC_OFFSET_MINUTES",
    "BarInterval",
    "BarSnapshot",
    "FabricCounters",
    "FabricSubscription",
    "MarketDataFabric",
    "PublishOutcome",
    "align_bar_start",
]
