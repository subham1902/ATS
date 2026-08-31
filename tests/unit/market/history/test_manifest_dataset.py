"""Unit tests for the immutable dataset manifest and dataset container."""

from __future__ import annotations

import pytest
from ats.market.history import DatasetSourceClass, FileHashEntry, TransformStep
from pydantic import ValidationError

from tests.unit.market.history.fixtures import (
    build_test_dataset,
    scenario_late_arrival,
    scenario_normal_series,
    scenario_stale_bar,
)


def test_manifest_is_frozen_and_complete() -> None:
    dataset = build_test_dataset(scenario_normal_series(3))
    manifest = dataset.manifest
    assert manifest.schema_version == "1.1"
    assert len(manifest.validation_policy_hash) == 64
    assert manifest.row_count == 3
    assert manifest.source == "ATS_TEST_ONLY_SYNTHETIC"
    assert manifest.data_classification is DatasetSourceClass.TEST_ONLY_SYNTHETIC
    assert manifest.instrument_universe == ("RELIANCE",)
    with pytest.raises(ValidationError, match="frozen"):
        manifest.row_count = 99  # type: ignore[misc]


def test_manifest_quality_summary_classifies_stale_rows_as_degraded() -> None:
    dataset = build_test_dataset((*scenario_normal_series(3), scenario_stale_bar()))
    summary = dataset.manifest.quality_summary
    assert summary.good_count == 3
    assert summary.degraded_count == 1
    assert summary.total_count == 4
    assert dataset.manifest.row_count == summary.total_count


def test_late_arrival_within_threshold_stays_good() -> None:
    dataset = build_test_dataset(scenario_late_arrival())
    assert dataset.manifest.quality_summary.good_count == 4
    assert dataset.manifest.quality_summary.degraded_count == 0


def test_dataset_json_round_trip_preserves_equality() -> None:
    dataset = build_test_dataset(scenario_normal_series(3))
    restored = type(dataset).model_validate_json(dataset.model_dump_json())
    assert restored == dataset
    assert restored.manifest.payload_hash == dataset.manifest.payload_hash


def test_dataset_identity_changes_when_content_changes() -> None:
    small = build_test_dataset(scenario_normal_series(3))
    large = build_test_dataset(scenario_normal_series(4))
    assert small.manifest.dataset_id != large.manifest.dataset_id


def test_manifest_rejects_unsorted_file_hashes() -> None:
    hashes = (
        FileHashEntry(file_name="raw.jsonl", content_sha256="d" * 64),
        FileHashEntry(file_name="normalized.jsonl", content_sha256="c" * 64),
    )
    with pytest.raises(ValueError, match="sorted"):
        build_test_dataset(scenario_normal_series(2), file_hashes=hashes)


def test_manifest_rejects_non_contiguous_lineage() -> None:
    lineage = (
        TransformStep(step_index=0, transform_id="A_V1", transform_version="1.0.0"),
        TransformStep(step_index=2, transform_id="B_V1", transform_version="1.0.0"),
    )
    with pytest.raises(ValueError, match="contiguous"):
        build_test_dataset(scenario_normal_series(2), transform_lineage=lineage)
