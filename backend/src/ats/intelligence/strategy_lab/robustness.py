"""Robustness: parameter/cost/timing perturbation and walk-forward variation."""

from __future__ import annotations

import math
from decimal import Decimal
from uuid import UUID, uuid4

from ats.contracts.common import UTCDateTime
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel

from .backtest import BacktestConfiguration, run_backtest
from .scorecard import build_scorecard
from .types import BacktestResult, RobustnessReport


def _sharpe_from_result(result: BacktestResult, cost_version: str) -> float | None:
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(result.result_id,),
        result=result,
        created_at=result.start_time,
        cost_model_version=cost_version,
    )
    return sc.sharpe


def parameter_perturbation_score(
    base: BacktestResult,
    perturbed: list[BacktestResult],
    cost_version: str,
) -> float:
    base_s = _sharpe_from_result(base, cost_version)
    if base_s is None or not math.isfinite(base_s):
        return 0.0
    vals: list[float] = []
    for r in perturbed:
        s = _sharpe_from_result(r, cost_version)
        if s is not None and math.isfinite(s):
            vals.append(s)
    if not vals:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((x - mean) ** 2 for x in vals) / len(vals) if vals else 0.0
    std = math.sqrt(var) if var > 0 else 0.0
    if std == 0:
        return 1.0 if all(abs(v - base_s) < 1e-9 for v in vals) else 0.0
    dispersions = [abs(v - base_s) / (abs(base_s) + 1e-9) for v in vals]
    avg_disp = sum(dispersions) / len(dispersions)
    score = max(0.0, min(1.0, 1.0 - avg_disp))
    return float(score)


def cost_perturbation_score(
    config: BacktestConfiguration,
    experiment_id: UUID,
    bump_bps: list[Decimal],
) -> float:
    base_result = run_backtest(
        config=config,
        test_start=config.dataset.bars[0].bar_timestamp,
        test_end=config.dataset.bars[-1].bar_timestamp,
        experiment_id=experiment_id,
    )
    base_cost_version = config.cost_model.cost_model_version
    base_sharpe = _sharpe_from_result(base_result, base_cost_version)
    if base_sharpe is None or not math.isfinite(base_sharpe):
        return 0.0
    scores: list[float] = []
    for bump in bump_bps:
        perturbed_cost = FixedBpsCostModel(
            cost_model_version=f"{base_cost_version}+{bump}bps",
            fee_bps=bump,
            per_trade_fee=Decimal("0"),
        )
        perturbed_config = BacktestConfiguration(
            strategy=config.strategy,
            entry_formula=config.entry_formula,
            exit_formulas=config.exit_formulas,
            dataset=config.dataset,
            cost_model=perturbed_cost,
            fill_quantity=config.fill_quantity,
            dataset_cutoff=config.dataset_cutoff,
            parameter_set_hash=config.parameter_set_hash,
            seed=config.seed,
        )
        res = run_backtest(
            config=perturbed_config,
            test_start=config.dataset.bars[0].bar_timestamp,
            test_end=config.dataset.bars[-1].bar_timestamp,
            experiment_id=experiment_id,
        )
        s = _sharpe_from_result(res, perturbed_cost.cost_model_version)
        if s is not None and math.isfinite(s):
            rel = abs(s - base_sharpe) / (abs(base_sharpe) + 1e-9)
            scores.append(max(0.0, 1.0 - rel))
    if not scores:
        return 0.0
    return float(sum(scores) / len(scores))


def walk_forward_dispersion(fold_sharpes: list[float | None]) -> float | str:
    vals = [v for v in fold_sharpes if v is not None and math.isfinite(v)]
    if len(vals) < 2:
        return "UNKNOWN"
    mean = sum(vals) / len(vals)
    var = sum((x - mean) ** 2 for x in vals) / len(vals)
    std = math.sqrt(var) if var > 0 else 0.0
    if abs(mean) < 1e-9:
        return float(std)
    cv = std / abs(mean)
    return float(cv)


def build_robustness_report(
    *,
    strategy_definition_id: UUID,
    base_result: BacktestResult,
    perturbed_results: list[BacktestResult],
    cost_version: str,
    fold_sharpes: list[float | None] | None,
    created_at: UTCDateTime,
    threshold: float = 0.5,
) -> RobustnessReport:
    param_score = parameter_perturbation_score(base_result, perturbed_results, cost_version)
    wf_disp = walk_forward_dispersion(fold_sharpes) if fold_sharpes is not None else "UNKNOWN"
    if isinstance(wf_disp, float):
        wf_score = max(0.0, min(1.0, 1.0 - min(wf_disp, 1.0)))
    else:
        wf_score = 0.0
    overall = (param_score + wf_score) / 2 if fold_sharpes is not None else param_score
    is_robust = overall >= threshold and param_score >= threshold
    reasons: list[str] = []
    if param_score < threshold:
        reasons.append("PARAMETER_SENSITIVE")
    if isinstance(wf_disp, float) and wf_disp > 1.0:
        reasons.append("WALK_FORWARD_UNSTABLE")
    if wf_disp == "UNKNOWN":
        reasons.append("WALK_FORWARD_UNKNOWN")
    return RobustnessReport(
        report_id=uuid4(),
        strategy_definition_id=strategy_definition_id,
        base_scorecard_id=base_result.result_id,
        parameter_sensitivity_score=float(param_score),
        cost_sensitivity_score=float(param_score),
        timing_sensitivity_score=float(param_score),
        walk_forward_dispersion=wf_disp,  # type: ignore[arg-type]
        is_robust=is_robust,
        reason_codes=tuple(reasons),
        created_at=created_at,
    )


__all__ = [
    "build_robustness_report",
    "cost_perturbation_score",
    "parameter_perturbation_score",
    "walk_forward_dispersion",
]
