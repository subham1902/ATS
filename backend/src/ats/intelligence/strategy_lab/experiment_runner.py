"""ExperimentRunner — builds exact frozen StrategyExperiment."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import StrategyExperiment
from ats.contracts.intelligence.types import ExperimentStatus, ExperimentType, LeakageScanStatus

from .backtest import BacktestConfiguration, run_backtest
from .leakage_scanner import scan_leakage
from .types import BacktestResult


def _payload_hash(experiment_id: UUID) -> str:
    # Deterministic placeholder hash using id
    return sha256(str(experiment_id).encode()).hexdigest()


def build_experiment(
    *,
    experiment_id: UUID,
    strategy_definition_id: UUID,
    strategy_definition_version: int,
    experiment_type: ExperimentType,
    instrument_universe: tuple[str, ...],
    timeframe: str,
    dataset_manifest_id: UUID,
    dataset_version: str,
    dataset_cutoff: UTCDateTime,
    train_start: UTCDateTime | None,
    train_end: UTCDateTime | None,
    test_start: UTCDateTime,
    test_end: UTCDateTime | None,
    purge_bars: int,
    embargo_bars: int,
    cost_model_version: str,
    parameter_set_hash: str,
    seed: int,
    started_at: UTCDateTime | None = None,
    completed_at: UTCDateTime | None = None,
    scorecard_id: UUID | None = None,
    leakage_scan_status: LeakageScanStatus | None = None,
    status: ExperimentStatus = ExperimentStatus.PLANNED,
) -> StrategyExperiment:
    # Compute leakage if not supplied
    if leakage_scan_status is None:
        # Use dummy scan based on ordering; will be PASS if valid
        # Build minimal experiment for scan
        tmp = StrategyExperiment(
            schema_version="1.0",
            experiment_id=experiment_id,
            strategy_definition_id=strategy_definition_id,
            strategy_definition_version=strategy_definition_version,
            experiment_type=experiment_type,
            status=status,
            instrument_universe=instrument_universe,
            timeframe=timeframe,
            dataset_manifest_id=dataset_manifest_id,
            dataset_version=dataset_version,
            dataset_cutoff=dataset_cutoff,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            purge_bars=purge_bars,
            embargo_bars=embargo_bars,
            cost_model_version=cost_model_version,
            parameter_set_hash=parameter_set_hash,
            seed=seed,
            benchmark_strategy_refs=(),
            leakage_scan_status=LeakageScanStatus.PASS,
            shadow_campaign_id=None,
            started_at=started_at,
            completed_at=completed_at,
            scorecard_id=scorecard_id,
            reason_codes=(),
            payload_hash="0" * 64,
        )
        scan = scan_leakage(tmp)
        leakage_scan_status = scan.status

    return StrategyExperiment(
        schema_version="1.0",
        experiment_id=experiment_id,
        strategy_definition_id=strategy_definition_id,
        strategy_definition_version=strategy_definition_version,
        experiment_type=experiment_type,
        status=status,
        instrument_universe=instrument_universe,
        timeframe=timeframe,
        dataset_manifest_id=dataset_manifest_id,
        dataset_version=dataset_version,
        dataset_cutoff=dataset_cutoff,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
        purge_bars=purge_bars,
        embargo_bars=embargo_bars,
        cost_model_version=cost_model_version,
        parameter_set_hash=parameter_set_hash,
        seed=seed,
        benchmark_strategy_refs=(),
        leakage_scan_status=leakage_scan_status,
        shadow_campaign_id=None,
        started_at=started_at,
        completed_at=completed_at,
        scorecard_id=scorecard_id,
        reason_codes=(),
        payload_hash=_payload_hash(experiment_id),
    )


def run_experiment(
    *,
    config: BacktestConfiguration,
    experiment: StrategyExperiment,
    now: UTCDateTime,
) -> tuple[StrategyExperiment, BacktestResult]:
    """Deterministic runner: scans leakage, runs backtest, returns COMPLETED experiment."""
    scan = scan_leakage(experiment)
    if scan.status is not LeakageScanStatus.PASS:
        # Return FAILED experiment
        failed = experiment.model_copy(
            update={
                "status": ExperimentStatus.FAILED,
                "started_at": now,
                "completed_at": now,
                "leakage_scan_status": LeakageScanStatus.FAIL,
                "reason_codes": scan.reason_codes[:1] if scan.reason_codes else ("LEAKAGE",),
            }
        )
        # Empty result for failure
        from .types import BacktestResult

        empty_result = BacktestResult(
            result_id=uuid5(experiment.experiment_id, "failed"),
            experiment_id=experiment.experiment_id,
            trades=(),
            fills=(),
            signals=(),
            start_time=experiment.test_start,
            end_time=experiment.test_end or experiment.test_start,
            seed=experiment.seed,
        )
        return failed, empty_result

    # Run deterministic backtest
    result = run_backtest(
        config=config,
        test_start=experiment.test_start,
        test_end=experiment.test_end,
        experiment_id=experiment.experiment_id,
    )
    # For now scorecard_id is result.result_id deterministically
    completed = experiment.model_copy(
        update={
            "status": ExperimentStatus.COMPLETED,
            "started_at": experiment.started_at or now,
            "completed_at": now,
            "leakage_scan_status": LeakageScanStatus.PASS,
            "scorecard_id": result.result_id,
            "test_end": experiment.test_end or result.end_time,
        }
    )
    return completed, result


__all__ = ["build_experiment", "run_experiment"]
