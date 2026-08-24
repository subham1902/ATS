"""Strategy Lab — research-only deterministic foundation."""

from .backtest import BacktestConfiguration, run_backtest
from .cost_model import CostModel, FixedBpsCostModel, ZeroCostModel
from .dataset_binding import DatasetBinding
from .experiment_runner import build_experiment, run_experiment
from .leakage_scanner import LeakageScanResult, scan_leakage
from .promotion_gate import PromotionEvaluationResult, PromotionEvaluationStatus, evaluate_promotion
from .scorecard import build_scorecard
from .types import (
    BacktestResult,
    FillAssumption,
    ResearchFill,
    ResearchSignal,
    ResearchTrade,
    WalkForwardPlan,
    WalkForwardWindow,
)
from .walk_forward import build_rolling_plan, split_for_experiment

__all__ = [
    "BacktestConfiguration",
    "BacktestResult",
    "CostModel",
    "DatasetBinding",
    "FillAssumption",
    "FixedBpsCostModel",
    "LeakageScanResult",
    "PromotionEvaluationResult",
    "PromotionEvaluationStatus",
    "ResearchFill",
    "ResearchSignal",
    "ResearchTrade",
    "WalkForwardPlan",
    "WalkForwardWindow",
    "ZeroCostModel",
    "build_experiment",
    "build_rolling_plan",
    "build_scorecard",
    "evaluate_promotion",
    "run_backtest",
    "run_experiment",
    "scan_leakage",
    "split_for_experiment",
]
