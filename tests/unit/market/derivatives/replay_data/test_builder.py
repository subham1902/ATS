from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.market.derivatives.artifacts import ArtifactSourceClass
from ats.market.derivatives.replay_data import (
    FiveMinuteDerivativeBar,
    FixtureBuildSpec,
    RawArtifactBinding,
    assert_phase_p_eligible,
    build_fixture,
)


def spec(source_class: ArtifactSourceClass) -> FixtureBuildSpec:
    real = source_class is ArtifactSourceClass.REAL_SOURCE
    return FixtureBuildSpec(
        fixture_name="TEST_ONLY_NIFTY_OPTIONS_STRUCTURAL_V1",
        market="NSE",
        underlying="NIFTY",
        source="APPROVED_SOURCE" if real else "STRUCTURAL_TEST_FIXTURE",
        source_api_or_file="APPROVED_RAW_ARTIFACT" if real else "RECORDED_PROVIDER_SHAPE",
        provider="UPSTOX" if real else "FAKE_UPSTOX",
        retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_version="test-shape-v1",
        contract_master_hash="a" * 64,
        timezone="Asia/Kolkata",
        normalizer_version="1.0.0-test",
        data_cutoff=datetime(2026, 8, 24, 4, 0, tzinfo=UTC),
        license_classification="APPROVED_FOR_REPLAY" if real else "TEST_ONLY_NON_MARKET_DATA",
        session_date="2026-08-24",
        expiry="2026-08-25",
        selected_contract_ids=("TEST_ONLY_NIFTY_CE",),
        raw_artifacts=(
            RawArtifactBinding(
                artifact_id="TEST_ONLY_RAW_1",
                raw_sha256="b" * 64,
                source_class=source_class,
            ),
        ),
    )


def bar() -> FiveMinuteDerivativeBar:
    return FiveMinuteDerivativeBar(
        instrument_id="TEST_ONLY_NIFTY_CE",
        bar_close=datetime(2026, 8, 24, 3, 50, tzinfo=UTC),
        timeframe="5m",
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
        open_interest=Decimal("1000"),
        source_minute_count=5,
        quality="COMPLETE",
    )


def test_deterministic_hash_chain_and_manifest_binding() -> None:
    first = build_fixture(spec=spec(ArtifactSourceClass.RECORDED_PROVIDER_SHAPE), bars=(bar(),))
    second = build_fixture(spec=spec(ArtifactSourceClass.RECORDED_PROVIDER_SHAPE), bars=(bar(),))
    assert first == second
    assert first.manifest.raw_hash
    assert first.manifest.normalized_hash
    assert first.manifest.contract_master_hash == "a" * 64
    assert first.manifest_hash


def test_raw_hash_and_normalizer_version_are_bound_into_normalized_hash() -> None:
    original = spec(ArtifactSourceClass.RECORDED_PROVIDER_SHAPE)
    first = build_fixture(spec=original, bars=(bar(),))
    new_raw = original.model_copy(
        update={
            "raw_artifacts": (
                RawArtifactBinding(
                    artifact_id="TEST_ONLY_RAW_1",
                    raw_sha256="c" * 64,
                    source_class=ArtifactSourceClass.RECORDED_PROVIDER_SHAPE,
                ),
            )
        }
    )
    new_version = original.model_copy(update={"normalizer_version": "1.0.1-test"})
    assert (
        build_fixture(spec=new_raw, bars=(bar(),)).manifest.normalized_hash
        != first.manifest.normalized_hash
    )
    assert (
        build_fixture(spec=new_version, bars=(bar(),)).manifest.normalized_hash
        != first.manifest.normalized_hash
    )


def test_test_only_or_recorded_shape_cannot_enter_phase_p() -> None:
    for source_class in (
        ArtifactSourceClass.TEST_ONLY_SYNTHETIC,
        ArtifactSourceClass.RECORDED_PROVIDER_SHAPE,
    ):
        result = build_fixture(spec=spec(source_class), bars=(bar(),))
        with pytest.raises(ValueError, match="REAL_SOURCE"):
            assert_phase_p_eligible(result)


def test_real_source_class_is_only_phase_p_eligible_class() -> None:
    result = build_fixture(spec=spec(ArtifactSourceClass.REAL_SOURCE), bars=(bar(),))
    assert_phase_p_eligible(result)


def test_orphan_normalized_bar_is_rejected() -> None:
    orphan = bar().model_copy(update={"instrument_id": "TEST_ONLY_ORPHAN"})
    with pytest.raises(ValueError, match="does not bind"):
        build_fixture(spec=spec(ArtifactSourceClass.TEST_ONLY_SYNTHETIC), bars=(orphan,))
