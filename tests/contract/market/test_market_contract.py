from __future__ import annotations

import json
from pathlib import Path

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import MarketSnapshot
from ats.market import ReplayManifest
from ats.market.replay.models import ReplayDataset

from tests.unit.market.fixtures import make_replay

GOLDEN = json.loads(Path("tests/contract/market/golden_replay.json").read_text(encoding="utf-8"))


def test_replay_and_manifest_models_export_json_schema() -> None:
    for model in (ReplayManifest, ReplayDataset):
        assert model.model_json_schema()["type"] == "object"


def test_every_output_is_the_frozen_a02_market_snapshot() -> None:
    replay = make_replay()
    snapshots = tuple(replay.advance() for _ in range(replay.state.total_bars))
    assert all(type(item) is MarketSnapshot for item in snapshots)
    assert all(item.exchange == "NSE" for item in snapshots)
    assert all(item.segment == "CASH" for item in snapshots)
    assert all(item.timeframe == "5m" for item in snapshots)
    assert all(item.payload_hash == compute_payload_hash(item) for item in snapshots)


def test_committed_replay_golden_is_exact() -> None:
    replay = make_replay()
    actual = []
    for _ in range(replay.state.total_bars):
        snapshot = replay.advance()
        actual.append(
            {
                "snapshot_id": str(snapshot.snapshot_id),
                "sequence": snapshot.sequence,
                "session_state": snapshot.session_state.value,
                "payload_hash": snapshot.payload_hash,
            }
        )
    assert actual == GOLDEN["snapshots"]


def test_public_replay_surface_has_no_future_preload_accessor() -> None:
    import ats.market as market

    replay = make_replay()
    public = {name for name in dir(replay) if not name.startswith("_")}
    assert public == {"advance", "clock", "current", "snapshot_at", "state", "visible_snapshots"}
    assert "ReplayDataset" not in market.__all__
    assert "load_replay_dataset" not in market.__all__
    assert "load_approved_fixture" not in market.__all__
