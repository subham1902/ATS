"""Bounded O(1) hot quote and underlying caches with explicit resync state."""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import DataQualityState

from .models import (
    ActiveOptionWindow,
    ActiveWindowError,
    ActiveWindowErrorCode,
    HotOptionQuoteInput,
    HotOptionQuoteView,
    HotWindowSnapshot,
    IncrementalUnderlyingSnapshot,
    MarketStateFreshness,
    UnderlyingObservation,
)


class ActiveOptionQuoteCache:
    def __init__(self, window: ActiveOptionWindow, *, maximum_quote_age_ms: int) -> None:
        if isinstance(maximum_quote_age_ms, bool) or maximum_quote_age_ms <= 0:
            raise ValueError("maximum_quote_age_ms must be positive")
        self._window = window
        self._maximum_quote_age_ms = maximum_quote_age_ms
        self._active_ids = frozenset(window.contract_ids())
        self._quotes: dict[UUID, HotOptionQuoteInput] = {}
        self._resync_required = False

    def update(self, quote: HotOptionQuoteInput) -> bool:
        if quote.contract_id not in self._active_ids:
            raise ActiveWindowError(ActiveWindowErrorCode.CONTRACT_NOT_ACTIVE)
        previous = self._quotes.get(quote.contract_id)
        if previous is not None:
            if quote.quote_time < previous.quote_time:
                raise ActiveWindowError(ActiveWindowErrorCode.TIMESTAMP_REGRESSION)
            if quote.quote_time == previous.quote_time:
                if quote == previous:
                    return False
                raise ActiveWindowError(ActiveWindowErrorCode.TIMESTAMP_REGRESSION)
        self._quotes[quote.contract_id] = quote
        return True

    def mark_disconnected(self) -> None:
        self._quotes.clear()
        self._resync_required = True

    def complete_resync(self, *, as_of_time: UTCDateTime) -> None:
        snapshot = self.snapshot(as_of_time=as_of_time)
        if snapshot.missing_contract_ids:
            raise ValueError("cannot complete resync with missing active quotes")
        if any(item.quote_age_ms > self._maximum_quote_age_ms for item in snapshot.quotes):
            raise ValueError("cannot complete resync with stale quotes")
        if any(item.quality is not DataQualityState.GOOD for item in snapshot.quotes):
            raise ValueError("cannot complete resync with unsafe quote quality")
        self._resync_required = False

    def snapshot(self, *, as_of_time: UTCDateTime) -> HotWindowSnapshot:
        missing = tuple(sorted(self._active_ids - self._quotes.keys(), key=str))
        views: list[HotOptionQuoteView] = []
        for contract_id in sorted(self._quotes, key=str):
            quote = self._quotes[contract_id]
            age = as_of_time - quote.quote_time
            if age.total_seconds() < 0:
                raise ActiveWindowError(ActiveWindowErrorCode.TIMESTAMP_REGRESSION)
            age_ms = age.days * 86_400_000 + age.seconds * 1_000 + age.microseconds // 1_000
            spread = (
                quote.ask - quote.bid if quote.ask is not None and quote.bid is not None else None
            )
            views.append(
                HotOptionQuoteView(
                    contract_id=quote.contract_id,
                    quote_time=quote.quote_time,
                    bid=quote.bid,
                    ask=quote.ask,
                    bid_quantity=quote.bid_quantity,
                    ask_quantity=quote.ask_quantity,
                    last_price=quote.last_price,
                    volume=quote.volume,
                    open_interest=quote.open_interest,
                    implied_volatility=quote.implied_volatility,
                    delta=quote.delta,
                    gamma=quote.gamma,
                    theta=quote.theta,
                    vega=quote.vega,
                    spread=spread,
                    quote_age_ms=age_ms,
                    quality=quote.quality,
                )
            )
        freshness = self._freshness(tuple(views), missing)
        return HotWindowSnapshot(
            window=self._window,
            as_of_time=as_of_time,
            freshness=freshness,
            quotes=tuple(views),
            missing_contract_ids=missing,
        )

    def _freshness(
        self, quotes: tuple[HotOptionQuoteView, ...], missing: tuple[UUID, ...]
    ) -> MarketStateFreshness:
        if self._resync_required:
            return MarketStateFreshness.RESYNC_REQUIRED
        if missing:
            return MarketStateFreshness.UNKNOWN
        if any(item.quality is not DataQualityState.GOOD for item in quotes):
            return MarketStateFreshness.UNKNOWN
        if any(item.quote_age_ms > self._maximum_quote_age_ms for item in quotes):
            return MarketStateFreshness.STALE
        return MarketStateFreshness.FRESH


class IncrementalUnderlyingCache:
    def __init__(self, *, maximum_points: int) -> None:
        if isinstance(maximum_points, bool) or maximum_points <= 0:
            raise ValueError("maximum_points must be positive")
        self._observations: deque[UnderlyingObservation] = deque(maxlen=maximum_points)
        self._rolling_sum = Decimal("0")
        self._freshness = MarketStateFreshness.UNKNOWN

    def update(self, observation: UnderlyingObservation) -> bool:
        if self._freshness is MarketStateFreshness.RESYNC_REQUIRED:
            raise ActiveWindowError(ActiveWindowErrorCode.SEQUENCE_GAP)
        if self._observations:
            previous = self._observations[-1]
            if observation.underlying is not previous.underlying:
                raise ValueError("one underlying cache accepts one underlying")
            if observation.sequence == previous.sequence and observation == previous:
                return False
            if observation.sequence != previous.sequence + 1:
                self._freshness = MarketStateFreshness.RESYNC_REQUIRED
                raise ActiveWindowError(ActiveWindowErrorCode.SEQUENCE_GAP)
            if observation.event_time <= previous.event_time:
                raise ActiveWindowError(ActiveWindowErrorCode.TIMESTAMP_REGRESSION)
        if len(self._observations) == self._observations.maxlen:
            self._rolling_sum -= self._observations[0].price
        self._observations.append(observation)
        self._rolling_sum += observation.price
        self._freshness = (
            MarketStateFreshness.FRESH
            if observation.quality is DataQualityState.GOOD
            else MarketStateFreshness.UNKNOWN
        )
        return True

    def resynchronize(self, observation: UnderlyingObservation) -> None:
        self._observations.clear()
        self._observations.append(observation)
        self._rolling_sum = observation.price
        self._freshness = (
            MarketStateFreshness.FRESH
            if observation.quality is DataQualityState.GOOD
            else MarketStateFreshness.UNKNOWN
        )

    def snapshot(self) -> IncrementalUnderlyingSnapshot:
        if not self._observations:
            raise ValueError("underlying cache is empty")
        return IncrementalUnderlyingSnapshot(
            underlying=self._observations[-1].underlying,
            freshness=self._freshness,
            observations=tuple(self._observations),
            rolling_price_sum=self._rolling_sum,
        )


__all__ = ["ActiveOptionQuoteCache", "IncrementalUnderlyingCache"]
