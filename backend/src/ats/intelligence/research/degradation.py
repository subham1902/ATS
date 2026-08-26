"""Deterministic strategy degradation monitoring and assessment."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime

from .models import DegradationAction, DegradationAssessment, DegradationMetric


class StrategyDegradationMonitor:
    """Evaluates strategy performance metrics against degradation thresholds."""

    def __init__(
        self,
        *,
        pause_drawdown: Decimal = Decimal("0.15"),
        pause_expectancy: float = -0.20,
        reduce_drawdown: Decimal = Decimal("0.08"),
        reduce_profit_factor: float = 1.00,
        challenger_drift: float = 0.25,
        challenger_cost_sensitivity: float = 0.50,
        review_expectancy: float = 0.10,
        minimum_sample_count: int = 10,
    ) -> None:
        self.pause_drawdown = pause_drawdown
        self.pause_expectancy = pause_expectancy
        self.reduce_drawdown = reduce_drawdown
        self.reduce_profit_factor = reduce_profit_factor
        self.challenger_drift = challenger_drift
        self.challenger_cost_sensitivity = challenger_cost_sensitivity
        self.review_expectancy = review_expectancy
        self.minimum_sample_count = minimum_sample_count

    def assess(
        self,
        *,
        strategy_id: UUID,
        strategy_version: int,
        metrics: DegradationMetric,
        evaluated_at: UTCDateTime,
    ) -> DegradationAssessment:
        """Evaluate degradation state from current running metrics."""
        reasons: list[str] = []

        if metrics.sample_count < self.minimum_sample_count:
            return DegradationAssessment(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                action=DegradationAction.HEALTHY,
                reasons=("INSUFFICIENT_SAMPLE_WINDOW",),
                metrics=metrics,
                evaluated_at=evaluated_at,
            )

        # 1. Critical pause conditions
        if metrics.drawdown_fraction >= self.pause_drawdown:
            reasons.append("CRITICAL_DRAWDOWN_EXCEEDED")
        if metrics.rolling_expectancy_r <= self.pause_expectancy:
            reasons.append("NEGATIVE_EXPECTANCY_BREACH")

        if reasons:
            return DegradationAssessment(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                action=DegradationAction.PAUSE_STRATEGY,
                reasons=tuple(reasons),
                metrics=metrics,
                evaluated_at=evaluated_at,
            )

        # 2. Reduction conditions
        if metrics.drawdown_fraction >= self.reduce_drawdown:
            reasons.append("ELEVATED_DRAWDOWN")
        if metrics.profit_factor < self.reduce_profit_factor:
            reasons.append("PROFIT_FACTOR_SUB_UNITY")

        if reasons:
            return DegradationAssessment(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                action=DegradationAction.REDUCE_ALLOCATION,
                reasons=tuple(reasons),
                metrics=metrics,
                evaluated_at=evaluated_at,
            )

        # 3. Challenger evaluation trigger
        if metrics.calibration_drift >= self.challenger_drift:
            reasons.append("CALIBRATION_DRIFT_DETECTED")
        if metrics.cost_sensitivity >= self.challenger_cost_sensitivity:
            reasons.append("EXCESSIVE_COST_SENSITIVITY")

        if reasons:
            return DegradationAssessment(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                action=DegradationAction.EVALUATE_CHALLENGER,
                reasons=tuple(reasons),
                metrics=metrics,
                evaluated_at=evaluated_at,
            )

        # 4. Review trigger
        if metrics.rolling_expectancy_r < self.review_expectancy:
            reasons.append("SUBOPTIMAL_EXPECTANCY")
            return DegradationAssessment(
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                action=DegradationAction.REVIEW,
                reasons=tuple(reasons),
                metrics=metrics,
                evaluated_at=evaluated_at,
            )

        return DegradationAssessment(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            action=DegradationAction.HEALTHY,
            reasons=("METRICS_WITHIN_NOMINAL_ENVELOPE",),
            metrics=metrics,
            evaluated_at=evaluated_at,
        )


__all__ = ["StrategyDegradationMonitor"]
