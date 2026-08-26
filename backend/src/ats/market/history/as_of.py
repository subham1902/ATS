"""As-of information gates enforcing the AS_OF_INFORMATION_MODEL.

These pure functions admit observations at a simulated decision time ``T``
exactly when ``observation.times.available_to_strategy_time <= T``, resolve
correction (supersede) chains among the visible window, and expose derivative
knowledge such as expiries strictly as of ``T``.
"""

from __future__ import annotations

from collections.abc import Iterable

from ats.contracts.common import UTCDateTime

from .errors import FutureInformationError, HistoricalTruthErrorCode
from .models import ContractMetadataPayload, MarketObservation


def is_admissible_as_of(observation: MarketObservation, *, at_time: UTCDateTime) -> bool:
    """Return whether the observation satisfies the as-of admission rule."""

    return observation.times.available_to_strategy_time <= at_time


def require_available(
    observation: MarketObservation, *, at_time: UTCDateTime
) -> MarketObservation:
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
    """

    visible = [
        item for item in observations if item.times.available_to_strategy_time <= at_time
    ]
    visible_ids = {item.observation_id for item in visible}
    superseded = {
        item.supersedes
        for item in visible
        if item.supersedes is not None and item.supersedes in visible_ids
    }
    effective = [item for item in visible if item.observation_id not in superseded]
    effective.sort(
        key=lambda item: (
            item.times.available_to_strategy_time,
            item.times.event_time,
            item.observation_id,
        )
    )
    return tuple(effective)


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
    "is_admissible_as_of",
    "known_expiries_as_of",
    "latest_contract_metadata_as_of",
    "require_available",
    "visible_observations",
]
