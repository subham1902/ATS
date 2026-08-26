"""Tamper-evident persistence: roundtrip, corruption and identity checks."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from ats.market.history import (
    HistoricalTruthError,
    load_historical_dataset,
    save_historical_dataset,
)

from tests.unit.market.history.fixtures import (
    build_test_dataset,
    make_bar_observation,
    scenario_normal_series,
)


def _dataset():
    base = scenario_normal_series(count=4)
    revision = make_bar_observation(
        sequence=1,
        close_price=Decimal("2919.00"),
        availability_lag_ms=400_000,
        supersedes=base[0].observation_id,
    )
    return build_test_dataset((*base, revision))


def test_roundtrip_preserves_identity_and_content(tmp_path) -> None:
    dataset = _dataset()
    receipt = save_historical_dataset(dataset, tmp_path)
    reloaded = load_historical_dataset(tmp_path)
    assert reloaded.manifest.dataset_id == dataset.manifest.dataset_id
    assert reloaded.manifest.payload_hash == dataset.manifest.payload_hash
    assert reloaded.manifest.quality_summary == dataset.manifest.quality_summary
    assert tuple(item.observation_id for item in reloaded.observations) == tuple(
        item.observation_id for item in dataset.observations
    )
    assert receipt.records_sha256


def test_tampered_records_file_is_rejected(tmp_path) -> None:
    save_historical_dataset(_dataset(), tmp_path)
    records = tmp_path / "observations.jsonl"
    payload = records.read_text(encoding="utf-8")
    records.write_text(payload.replace("2918.50", "9999.99"), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="records.sha256"):
        load_historical_dataset(tmp_path)


def test_missing_digest_file_is_rejected(tmp_path) -> None:
    save_historical_dataset(_dataset(), tmp_path)
    (tmp_path / "records.sha256").unlink()
    with pytest.raises(HistoricalTruthError):
        load_historical_dataset(tmp_path)


def test_manifest_drift_breaks_dataset_identity(tmp_path) -> None:
    save_historical_dataset(_dataset(), tmp_path)
    manifest_path = tmp_path / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["contract_master_version"] = "TAMPERED_MASTER_V9"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="DATASET_IDENTITY_MISMATCH"):
        load_historical_dataset(tmp_path)


def test_atomic_overwrite_keeps_dataset_loadable(tmp_path) -> None:
    first = build_test_dataset(scenario_normal_series())
    second = _dataset()
    save_historical_dataset(first, tmp_path)
    save_historical_dataset(second, tmp_path)
    reloaded = load_historical_dataset(tmp_path)
    assert len(reloaded.observations) == len(second.observations)
