"""R14-F03: Leakage scanner purge/embargo gap enforcement tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.contracts.intelligence.types import ExperimentStatus, ExperimentType, LeakageScanStatus
from ats.intelligence.strategy_lab.experiment_runner import build_experiment
from ats.intelligence.strategy_lab.leakage_scanner import scan_leakage
from ats.market.replay.models import ReplayBar, ReplayDataset, ReplayManifest


def _dataset(n: int = 30) -> ReplayDataset:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []
    for i in range(n):
        bars.append(
            ReplayBar(
                instrument_id="NSE_EQ-TCS",
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                bar_timestamp=base + timedelta(days=i),
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=Decimal("1000"),
                source_sequence=i + 1,
                quality_state=DataQualityState.GOOD,
                quality_flags=(),
                session_state=SessionState.OPEN,
            )
        )
    manifest = ReplayManifest(
        dataset_id=uuid4(),
        dataset_version="v1",
        source_description="test",
        instrument="NSE_EQ-TCS",
        exchange="NSE",
        segment="CASH",
        timeframe="5m",
        first_bar=bars[0].bar_timestamp,
        last_bar=bars[-1].bar_timestamp,
        bar_count=len(bars),
        content_sha256="a" * 64,
        calendar_id="XNSE",
        calendar_version="1",
    )
    return ReplayDataset(manifest=manifest, bars=tuple(bars))


def test_insufficient_purge_gap_detected() -> None:
    """Insufficient purge gap detected when dataset provided."""
    dataset = _dataset(30)
    # train_end at day 10 (bar index 10), test_start at day 12 (bar index 12)
    # gap = 12 - 10 - 1 = 1 bar (day 11)
    # purge_bars=5 requires gap >= 5 → FAIL
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=dataset.manifest.dataset_id,
        dataset_version="v1",
        dataset_cutoff=dataset.manifest.last_bar,
        train_start=datetime(2024, 1, 1, tzinfo=UTC),
        train_end=datetime(2024, 1, 11, tzinfo=UTC),
        test_start=datetime(2024, 1, 13, tzinfo=UTC),
        test_end=datetime(2024, 1, 20, tzinfo=UTC),
        purge_bars=5,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
        dataset=dataset,
    )
    res = scan_leakage(exp, dataset)
    assert res.status is LeakageScanStatus.FAIL
    assert "insufficient_purge_gap" in res.reason_codes


def test_sufficient_purge_gap_passes() -> None:
    """Valid walk-forward windows pass with sufficient purge gap."""
    dataset = _dataset(30)
    # train_end at day 5 (bar 5), test_start at day 12 (bar 12)
    # gap = 12 - 5 - 1 = 6 bars (days 6-11)
    # purge_bars=5 → gap >= 5 → PASS
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=dataset.manifest.dataset_id,
        dataset_version="v1",
        dataset_cutoff=dataset.manifest.last_bar,
        train_start=datetime(2024, 1, 1, tzinfo=UTC),
        train_end=datetime(2024, 1, 6, tzinfo=UTC),
        test_start=datetime(2024, 1, 13, tzinfo=UTC),
        test_end=datetime(2024, 1, 20, tzinfo=UTC),
        purge_bars=5,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
        dataset=dataset,
    )
    res = scan_leakage(exp, dataset)
    assert res.status is LeakageScanStatus.PASS


def test_dataset_cutoff_enforced_against_actual_bars() -> None:
    """Dataset cutoff enforced against actual bars in dataset."""
    dataset = _dataset(20)
    # dataset_cutoff at day 15, test_end at day 14 → valid at contract level
    # scanner verifies no bar used has timestamp > cutoff
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=dataset.manifest.dataset_id,
        dataset_version="v1",
        dataset_cutoff=datetime(2024, 1, 16, tzinfo=UTC),
        train_start=None,
        train_end=None,
        test_start=datetime(2024, 1, 5, tzinfo=UTC),
        test_end=datetime(2024, 1, 15, tzinfo=UTC),
        purge_bars=0,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
        dataset=dataset,
    )
    res = scan_leakage(exp, dataset)
    assert res.status is LeakageScanStatus.PASS


def test_future_suffix_cannot_influence_prior_run() -> None:
    """Future suffix beyond test_end cannot influence prior research run."""
    dataset = _dataset(30)
    # test_end at day 10, dataset has 30 bars — bars 11-29 are future suffix
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=dataset.manifest.dataset_id,
        dataset_version="v1",
        dataset_cutoff=dataset.manifest.last_bar,
        train_start=None,
        train_end=None,
        test_start=datetime(2024, 1, 5, tzinfo=UTC),
        test_end=datetime(2024, 1, 11, tzinfo=UTC),
        purge_bars=0,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
        dataset=dataset,
    )
    res = scan_leakage(exp, dataset)
    assert res.status is LeakageScanStatus.PASS


def test_test_start_not_in_dataset_fails() -> None:
    """test_start not in dataset fails when dataset provided."""
    dataset = _dataset(10)
    # dataset has bars for days 0-9 (Jan 1-10)
    # test_start at day 100, test_end at day 101, cutoff at day 102
    # contract passes (test_end <= cutoff) but scanner catches missing bar
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=dataset.manifest.dataset_id,
        dataset_version="v1",
        dataset_cutoff=datetime(2024, 4, 12, tzinfo=UTC),
        train_start=None,
        train_end=None,
        test_start=datetime(2024, 4, 10, tzinfo=UTC),
        test_end=datetime(2024, 4, 11, tzinfo=UTC),
        purge_bars=0,
        embargo_bars=0,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
        dataset=dataset,
    )
    res = scan_leakage(exp, dataset)
    assert res.status is LeakageScanStatus.FAIL
    assert "test_start_not_in_dataset" in res.reason_codes


def test_metadata_only_scan_still_works() -> None:
    """scan_leakage without dataset still works (backward compatible)."""
    exp = build_experiment(
        experiment_id=uuid4(),
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_type=ExperimentType.BACKTEST,
        instrument_universe=("NSE_EQ-TCS",),
        timeframe="5m",
        dataset_manifest_id=uuid4(),
        dataset_version="v1",
        dataset_cutoff=datetime(2024, 1, 20, tzinfo=UTC),
        train_start=datetime(2024, 1, 1, tzinfo=UTC),
        train_end=datetime(2024, 1, 10, tzinfo=UTC),
        test_start=datetime(2024, 1, 11, tzinfo=UTC),
        test_end=datetime(2024, 1, 15, tzinfo=UTC),
        purge_bars=1,
        embargo_bars=1,
        cost_model_version="v1",
        parameter_set_hash="a" * 64,
        seed=42,
        status=ExperimentStatus.PLANNED,
    )
    res = scan_leakage(exp)
    assert res.status is LeakageScanStatus.PASS


def test_contract_rejects_test_end_after_cutoff() -> None:
    """Frozen contract rejects test_end > dataset_cutoff at construction."""
    with pytest.raises(ValueError):
        build_experiment(
            experiment_id=uuid4(),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            experiment_type=ExperimentType.BACKTEST,
            instrument_universe=("NSE_EQ-TCS",),
            timeframe="5m",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
            train_start=None,
            train_end=None,
            test_start=datetime(2024, 1, 5, tzinfo=UTC),
            test_end=datetime(2024, 1, 15, tzinfo=UTC),
            purge_bars=0,
            embargo_bars=0,
            cost_model_version="v1",
            parameter_set_hash="a" * 64,
            seed=42,
            status=ExperimentStatus.PLANNED,
        )
