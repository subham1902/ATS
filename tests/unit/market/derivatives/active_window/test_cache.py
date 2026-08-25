from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.types import DataQualityState
from ats.market.derivatives.active_window import (
    ActiveOptionQuoteCache,
    ActiveWindowError,
    HotOptionQuoteInput,
    IncrementalUnderlyingCache,
    MarketStateFreshness,
    UnderlyingObservation,
    build_active_option_window,
)
from ats.market.derivatives.contract_master import DerivativeUnderlying

from .test_engine import NOW, policy, universe


def window():
    return build_active_option_window(
        contracts=universe(),
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal("115"),
        as_of_time=NOW,
        policy=policy(),
    )


def quote(contract_id, *, offset_ms: int = 0, bid: str = "10", quality=DataQualityState.GOOD):
    at = NOW + timedelta(milliseconds=offset_ms)
    return HotOptionQuoteInput(
        contract_id=contract_id,
        quote_time=at,
        received_at=at,
        bid=Decimal(bid),
        ask=Decimal("12"),
        bid_quantity=10,
        ask_quantity=12,
        last_price=Decimal("11"),
        volume=100,
        open_interest=1000,
        implied_volatility=0.2,
        delta=None,
        gamma=None,
        theta=None,
        vega=None,
        quality=quality,
    )


def fill(cache: ActiveOptionQuoteCache, *, offset_ms: int = 0) -> None:
    for contract_id in window().contract_ids():
        cache.update(quote(contract_id, offset_ms=offset_ms))


def test_missing_quotes_unknown_then_complete_window_fresh() -> None:
    active = window()
    cache = ActiveOptionQuoteCache(active, maximum_quote_age_ms=1000)
    assert cache.snapshot(as_of_time=NOW).freshness is MarketStateFreshness.UNKNOWN
    for contract_id in active.contract_ids():
        cache.update(quote(contract_id))
    snapshot = cache.snapshot(as_of_time=NOW + timedelta(milliseconds=500))
    assert snapshot.freshness is MarketStateFreshness.FRESH
    assert all(item.spread == Decimal("2") for item in snapshot.quotes)


def test_quote_staleness_is_policy_driven() -> None:
    active = window()
    cache = ActiveOptionQuoteCache(active, maximum_quote_age_ms=1000)
    for contract_id in active.contract_ids():
        cache.update(quote(contract_id))
    assert (
        cache.snapshot(as_of_time=NOW + timedelta(milliseconds=1001)).freshness
        is MarketStateFreshness.STALE
    )


def test_disconnect_invalidates_cache_until_complete_fresh_resync() -> None:
    active = window()
    cache = ActiveOptionQuoteCache(active, maximum_quote_age_ms=1000)
    for contract_id in active.contract_ids():
        cache.update(quote(contract_id))
    cache.mark_disconnected()
    assert cache.snapshot(as_of_time=NOW).freshness is MarketStateFreshness.RESYNC_REQUIRED
    for contract_id in active.contract_ids():
        cache.update(quote(contract_id, offset_ms=10))
    cache.complete_resync(as_of_time=NOW + timedelta(milliseconds=10))
    assert (
        cache.snapshot(as_of_time=NOW + timedelta(milliseconds=10)).freshness
        is MarketStateFreshness.FRESH
    )


def test_duplicate_is_idempotent_and_conflicting_or_regressed_quote_rejected() -> None:
    active = window()
    cache = ActiveOptionQuoteCache(active, maximum_quote_age_ms=1000)
    first = quote(active.contract_ids()[0], offset_ms=10)
    assert cache.update(first)
    assert not cache.update(first)
    with pytest.raises(ActiveWindowError):
        cache.update(first.model_copy(update={"bid": Decimal("9")}))
    with pytest.raises(ActiveWindowError):
        cache.update(quote(active.contract_ids()[0], offset_ms=5))


def test_non_active_contract_is_rejected() -> None:
    active = window()
    other = UUID(int=999)
    with pytest.raises(ActiveWindowError):
        ActiveOptionQuoteCache(active, maximum_quote_age_ms=1000).update(quote(other))


def observation(sequence: int, *, price: str | None = None) -> UnderlyingObservation:
    at = NOW + timedelta(milliseconds=sequence)
    return UnderlyingObservation(
        underlying=DerivativeUnderlying.NIFTY,
        sequence=sequence,
        event_time=at,
        received_at=at,
        price=Decimal(price or str(100 + sequence)),
        quality=DataQualityState.GOOD,
    )


def test_incremental_cache_is_bounded_and_updates_rolling_sum_without_history_recompute() -> None:
    cache = IncrementalUnderlyingCache(maximum_points=3)
    for sequence in range(1, 5):
        cache.update(observation(sequence))
    snapshot = cache.snapshot()
    assert tuple(item.sequence for item in snapshot.observations) == (2, 3, 4)
    assert snapshot.rolling_price_sum == Decimal("309")


def test_incremental_duplicate_is_idempotent_and_gap_requires_resync() -> None:
    cache = IncrementalUnderlyingCache(maximum_points=3)
    first = observation(1)
    cache.update(first)
    assert not cache.update(first)
    with pytest.raises(ActiveWindowError):
        cache.update(observation(3))
    assert cache.snapshot().freshness is MarketStateFreshness.RESYNC_REQUIRED
    with pytest.raises(ActiveWindowError):
        cache.update(observation(2))
    cache.resynchronize(observation(10))
    assert cache.snapshot().freshness is MarketStateFreshness.FRESH
    assert tuple(item.sequence for item in cache.snapshot().observations) == (10,)
