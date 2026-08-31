"""Immutable validated container binding a canonical dataset to its manifest."""

from __future__ import annotations

from pydantic import PrivateAttr

from ats.contracts.common import ATSBaseModel, SchemaVersion, UTCDateTime

from .as_of import AsOfTimeline, known_expiries_as_of, latest_contract_metadata_as_of
from .models import DatasetManifest, MarketObservation


class HistoricalDataset(ATSBaseModel):
    """Immutable, sorted collection of canonical historical observations.

    Construction is restricted to
    :func:`ats.market.history.build_historical_dataset`, which fails closed on
    any ``INVALID`` validation finding before the manifest is derived.
    Consumers read the dataset only through as-of methods. Visibility queries
    reuse one pre-sorted :class:`AsOfTimeline` so repeated as-of lookups stay
    ``O(log n)`` per query after the first.
    """

    schema_version: SchemaVersion = "1.0"
    manifest: DatasetManifest
    observations: tuple[MarketObservation, ...]

    _timeline: AsOfTimeline | None = PrivateAttr(default=None)

    @property
    def timeline(self) -> AsOfTimeline:
        """Return the lazily-built shared visibility index."""

        if self._timeline is None:
            self._timeline = AsOfTimeline(self.observations)
        return self._timeline

    def visible_as_of(self, at_time: UTCDateTime) -> tuple[MarketObservation, ...]:
        """Return observations genuinely available to a strategy at ``at_time``."""

        return self.timeline.visible(at_time)

    def known_expiries_as_of(self, underlying: str, at_time: UTCDateTime) -> tuple[str, ...]:
        """Return expiries genuinely known for ``underlying`` at ``at_time``."""

        return known_expiries_as_of(self.observations, underlying=underlying, at_time=at_time)

    def latest_contract_metadata_as_of(
        self, trading_symbol: str, at_time: UTCDateTime
    ) -> MarketObservation | None:
        """Return the newest visible contract-master row for ``trading_symbol``."""

        return latest_contract_metadata_as_of(
            self.observations, trading_symbol=trading_symbol, at_time=at_time
        )


__all__ = ["HistoricalDataset"]
