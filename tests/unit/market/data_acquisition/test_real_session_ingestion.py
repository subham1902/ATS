"""Validation of the real Upstox session ingestion into Historical Truth.

These tests prove the core guarantees of feeding real market data through the
frozen, tamper-evident layer:

* No look-ahead: every observation's availability time is strictly after its
  event time (the four-clock ordering invariant), so a strategy can never see a
  bar before the underlying event occurred.
* Provenance: every record retains an immutable reference to the exact raw
  Upstox candle (source id + record sha + location).
* Tamper-evidence: any modification of a persisted record or manifest fails
  closed on reload.
* Determinism: rebuilding the same raw session reproduces the identical dataset
  identity and payload hash.
"""

from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from ats.market.history import (
    HistoryValidationPolicy,
    MarketBarPayload,
    RawRecordReference,
    load_historical_dataset,
)
from ats.market.data_acquisition.ingest_session import (
    ONE_MINUTE_POLICY,
    build_session_datasets,
)

HISTORY_DIR = Path(r"D:\Projects\ATS\ats\data\historical")
DATASETS = {
    "NIFTY": HISTORY_DIR / "nifty_options_a2_replay_v1",
    "BANKNIFTY": HISTORY_DIR / "banknifty_options_a2_replay_v1",
}
UNDERLYING_IDS = {
    "NSE_INDEX_NIFTY_50",
    "NSE_INDEX_NIFTY_BANK",
}
EXPECTED_BAR_COUNTS = {"underlying": 375, "option": 385}
SOURCE = "UPSTOX_ANALYTICS_V3"


def _load_all():
    return {name: load_historical_dataset(path) for name, path in DATASETS.items()}


@pytest.fixture()
def datasets():
    return _load_all()


def test_datasets_persisted_and_valid(datasets):
    for ds in datasets.values():
        assert ds.manifest.row_count == 4235
        assert ds.manifest.quality_summary.degraded_count == 0
        assert ds.manifest.data_classification.value == "REAL_SOURCE"
        assert ds.manifest.transform_lineage[0].transform_id == "UPSTOX_V3_NORMALIZER_V1"


def test_four_clock_no_lookahead(datasets):
    for ds in datasets.values():
        for obs in ds.observations:
            t = obs.times
            # event -> source -> ingest -> available must be non-decreasing
            assert t.event_time <= t.source_time <= t.ingest_time <= t.available_to_strategy_time
            # the strategy may never see a record before its event occurred
            assert t.available_to_strategy_time > t.event_time
            if isinstance(obs.payload, MarketBarPayload):
                # bar availability lags the event by the configured 62s floor
                assert t.available_to_strategy_time - t.event_time >= timedelta(milliseconds=62_000)
            else:
                assert t.available_to_strategy_time - t.event_time >= timedelta(milliseconds=2_000)


def test_provenance_present(datasets):
    for ds in datasets.values():
        for obs in ds.observations:
            prov = obs.provenance
            assert isinstance(prov, RawRecordReference)
            assert prov.source_id == SOURCE
            assert len(prov.raw_record_sha256) == 64
            assert prov.raw_location


def test_bar_coverage_and_interval(datasets):
    for ds in datasets.values():
        by_instrument: dict[str, list] = {}
        for obs in ds.observations:
            if isinstance(obs.payload, MarketBarPayload):
                by_instrument.setdefault(obs.instrument, []).append(obs)
        for inst, bars in by_instrument.items():
            expected = EXPECTED_BAR_COUNTS["underlying"] if inst in UNDERLYING_IDS else EXPECTED_BAR_COUNTS["option"]
            assert len(bars) == expected, inst
            times = [b.times.event_time for b in bars]
            assert times == sorted(times)
            assert len(set(times)) == len(times)
            deltas = {int((times[i + 1] - times[i]).total_seconds()) for i in range(len(times) - 1)}
            assert deltas == {60}


def test_self_describing_policy_sidecar():
    for path in DATASETS.values():
        sidecar = path / "policy.json"
        assert sidecar.exists()
        policy = HistoryValidationPolicy.model_validate_json(sidecar.read_bytes())
        assert policy.expected_bar_interval_ms == ONE_MINUTE_POLICY.expected_bar_interval_ms


def test_deterministic_rebuild():
    first = build_session_datasets()
    second = build_session_datasets()
    for name in first:
        assert first[name]["dataset_id"] == second[name]["dataset_id"]
        assert first[name]["payload_hash"] == second[name]["payload_hash"]
        assert first[name]["records_sha256"] == second[name]["records_sha256"]


def test_tamper_records_file_fails_closed(tmp_path):
    src = DATASETS["NIFTY"]
    work = tmp_path / "nifty_tamper"
    shutil.copytree(src, work)
    records = work / "observations.jsonl"
    lines = records.read_bytes().decode("utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["close"] = str(float(first["payload"]["close"]) + 1.0)
    lines[0] = json.dumps(first)
    records.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_historical_dataset(work)


def test_tamper_manifest_fails_closed(tmp_path):
    src = DATASETS["NIFTY"]
    work = tmp_path / "nifty_manifest_tamper"
    shutil.copytree(src, work)
    manifest = work / "manifest.json"
    data = json.loads(manifest.read_bytes())
    data["dataset_id"] = "00000000-0000-0000-0000-000000000000"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(Exception):
        load_historical_dataset(work)
