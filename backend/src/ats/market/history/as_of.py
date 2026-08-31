"""As-of information gates enforcing the AS_OF_INFORMATION_MODEL.

These pure functions admit observations at a simulated decision time ``T``
exactly when ``observation.times.available_to_strategy_time <= T``, resolve
correction (supersede) chains among the visible window, and expose derivative
knowledge such as expiries strictly as of ``T``.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from uuid import UUID

from ats.contracts.common import UTCDateTime

from .errors import FutureInformationError, HistoricalTruthErrorCode
from .models import ContractMetadataPayload, MarketObservation


class AsOfTimeline:
    """Pre-sorted visibility index for one immutable observation collection.

    Building the timeline costs ``O(n log n)`` once; every subsequent
    :meth:`visible` query is a binary search plus a linear walk over the
    visible prefix instead of a full re-sort. Semantics are identical to
    :func:`visible_observations`.
    """

    __slots__ = ("_availability", "_hidden_from", "_records")

    def __init__(self, observations: Iterable[MarketObservation]) -> None:
        records = tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.times.available_to_strategy_time,
                    item.times.event_time,
                    item.observation_id,
                ),
            )
        )
        self._records = records
        self._availability = [item.times.available_to_strategy_time for item in records]
        identity_set = {item.observation_id for item in records}
        hidden_from: dict[UUID, UTCDateTime] = {}
        for item in records:
            target = item.supersedes
            if target is None or target not in identity_set:
                continue
            availability = item.times.available_to_strategy_time
            known = hidden_from.get(target)
            if known is None or availability < known:
                hidden_from[target] = availability
        self._hidden_from = hidden_from

    def visible(self, at_time: UTCDateTime) -> tuple[MarketObservation, ...]:
        """Return the deterministic visible window at ``at_time``."""

        cutoff = bisect_right(self._availability, at_time)
        visible: list[MarketObservation] = []
        for record in self._records[:cutoff]:
            hidden_at = self._hidden_from.get(record.observation_id)
            if hidden_at is not None and hidden_at <= at_time:
                continue
            visible.append(record)
        return tuple(visible)


def is_admissible_as_of(observation: MarketObservation, *, at_time: UTCDateTime) -> bool:
    """Return whether the observation satisfies the as-of admission rule."""

    return observation.times.available_to_strategy_time <= at_time


def require_available(observation: MarketObservation, *, at_time: UTCDateTime) -> MarketObservation:
    """Return the observation, or raise if it is not available at ``at_time``."""

    if not is_admissible_as_of(observation, at_time=at_time):
        raise FutureInformationError(
            HistoricalTruthErrorCode.FUTURE_INFORMATION_NOT_AVAILABLE,
            f"observation {observation.observation_id} becomes available at "
            f"{observation.times.available_to_strategy_time.isoformat()}, after "
            f"decision time {at_time.isoformat()}",
        )
    return observation


def visible_observations(
    observations: Iterable[MarketObservation], *, at_time: UTCDateTime
) -> tuple[MarketObservation, ...]:
    """Return the deterministic visible window at ``at_time``.

    Records with ``available_to_strategy_time > at_time`` are never returned.
    Within the visible window any record superseded by another visible record
    is replaced by its reviser. Output order is
    ``(available_to_strategy_time, event_time, observation_id)``.

    For repeated queries over the same collection prefer building an
    :class:`AsOfTimeline` once and calling :meth:`AsOfTimeline.visible`.
    """

    return AsOfTimeline(observations).visible(at_time)


def known_expiries_as_of(
    observations: Iterable[MarketObservation],
    *,
    underlying: str,
    at_time: UTCDateTime,
) -> tuple[str, ...]:
    """Return contract expiries genuinely known for ``underlying`` at ``at_time``."""

    expiries: set[str] = set()
    for observation in visible_observations(observations, at_time=at_time):
        if not isinstance(observation.payload, ContractMetadataPayload):
            continue
        if observation.payload.underlying == underlying:
            expiries.add(observation.payload.expiry_date)
    return tuple(sorted(expiries))


def latest_contract_metadata_as_of(
    observations: Iterable[MarketObservation],
    *,
    trading_symbol: str,
    at_time: UTCDateTime,
) -> MarketObservation | None:
    """Return the newest visible contract-master row for ``trading_symbol``."""

    candidates = [
        item
        for item in visible_observations(observations, at_time=at_time)
        if isinstance(item.payload, ContractMetadataPayload)
        and item.payload.trading_symbol == trading_symbol
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item.times.available_to_strategy_time, item.observation_id),
    )


__all__ = [
    "AsOfTimeline",
    "is_admissible_as_of",
    "known_expiries_as_of",
    "latest_contract_metadata_as_of",
    "require_available",
    "visible_observations",
]
