from __future__ import annotations

from datetime import timedelta

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market import (
    FutureDataAccessError,
    ReplayClock,
    ReplayPhase,
    ReplayTerminalError,
)

from tests.unit.market.fixtures import make_replay


def test_replay_clock_is_explicit_monotonic_and_rejects_naive_time() -> None:
    replay = make_replay()
    clock = ReplayClock(replay.state.cursor.replay_time)
    clock.advance_to(clock.now() + timedelta(seconds=1))
    with pytest.raises(ValueError, match="backwards"):
        clock.advance_to(clock.now() - timedelta(seconds=1))
    with pytest.raises(ValueError):
        ReplayClock(clock.now().replace(tzinfo=None))


def test_cursor_hides_all_future_data_until_advance() -> None:
    replay = make_replay()
    assert replay.state.phase is ReplayPhase.INITIAL
    assert replay.visible_snapshots() == ()
    with pytest.raises(FutureDataAccessError):
        replay.current()
    with pytest.raises(FutureDataAccessError):
        replay.snapshot_at(1)
    first = replay.advance()
    assert replay.current() == first
    assert replay.snapshot_at(1) == first
    with pytest.raises(FutureDataAccessError):
        replay.snapshot_at(2)


def test_snapshot_conversion_is_exact_and_canonically_hashed() -> None:
    snapshot = make_replay().advance()
    assert (snapshot.exchange, snapshot.segment, snapshot.timeframe) == ("NSE", "CASH", "5m")
    assert snapshot.sequence == 1
    assert snapshot.received_at == snapshot.bar_timestamp + timedelta(milliseconds=250)
    assert snapshot.payload_hash == compute_payload_hash(snapshot)


def test_terminal_replay_cannot_advance_again() -> None:
    replay = make_replay()
    snapshots = tuple(replay.advance() for _ in range(replay.state.total_bars))
    assert replay.state.phase is ReplayPhase.TERMINAL
    assert tuple(item.sequence for item in snapshots) == (1, 2, 3, 4)
    with pytest.raises(ReplayTerminalError):
        replay.advance()


def test_invalid_cursor_values_are_rejected() -> None:
    replay = make_replay()
    with pytest.raises(ValueError):
        replay.snapshot_at(0)
    with pytest.raises(ValueError):
        replay.snapshot_at(True)
