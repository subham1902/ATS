"""Centralized subscription registry for provider feeds."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from ats.market.feeds.upstox_v3.config import FeedMode

LOGGER = logging.getLogger(__name__)


@dataclass
class SubscriptionRecord:
    """Tracking metadata for one instrument subscription."""

    instrument_key: str
    requested_mode: FeedMode
    effective_mode: FeedMode
    consumer_count: int = 1
    last_subscribed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_update_at: datetime | None = None
    status: Literal["ACTIVE", "PENDING", "UNSUBSCRIBED", "DOWNGRADED"] = "PENDING"


class SubscriptionRegistry:
    """Central registry managing provider feed subscriptions and reference counts."""

    def __init__(self, provider: str = "upstox") -> None:
        self.provider = provider
        self._subscriptions: dict[str, SubscriptionRecord] = {}

    def subscribe(
        self,
        instrument_key: str,
        mode: FeedMode | str = FeedMode.FULL,
        consumer_id: str | None = None,
    ) -> tuple[SubscriptionRecord, bool]:
        """Register or increment interest for an instrument.

        Returns (record, is_new_subscription).
        """
        feed_mode = (
            FeedMode.FULL
            if (isinstance(mode, str) and mode.lower() == "full")
            else (mode if isinstance(mode, FeedMode) else FeedMode.LTPC)
        )
        existing = self._subscriptions.get(instrument_key)
        if existing is not None and existing.status != "UNSUBSCRIBED":
            existing.consumer_count += 1
            if feed_mode == FeedMode.FULL and existing.requested_mode != FeedMode.FULL:
                existing.requested_mode = FeedMode.FULL
                existing.effective_mode = FeedMode.FULL
            return existing, False

        record = SubscriptionRecord(
            instrument_key=instrument_key,
            requested_mode=feed_mode,
            effective_mode=feed_mode,
            consumer_count=1,
            last_subscribed_at=datetime.now(UTC),
            status="PENDING",
        )
        self._subscriptions[instrument_key] = record
        LOGGER.info(
            "Registered subscription for [%s] mode=%s consumer=%s (provider: %s)",
            instrument_key,
            feed_mode,
            consumer_id,
            self.provider,
        )
        return record, True

    def unsubscribe(
        self, instrument_key: str, consumer_id: str | None = None
    ) -> tuple[SubscriptionRecord | None, bool]:
        """Decrement reference count; returns (record, should_unsubscribe_upstream)."""
        existing = self._subscriptions.get(instrument_key)
        if existing is None:
            return None, False

        existing.consumer_count -= 1
        if existing.consumer_count <= 0:
            existing.status = "UNSUBSCRIBED"
            existing.consumer_count = 0
            LOGGER.info(
                "Unsubscribed upstream for [%s] (provider: %s)",
                instrument_key,
                self.provider,
            )
            return existing, True
        return existing, False

    def change_mode(self, instrument_key: str, mode: FeedMode) -> SubscriptionRecord | None:
        existing = self._subscriptions.get(instrument_key)
        if existing is not None:
            existing.requested_mode = mode
            existing.effective_mode = mode
        return existing

    def mark_active(self, instrument_key: str, effective_mode: FeedMode | None = None) -> None:
        existing = self._subscriptions.get(instrument_key)
        if existing is not None:
            existing.status = "ACTIVE"
            if effective_mode is not None:
                existing.effective_mode = effective_mode

    def record_update(self, instrument_key: str, timestamp: datetime | None = None) -> None:
        existing = self._subscriptions.get(instrument_key)
        if existing is not None:
            existing.last_update_at = timestamp or datetime.now(UTC)
            if existing.status == "PENDING":
                existing.status = "ACTIVE"

    def get_active_keys(self) -> tuple[str, ...]:
        return tuple(
            k for k, s in self._subscriptions.items() if s.status in ("ACTIVE", "PENDING")
        )

    @property
    def active_count(self) -> int:
        return len(self.get_active_keys())

    def is_subscribed(self, instrument_key: str) -> bool:
        return instrument_key in self.get_active_keys()

    def get_all(self) -> tuple[SubscriptionRecord, ...]:
        return tuple(self._subscriptions.values())

    def get(self, instrument_key: str) -> SubscriptionRecord | None:
        return self._subscriptions.get(instrument_key)
