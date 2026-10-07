from __future__ import annotations

import hashlib
from pathlib import Path

from ats.contracts.domain import FeatureBundle
from ats.market.calendar import xauusd_test_calendar
from ats.market.features import compute_feature_bundle
from ats.market.fixtures import ApprovedFixture, approved_manifest, create_approved_replay
from ats.market.replay import ReplayConfiguration

ROOT = Path(__file__).parents[4]
FIXTURE = (
    ROOT / "backend" / "src" / "ats" / "market" / "fixtures" / "xauusd_synthetic_5m_v1.bars.json"
)
GOLDEN = Path(__file__).with_name("golden_feature_bundle.json")
EXPECTED_FIXTURE_SHA = "2ba55dd2919304e3aec6f516f1155d8014f31215b8f7347fe71df7c5eb11ed77"
EXPECTED_SNAPSHOT_HASHES = (
    "d8a4ce6ad38bad6f349e3940ca5f6536252e714a905d6d5d208e48308203817f",
    "f8d7b4593164ae190bd4e406140bf8736a29d8511d50b5eac17f6edbbb917885",
    "7b7b8c226d325b8b66943aec1136867bbd76d4959252d2cdbdc7595e868aacd3",
    "52ef3727aed8efa3f18b500279458a047a310ad64aa06d02a0019383828f6601",
)


def _run_pipeline() -> tuple[tuple[object, ...], FeatureBundle]:
    manifest = approved_manifest(ApprovedFixture.XAUUSD_SYNTHETIC_5M_V1)
    replay = create_approved_replay(
        ApprovedFixture.XAUUSD_SYNTHETIC_5M_V1,
        xauusd_test_calendar(),
        ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=250),
    )
    bundle: FeatureBundle | None = None
    for _ in range(manifest.bar_count):
        snapshot = replay.advance()
        bundle = compute_feature_bundle(
            replay.visible_snapshots(), cutoff_sequence=snapshot.sequence
        )
    assert bundle is not None
    return replay.visible_snapshots(), bundle


def test_b01_replay_to_feature_bundle_matches_committed_golden() -> None:
    snapshots, bundle = _run_pipeline()
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == EXPECTED_FIXTURE_SHA
    assert tuple(snapshot.sequence for snapshot in snapshots) == (1, 2, 3, 4)
    assert tuple(snapshot.payload_hash for snapshot in snapshots) == EXPECTED_SNAPSHOT_HASHES
    assert (
        bundle.model_dump_json()
        == FeatureBundle.model_validate_json(GOLDEN.read_bytes()).model_dump_json()
    )


def test_complete_pipeline_is_deterministic() -> None:
    first_snapshots, first_bundle = _run_pipeline()
    second_snapshots, second_bundle = _run_pipeline()
    assert tuple(item.model_dump_json() for item in first_snapshots) == tuple(
        item.model_dump_json() for item in second_snapshots
    )
    assert first_bundle.model_dump_json() == second_bundle.model_dump_json()
