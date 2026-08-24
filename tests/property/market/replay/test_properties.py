from __future__ import annotations

import pytest
from ats.market import FutureDataAccessError, ReplayTerminalError

from tests.unit.market.fixtures import make_replay


@pytest.mark.parametrize("repetition", range(8))
def test_repeated_replay_is_byte_and_hash_deterministic(repetition: int) -> None:
    del repetition
    left = make_replay()
    right = make_replay()
    left_snapshots = tuple(left.advance() for _ in range(left.state.total_bars))
    right_snapshots = tuple(right.advance() for _ in range(right.state.total_bars))
    assert tuple(item.model_dump_json() for item in left_snapshots) == tuple(
        item.model_dump_json() for item in right_snapshots
    )
    assert tuple(item.payload_hash for item in left_snapshots) == tuple(
        item.payload_hash for item in right_snapshots
    )


def test_every_cursor_boundary_hides_exactly_the_future_suffix() -> None:
    replay = make_replay()
    total = replay.state.total_bars
    for visible in range(total + 1):
        assert len(replay.visible_snapshots()) == visible
        for sequence in range(1, visible + 1):
            assert replay.snapshot_at(sequence).sequence == sequence
        for sequence in range(visible + 1, total + 1):
            with pytest.raises(FutureDataAccessError):
                replay.snapshot_at(sequence)
        if visible < total:
            replay.advance()


def test_sequences_and_replay_times_are_strictly_monotonic() -> None:
    replay = make_replay()
    snapshots = tuple(replay.advance() for _ in range(replay.state.total_bars))
    assert tuple(item.sequence for item in snapshots) == tuple(range(1, len(snapshots) + 1))
    assert tuple(item.bar_timestamp for item in snapshots) == tuple(
        sorted(item.bar_timestamp for item in snapshots)
    )
    assert tuple(item.received_at for item in snapshots) == tuple(
        sorted(item.received_at for item in snapshots)
    )


def test_terminal_state_never_wraps_or_restarts() -> None:
    replay = make_replay()
    for _ in range(replay.state.total_bars):
        replay.advance()
    for _ in range(4):
        with pytest.raises(ReplayTerminalError):
            replay.advance()
