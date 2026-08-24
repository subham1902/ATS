from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

from ats.market import ReplayManifest
from ats.market.replay.models import ReplayFixtureDocument


def test_committed_fixture_hash_matches_both_manifest_and_golden() -> None:
    package = files("ats.market.fixtures")
    content = package.joinpath("nse_cash_reliance_5m_v1.bars.json").read_bytes()
    manifest = ReplayManifest.model_validate_json(
        package.joinpath("nse_cash_reliance_5m_v1.manifest.json").read_bytes()
    )
    golden = json.loads(
        Path("tests/contract/market/golden_replay.json").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(content).hexdigest()
    assert digest == manifest.content_sha256 == golden["dataset_content_sha256"]


def test_fixture_document_is_small_strict_and_sequence_complete() -> None:
    content = (
        files("ats.market.fixtures").joinpath("nse_cash_reliance_5m_v1.bars.json").read_bytes()
    )
    fixture = ReplayFixtureDocument.model_validate_json(content)
    assert len(content) < 10_000
    assert tuple(item.source_sequence for item in fixture.bars) == (1, 2, 3, 4)
