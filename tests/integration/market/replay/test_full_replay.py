from __future__ import annotations

import json
from pathlib import Path

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market import (
    ApprovedFixture,
    ReplayConfiguration,
    ReplayPhase,
    ReplayTerminalError,
    approved_manifest,
    create_approved_replay,
    nse_cash_alpha_v1_calendar,
)


def test_approved_fixture_replays_end_to_end_against_committed_golden() -> None:
    calendar = nse_cash_alpha_v1_calendar()
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    replay = create_approved_replay(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        calendar,
        ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=250),
    )
    golden = json.loads(
        Path("tests/contract/market/golden_replay.json").read_text(encoding="utf-8")
    )
    snapshots = tuple(replay.advance() for _ in range(manifest.bar_count))
    assert replay.state.phase is ReplayPhase.TERMINAL
    assert [item.payload_hash for item in snapshots] == [
        item["payload_hash"] for item in golden["snapshots"]
    ]
    assert all(item.payload_hash == compute_payload_hash(item) for item in snapshots)
    assert replay.visible_snapshots() == snapshots
    with pytest.raises(ReplayTerminalError):
        replay.advance()
