"""Pure in-memory replay with monotonic time and cursor-gated visibility."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid5

from pydantic import TypeAdapter

from ats.contracts.common import ClockProtocol, UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import MarketSnapshot

from .models import (
    ReplayConfiguration,
    ReplayCursor,
    ReplayDataset,
    ReplayPhase,
    ReplayState,
)

_UTC_ADAPTER = TypeAdapter(UTCDateTime)


class FutureDataAccessError(IndexError):
    """Raised when a consumer asks for data beyond the visible cursor."""


class ReplayTerminalError(RuntimeError):
    """Raised when advance is attempted after all fixture bars were emitted."""


class ReplayClock(ClockProtocol):
    """Explicit monotonic replay time; it never reads the wall clock."""

    __slots__ = ("_current",)

    def __init__(self, start_at: UTCDateTime) -> None:
        self._current = _UTC_ADAPTER.validate_python(start_at, strict=True)

    def now(self) -> UTCDateTime:
        return self._current

    def advance_to(self, timestamp: UTCDateTime) -> None:
        target = _UTC_ADAPTER.validate_python(timestamp, strict=True)
        if target < self._current:
            raise ValueError("replay clock cannot move backwards")
        self._current = target


class DeterministicReplay:
    """Consumer surface exposing only snapshots at or behind its cursor."""

    __slots__ = ("_clock", "_configuration", "_dataset", "_visible")

    def __init__(
        self,
        dataset: ReplayDataset,
        configuration: ReplayConfiguration,
        *,
        clock: ReplayClock | None = None,
    ) -> None:
        if configuration.start_at > dataset.manifest.first_bar:
            raise ValueError("replay start_at must not be after the first bar")
        self._dataset = dataset
        self._configuration = configuration
        self._clock = clock or ReplayClock(configuration.start_at)
        if self._clock.now() != configuration.start_at:
            raise ValueError("injected replay clock must equal configured start_at")
        self._visible: list[MarketSnapshot] = []

    @property
    def clock(self) -> ClockProtocol:
        return self._clock

    @property
    def state(self) -> ReplayState:
        count = len(self._visible)
        phase = (
            ReplayPhase.INITIAL
            if count == 0
            else ReplayPhase.TERMINAL
            if count == len(self._dataset.bars)
            else ReplayPhase.RUNNING
        )
        return ReplayState(
            phase=phase,
            cursor=ReplayCursor(
                visible_count=count,
                last_sequence=count,
                replay_time=self._clock.now(),
            ),
            total_bars=len(self._dataset.bars),
        )

    def advance(self) -> MarketSnapshot:
        index = len(self._visible)
        if index >= len(self._dataset.bars):
            raise ReplayTerminalError("replay is terminal")
        snapshot = self._snapshot(index)
        self._clock.advance_to(snapshot.received_at)
        self._visible.append(snapshot)
        return snapshot

    def current(self) -> MarketSnapshot:
        if not self._visible:
            raise FutureDataAccessError("no bar is visible before the first advance")
        return self._visible[-1]

    def snapshot_at(self, sequence: int) -> MarketSnapshot:
        if type(sequence) is not int or sequence <= 0:
            raise ValueError("sequence must be a positive integer")
        if sequence > len(self._visible):
            raise FutureDataAccessError("requested sequence is beyond the replay cursor")
        return self._visible[sequence - 1]

    def visible_snapshots(self) -> tuple[MarketSnapshot, ...]:
        return tuple(self._visible)

    def _snapshot(self, index: int) -> MarketSnapshot:
        bar = self._dataset.bars[index]
        manifest = self._dataset.manifest
        snapshot = MarketSnapshot(
            schema_version="1.0",
            snapshot_id=uuid5(
                manifest.dataset_id,
                f"{manifest.dataset_version}:{bar.source_sequence}:{bar.bar_timestamp.isoformat()}",
            ),
            instrument_id=bar.instrument_id,
            exchange=bar.exchange,
            segment=bar.segment,
            timeframe=bar.timeframe,
            bar_timestamp=bar.bar_timestamp,
            received_at=bar.bar_timestamp
            + timedelta(milliseconds=self._configuration.received_delay_ms),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            sequence=bar.source_sequence,
            quality_state=bar.quality_state,
            quality_flags=bar.quality_flags,
            source=manifest.source_description,
            source_version=manifest.dataset_version,
            session_state=bar.session_state,
            payload_hash="0" * 64,
        )
        return snapshot.model_copy(update={"payload_hash": compute_payload_hash(snapshot)})


__all__ = [
    "DeterministicReplay",
    "FutureDataAccessError",
    "ReplayClock",
    "ReplayTerminalError",
]
