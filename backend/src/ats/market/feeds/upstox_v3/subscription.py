"""Subscription registry binding provider keys to canonical ATS identities.

The registry is the single source of truth for what the feed must be
subscribed to. Provider instrument keys are aliases registered against a
canonical ATS identity; a reused provider token can therefore never mutate an
ATS identity, and full re-subscription after reconnect replays exactly this
state.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from ats.contracts.domain.types import NonEmptyStr

from .config import FeedMode
from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .instrument_keys import validate_feed_key


class SubscriptionEntry(BaseModel):
    """One registered alias with its canonical binding and requested mode."""

    instrument_key: NonEmptyStr
    ats_identity: NonEmptyStr
    mode: FeedMode

    @model_validator(mode="after")
    def validate_key(self) -> SubscriptionEntry:
        validate_feed_key(self.instrument_key)
        return self

    def __lt__(self, other: SubscriptionEntry) -> bool:
        return self.instrument_key < other.instrument_key


class SubscriptionRegistry:
    """Deterministic, insertion-safe registry with fail-closed duplicates."""

    def __init__(self) -> None:
        self._entries: dict[str, SubscriptionEntry] = {}

    def register(
        self, *, instrument_key: str, ats_identity: str, mode: FeedMode
    ) -> SubscriptionEntry:
        entry = SubscriptionEntry(
            instrument_key=instrument_key, ats_identity=ats_identity, mode=mode
        )
        if entry.instrument_key in self._entries:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.DUPLICATE_INSTRUMENT_KEY,
                f"{entry.instrument_key} is already registered",
            )
        self._entries[entry.instrument_key] = entry
        return entry

    def unregister(self, *, instrument_key: str) -> SubscriptionEntry:
        try:
            return self._entries.pop(instrument_key)
        except KeyError as exc:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.UNKNOWN_INSTRUMENT_KEY,
                f"{instrument_key} was never registered",
            ) from exc

    def require(self, instrument_key: str) -> SubscriptionEntry:
        try:
            return self._entries[instrument_key]
        except KeyError as exc:
            raise UpstoxFeedError(
                UpstoxFeedErrorCode.UNKNOWN_INSTRUMENT_KEY,
                f"{instrument_key} is not part of this subscription set",
            ) from exc

    def is_registered(self, instrument_key: str) -> bool:
        return instrument_key in self._entries

    def entries(self) -> tuple[SubscriptionEntry, ...]:
        return tuple(sorted(self._entries.values()))

    def instrument_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def snapshot_by_mode(self) -> tuple[tuple[FeedMode, tuple[str, ...]], ...]:
        grouped: dict[FeedMode, list[str]] = {}
        for key in sorted(self._entries):
            grouped.setdefault(self._entries[key].mode, []).append(key)
        return tuple(
            (mode, tuple(keys))
            for mode, keys in sorted(grouped.items(), key=lambda item: item[0].value)
        )

    def __len__(self) -> int:
        return len(self._entries)


__all__ = ["SubscriptionEntry", "SubscriptionRegistry"]
