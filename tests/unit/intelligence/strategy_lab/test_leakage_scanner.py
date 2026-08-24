from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ats.contracts.intelligence.types import ExperimentStatus, ExperimentType, LeakageScanStatus
from ats.intelligence.strategy_lab.experiment_runner import build_experiment
from ats.intelligence.strategy_lab.leakage_scanner import scan_leakage


def test_leakage_pass_valid() -> None:
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


def test_leakage_fail_cutoff_violation() -> None:
    import pytest

    # Contract itself rejects test_end > dataset_cutoff -> leakage prevented at construction
    with pytest.raises(Exception):
        build_experiment(
            experiment_id=uuid4(),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            experiment_type=ExperimentType.BACKTEST,
            instrument_universe=("NSE_EQ-TCS",),
            timeframe="5m",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 12, tzinfo=UTC),
            train_start=None,
            train_end=None,
            test_start=datetime(2024, 1, 10, tzinfo=UTC),
            test_end=datetime(2024, 1, 15, tzinfo=UTC),
            purge_bars=0,
            embargo_bars=0,
            cost_model_version="v1",
            parameter_set_hash="a" * 64,
            seed=42,
            status=ExperimentStatus.PLANNED,
        )
