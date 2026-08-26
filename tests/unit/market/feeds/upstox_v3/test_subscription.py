from __future__ import annotations

import pytest
from ats.market.feeds.upstox_v3 import (
    FeedMode,
    SubscriptionRegistry,
    UpstoxFeedError,
    UpstoxFeedErrorCode,
)

from . import helpers as fix
from .helpers import INDEX_KEY, OPTION_KEY, SECOND_OPTION_KEY


class TestRegistration:
    def test_register_and_lookup(self) -> None:
        registry = SubscriptionRegistry()
        entry = registry.register(
            instrument_key=INDEX_KEY, ats_identity="UNDERLYING:NIFTY", mode=FeedMode.FULL
        )
        assert registry.require(INDEX_KEY) is entry
        assert len(registry) == 1

    def test_duplicate_key_fails_closed(self) -> None:
        registry = SubscriptionRegistry()
        registry.register(instrument_key=INDEX_KEY, ats_identity="A", mode=FeedMode.FULL)
        with pytest.raises(UpstoxFeedError) as error:
            registry.register(instrument_key=INDEX_KEY, ats_identity="B", mode=FeedMode.LTPC)
        assert error.value.code is UpstoxFeedErrorCode.DUPLICATE_INSTRUMENT_KEY

    def test_unknown_key_fails_closed(self) -> None:
        registry = SubscriptionRegistry()
        with pytest.raises(UpstoxFeedError) as error:
            registry.require(OPTION_KEY)
        assert error.value.code is UpstoxFeedErrorCode.UNKNOWN_INSTRUMENT_KEY

    def test_malformed_key_never_enters_registry(self) -> None:
        registry = SubscriptionRegistry()
        with pytest.raises(UpstoxFeedError):
            registry.register(instrument_key="malformed key", ats_identity="A", mode=FeedMode.FULL)
        assert len(registry) == 0

    def test_unregister_requires_membership(self) -> None:
        registry = SubscriptionRegistry()
        registry.register(instrument_key=INDEX_KEY, ats_identity="A", mode=FeedMode.FULL)
        registry.unregister(instrument_key=INDEX_KEY)
        with pytest.raises(UpstoxFeedError):
            registry.unregister(instrument_key=INDEX_KEY)


class TestSnapshots:
    def test_snapshot_groups_by_mode_with_sorted_keys(self) -> None:
        snapshot = dict(fix.registry().snapshot_by_mode())
        assert snapshot[FeedMode.FULL] == (INDEX_KEY,)
        assert snapshot[FeedMode.OPTION_GREEKS] == (OPTION_KEY,)
        assert snapshot[FeedMode.LTPC] == (SECOND_OPTION_KEY,)

    def test_entries_are_sorted_and_bound_to_canonical_identities(self) -> None:
        entries = fix.registry().entries()
        assert [entry.instrument_key for entry in entries] == sorted(
            [INDEX_KEY, OPTION_KEY, SECOND_OPTION_KEY]
        )
        ce = next(entry for entry in entries if entry.instrument_key == OPTION_KEY)
        assert ce.ats_identity == "CONTRACT:TEST-ONLY-CE"

    def test_full_resubscription_snapshot_is_stable(self) -> None:
        first = fix.registry().snapshot_by_mode()
        second = fix.registry().snapshot_by_mode()
        assert first == second
