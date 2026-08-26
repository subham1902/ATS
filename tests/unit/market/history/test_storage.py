"""Tamper-evident persistence: roundtrip, corruption and identity checks."""

from __future__ import annotations

import json
from datetime import date, time
from decimal import Decimal

import pytest
from ats.market.calendar.models import SessionCalendar
from ats.market.history import (
    HistoricalTruthError,
    HistoryValidationPolicy,
    InstrumentPolicyOverride,
    load_historical_dataset,
    save_historical_dataset,
)
from ats.market.history.models import validation_policy_hash

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


def test_policy_hash_is_bound_to_dataset_identity() -> None:
    observations = scenario_normal_series(count=4)
    first = build_test_dataset(observations, policy=HistoryValidationPolicy())
    second = build_test_dataset(
        observations,
        policy=HistoryValidationPolicy(bar_maximum_source_lag_ms=900_001),
    )
    assert first.manifest.validation_policy_hash != second.manifest.validation_policy_hash
    assert first.manifest.dataset_id != second.manifest.dataset_id
    assert first.manifest.payload_hash != second.manifest.payload_hash


def test_tampered_policy_sidecar_is_rejected_before_revalidation(tmp_path) -> None:
    policy = HistoryValidationPolicy()
    dataset = build_test_dataset(scenario_normal_series(count=4), policy=policy)
    save_historical_dataset(dataset, tmp_path, policy=policy)
    weaker = policy.model_copy(update={"bar_minimum_availability_delay_ms": 0})
    (tmp_path / "policy.json").write_text(weaker.model_dump_json(), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="DATASET_POLICY_MISMATCH"):
        load_historical_dataset(tmp_path)


def test_missing_policy_sidecar_is_rejected_for_policy_bound_dataset(tmp_path) -> None:
    policy = HistoryValidationPolicy()
    dataset = build_test_dataset(scenario_normal_series(count=4), policy=policy)
    save_historical_dataset(dataset, tmp_path, policy=policy)
    (tmp_path / "policy.json").unlink()
    with pytest.raises(HistoricalTruthError, match="DATASET_POLICY_MISMATCH"):
        load_historical_dataset(tmp_path)


def test_unknown_policy_field_is_rejected(tmp_path) -> None:
    policy = HistoryValidationPolicy()
    dataset = build_test_dataset(scenario_normal_series(count=4), policy=policy)
    save_historical_dataset(dataset, tmp_path, policy=policy)
    document = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    document["unexpected"] = True
    (tmp_path / "policy.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="DATASET_POLICY_MISMATCH"):
        load_historical_dataset(tmp_path)


def test_identical_policy_canonical_hash_is_repeatable() -> None:
    first = HistoryValidationPolicy(contract_universe=("A", "B"))
    second = HistoryValidationPolicy.model_validate_json(first.model_dump_json())
    assert validation_policy_hash(first) == validation_policy_hash(second)


def test_quality_reinterpretation_cannot_be_applied_by_sidecar_tampering(tmp_path) -> None:
    policy = HistoryValidationPolicy(bar_minimum_availability_delay_ms=1_000)
    observation = make_bar_observation(sequence=1, availability_lag_ms=2_000)
    dataset = build_test_dataset((observation,), policy=policy)
    assert dataset.manifest.quality_summary.good_count == 1
    save_historical_dataset(dataset, tmp_path, policy=policy)
    stricter = policy.model_copy(update={"bar_minimum_availability_delay_ms": 3_000})
    (tmp_path / "policy.json").write_text(stricter.model_dump_json(), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="DATASET_POLICY_MISMATCH"):
        load_historical_dataset(tmp_path)


@pytest.mark.parametrize(
    "replacement",
    (
        HistoryValidationPolicy(bar_maximum_source_lag_ms=900_001),
        HistoryValidationPolicy(
            instrument_overrides=(
                InstrumentPolicyOverride(
                    instrument="RELIANCE",
                    timeframe="5m",
                    bar_minimum_availability_delay_ms=0,
                ),
            )
        ),
        HistoryValidationPolicy(
            session_calendar=SessionCalendar(
                calendar_id="NSE_CASH_TEST",
                calendar_version="1.0.0",
                timezone="Asia/Kolkata",
                trading_dates=(date(2024, 6, 3),),
                preopen_start=time(9, 0),
                market_open=time(9, 15),
                market_close=time(15, 30),
                overrides=(),
            )
        ),
    ),
)
def test_policy_semantic_mutations_are_rejected(tmp_path, replacement) -> None:
    policy = HistoryValidationPolicy()
    dataset = build_test_dataset(scenario_normal_series(count=4), policy=policy)
    save_historical_dataset(dataset, tmp_path, policy=policy)
    (tmp_path / "policy.json").write_text(replacement.model_dump_json(), encoding="utf-8")
    with pytest.raises(HistoricalTruthError, match="DATASET_POLICY_MISMATCH"):
        load_historical_dataset(tmp_path)
