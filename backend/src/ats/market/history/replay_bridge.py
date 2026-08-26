"""History-truth bridge over the existing B01 deterministic replay.

The bridge converts approved replay bars into canonical historical
observations with explicit availability times, then gates their visibility by
the AS_OF_INFORMATION_MODEL while the underlying :class:`DeterministicReplay`
keeps its own cursor semantics untouched. Determinism of B01 is preserved:
this module only reads its public surface and never mutates it.
"""

from __future__ import annotations

from datetime import timedelta

from ats.contracts.common import ATSBaseModel, ClockProtocol
from ats.contracts.domain.models import MarketSnapshot
from ats.contracts.domain.types import NonNegativeInt
from ats.contracts.hashing import canonical_sha256
from ats.market.replay.engine import DeterministicReplay
from ats.market.replay.models import ReplayBar, ReplayConfiguration, ReplayDataset, ReplayState

from .as_of import visible_observations
from .builder import build_market_observation
from .errors import HistoricalTruthError, HistoricalTruthErrorCode
from .models import (
    MarketBarPayload,
    MarketObservation,
    ObservationKind,
    ObservationTimes,
    RawRecordReference,
)


class HistoryTimeSemantics(ATSBaseModel):
    """Deterministic delays separating the four clocks in replay bridges."""

    source_publication_delay_ms: NonNegativeInt = 0
    ingestion_delay_ms: NonNegativeInt = 0
    strategy_visibility_delay_ms: NonNegativeInt = 0


DEFAULT_HISTORY_TIME_SEMANTICS = HistoryTimeSemantics(
    source_publication_delay_ms=100,
    ingestion_delay_ms=100,
    strategy_visibility_delay_ms=50,
)


def historical_bar_observations(
    dataset: ReplayDataset,
    *,
    semantics: HistoryTimeSemantics | None = None,
) -> tuple[MarketObservation, ...]:
    """Convert replay bars into canonical observations with availability times."""

    active_semantics = semantics or DEFAULT_HISTORY_TIME_SEMANTICS
    manifest = dataset.manifest
    observations: list[MarketObservation] = []
    for bar in dataset.bars:
        event_time = bar.bar_timestamp
        source_time = event_time + timedelta(
            milliseconds=active_semantics.source_publication_delay_ms
        )
        ingest_time = source_time + timedelta(
            milliseconds=active_semantics.ingestion_delay_ms
        )
        available_to_strategy_time = ingest_time + timedelta(
            milliseconds=active_semantics.strategy_visibility_delay_ms
        )
        observations.append(
            build_market_observation(
                instrument=bar.instrument_id,
                times=ObservationTimes(
                    event_time=event_time,
                    source_time=source_time,
                    ingest_time=ingest_time,
                    available_to_strategy_time=available_to_strategy_time,
                ),
                payload=MarketBarPayload(
                    payload_kind=ObservationKind.MARKET_BAR,
                    timeframe=bar.timeframe,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                ),
                provenance=RawRecordReference(
                    source_id=manifest.source_description,
                    raw_record_sha256=_raw_bar_digest(bar),
                    raw_location=f"{manifest.dataset_id}:{bar.source_sequence}",
                ),
                quality_state=bar.quality_state,
                quality_flags=bar.quality_flags,
            )
        )
    return tuple(observations)


class HistoricalReplaySession:
    """B01 replay with an independent as-of gate over canonical history.

    ``advance`` emits exactly one replay snapshot (unchanged B01 behavior) and
    re-derives the visible observation window from availability times at the
    current replay instant, verifying that both layers describe identical
    facts for the emitted bar.
    """

    __slots__ = ("_advances", "_observations", "_replay", "_visible")

    def __init__(
        self, replay: DeterministicReplay, observations: tuple[MarketObservation, ...]
    ) -> None:
        if len(observations) != replay.state.total_bars:
            raise HistoricalTruthError(
                HistoricalTruthErrorCode.HISTORY_REPLAY_MISALIGNED,
                "history observation count does not match replay bar count",
            )
        self._replay = replay
        self._observations = observations
        self._visible: tuple[MarketObservation, ...] = ()
        self._advances = 0

    @property
    def clock(self) -> ClockProtocol:
        return self._replay.clock

    @property
    def state(self) -> ReplayState:
        return self._replay.state

    def advance(self) -> MarketSnapshot:
        index = self._advances
        snapshot = self._replay.advance()
        _verify_alignment(snapshot, self._observations[index])
        self._advances += 1
        self._visible = visible_observations(
            self._observations, at_time=self._replay.clock.now()
        )
        return snapshot

    def visible_observations(self) -> tuple[MarketObservation, ...]:
        """Return observations whose availability precedes the replay instant."""

        return self._visible


def create_history_gated_replay(
    dataset: ReplayDataset,
    configuration: ReplayConfiguration,
    *,
    semantics: HistoryTimeSemantics | None = None,
) -> HistoricalReplaySession:
    """Create a B01 replay together with its gated historical window."""

    replay = DeterministicReplay(dataset, configuration)
    return HistoricalReplaySession(
        replay, historical_bar_observations(dataset, semantics=semantics)
    )


def _raw_bar_digest(bar: ReplayBar) -> str:
    return canonical_sha256(bar)


def _verify_alignment(snapshot: MarketSnapshot, observation: MarketObservation) -> None:
    payload = observation.payload
    mismatch = (
        observation.times.event_time != snapshot.bar_timestamp
        or observation.instrument != snapshot.instrument_id
        or payload.payload_kind is not ObservationKind.MARKET_BAR
        or payload.open != snapshot.open
        or payload.high != snapshot.high
        or payload.low != snapshot.low
        or payload.close != snapshot.close
        or payload.volume != snapshot.volume
    )
    if mismatch:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.HISTORY_REPLAY_MISALIGNED,
            f"snapshot {snapshot.snapshot_id} does not match its historical "
            f"observation {observation.observation_id}",
        )


__all__ = [
    "DEFAULT_HISTORY_TIME_SEMANTICS",
    "HistoricalReplaySession",
    "HistoryTimeSemantics",
    "create_history_gated_replay",
    "historical_bar_observations",
]
