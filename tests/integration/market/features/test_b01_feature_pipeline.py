from __future__ import annotations

import hashlib
from pathlib import Path

from ats.contracts.domain import FeatureBundle
from ats.market.calendar import nse_cash_alpha_v1_calendar
from ats.market.features import compute_feature_bundle
from ats.market.fixtures import ApprovedFixture, approved_manifest, create_approved_replay
from ats.market.replay import ReplayConfiguration

ROOT = Path(__file__).parents[4]
FIXTURE = (
    ROOT
    / "backend"
    / "src"
    / "ats"
    / "market"
    / "fixtures"
    / "nse_cash_reliance_5m_v1.bars.json"
)
GOLDEN = Path(__file__).with_name("golden_feature_bundle.json")
EXPECTED_FIXTURE_SHA = "182078ad14a46c8c2a92e7cf6838a62c838789820568f25b8c45c6063f62aaba"
EXPECTED_SNAPSHOT_HASHES = (
    "6fe94479bea55e8f7cd55e1ca73b4801fd315c54a7dcfeb535647814fa681428",
    "843126e0c6488c7f9603c77aa4cd88f3030410fd1805f9ecee5bf141a6796469",
    "e3460906b060daf4df4cd655274bd0c4f67c4686bbc648c175944561f81e6e99",
    "0ea5f8c837fcf4cc0f87d20929df6db94e45fd1fcadb18a6b54c023ef0da412d",
)


def _run_pipeline() -> tuple[tuple[object, ...], FeatureBundle]:
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    replay = create_approved_replay(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        nse_cash_alpha_v1_calendar(),
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
    assert bundle.model_dump_json() == FeatureBundle.model_validate_json(
        GOLDEN.read_bytes()
    ).model_dump_json()


def test_complete_pipeline_is_deterministic() -> None:
    first_snapshots, first_bundle = _run_pipeline()
    second_snapshots, second_bundle = _run_pipeline()
    assert tuple(item.model_dump_json() for item in first_snapshots) == tuple(
        item.model_dump_json() for item in second_snapshots
    )
    assert first_bundle.model_dump_json() == second_bundle.model_dump_json()
