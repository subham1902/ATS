"""ScorecardBuilder — frozen StrategyScorecard metrics, no NaN/Infinity."""

from __future__ import annotations

import math
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.intelligence.models import StrategyScorecard
from ats.contracts.intelligence.types import ScorecardValidationStatus

from .types import BacktestResult


def _safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    v = a / b
    if not math.isfinite(v):
        return None
    return v


def build_scorecard(
    *,
    strategy_definition_id: UUID,
    strategy_definition_version: int,
    experiment_ids: tuple[UUID, ...],
    result: BacktestResult,
    created_at: UTCDateTime,
    cost_model_version: str | None = None,
) -> StrategyScorecard:
    trades = result.trades
    trade_count = len(trades)
    sample_count = len(trades)  # For v1, sample == trade count

    # Net return fraction: sum pnl_fraction
    if trade_count == 0:
        net_return = 0.0
        expectancy_r: float = 0.0
        profit_factor_val: float | None = None
        win_rate_val: Decimal | None = None
        avg_win_r: float | None = None
        avg_loss_r: float | None = None
        max_dd_val = Decimal("0")
        sharpe_val: float | None = None
        sortino_val: float | None = None
        tail_loss: float = 0.0
        turnover_val: float = 0.0
        estimated_costs = Decimal("0")
        stability = 0.0
        param_sens = 0.0
        regime_cov = 0.0
        benchmark_delta = 0.0
    else:
        pnls = [float(t.pnl_fraction) if t.pnl_fraction is not None else 0.0 for t in trades]
        rs = [float(t.pnl_r) if t.pnl_r is not None else 0.0 for t in trades]
        net_return = sum(pnls)
        # Expectancy R = mean R
        expectancy_r = sum(rs) / len(rs) if rs else 0.0

        wins = [x for x in rs if x > 0]
        losses = [x for x in rs if x < 0]
        win_rate_val = Decimal(len(wins)) / Decimal(trade_count) if trade_count else None
        # Profit factor: sum wins / abs(sum losses)
        gross_win = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        if gross_loss == 0:
            profit_factor_val = (
                None if gross_win == 0 else None
            )  # undefined per spec when no losses? Use None
            # Actually if all wins, profit_factor undefined -> None
            if gross_win > 0 and gross_loss == 0:
                profit_factor_val = None
        else:
            pf = gross_win / gross_loss
            profit_factor_val = float(pf) if math.isfinite(pf) and pf >= 0 else None

        avg_win_r = float(sum(wins) / len(wins)) if wins else None
        avg_loss_r = float(sum(losses) / len(losses)) if losses else None

        # Maximum drawdown on cumulative pnl curve (fraction)
        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cum += p
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd
        max_dd_val = Decimal(str(max_dd)) if max_dd >= 0 else Decimal("0")
        # Ensure within 0..1 for PortfolioFraction? It is PortfolioFraction 0..1, clamp
        if max_dd_val > Decimal("1"):
            max_dd_val = Decimal("1")
        if max_dd_val < Decimal("0"):
            max_dd_val = Decimal("0")

        # Sharpe: mean(pnl)/std(pnl) * sqrt(trades) (annualization not defined, use raw)
        mean_pnl = sum(pnls) / len(pnls) if pnls else 0.0
        var = sum((x - mean_pnl) ** 2 for x in pnls) / len(pnls) if pnls else 0.0
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe_val = (mean_pnl / std * math.sqrt(len(pnls))) if std != 0 else None
        if sharpe_val is not None and not math.isfinite(sharpe_val):
            sharpe_val = None
        # Sortino: mean / downside std
        downside = [x for x in pnls if x < 0]
        if downside:
            d_var = sum((x - mean_pnl) ** 2 for x in downside) / len(downside)
            d_std = math.sqrt(d_var) if d_var > 0 else 0.0
            sortino_val = (mean_pnl / d_std * math.sqrt(len(pnls))) if d_std != 0 else None
            if sortino_val is not None and not math.isfinite(sortino_val):
                sortino_val = None
        else:
            sortino_val = None

        tail_loss = abs(min(pnls)) if pnls else 0.0
        if not math.isfinite(tail_loss):
            tail_loss = 0.0
        turnover_val = float(trade_count)  # minimal turnover = trade count
        # Estimated costs: sum fill costs
        total_cost = sum((f.cost for f in result.fills), Decimal("0"))
        estimated_costs = total_cost
        # Stability / sensitivity / regime coverage: insufficient evidence deterministic 0.0 for v1
        stability = 0.0
        param_sens = 0.0
        regime_cov = 0.0
        benchmark_delta = 0.0
        # Clamp turnover etc to finite
        if not math.isfinite(turnover_val):
            turnover_val = 0.0

    # Placeholder zero-cost fixtures are deterministic, but not authoritative
    # promotion evidence. The caller must bind the same version recorded by
    # the backtest result.
    cost_evidence_valid = (
        result.cost_model_authoritative is True
        and result.cost_model_version is not None
        and cost_model_version == result.cost_model_version
    )
    if trade_count == 0 or not cost_evidence_valid:
        validation_status = ScorecardValidationStatus.INSUFFICIENT_EVIDENCE
    else:
        validation_status = ScorecardValidationStatus.PASS

    scorecard_id = uuid5(result.result_id, "scorecard")

    scorecard = StrategyScorecard(
        schema_version="1.0",
        scorecard_id=scorecard_id,
        strategy_definition_id=strategy_definition_id,
        strategy_definition_version=strategy_definition_version,
        experiment_ids=experiment_ids,
        evaluation_start=result.start_time,
        evaluation_end=result.end_time,
        sample_count=sample_count,
        trade_count=trade_count,
        net_return_fraction=float(net_return) if math.isfinite(net_return) else 0.0,
        expectancy_r=float(expectancy_r) if math.isfinite(expectancy_r) else 0.0,
        profit_factor=profit_factor_val,
        win_rate=win_rate_val,
        average_win_r=avg_win_r,
        average_loss_r=avg_loss_r,
        maximum_drawdown=max_dd_val,
        sharpe=sharpe_val,
        sortino=sortino_val,
        tail_loss_metric=float(tail_loss),
        turnover=float(turnover_val),
        estimated_costs=estimated_costs,
        stability_score=float(stability),
        parameter_sensitivity_score=float(param_sens),
        regime_coverage_score=float(regime_cov),
        benchmark_delta=float(benchmark_delta),
        validation_status=validation_status,
        created_at=created_at,
        payload_hash="0" * 64,
    )
    return scorecard.model_copy(update={"payload_hash": compute_payload_hash(scorecard)})


__all__ = ["build_scorecard"]
