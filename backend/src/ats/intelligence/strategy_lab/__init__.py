"""Strategy Lab — research-only deterministic foundation."""

from .anti_overfit import (
    build_lineage,
    build_overfit_evidence,
    cscv_evidence,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pbo_evidence,
    probabilistic_sharpe_ratio,
)
from .backtest import BacktestConfiguration, run_backtest
from .cost_model import (
    CONSERVATIVE_COST_MODEL_VERSION,
    COST_MODEL_REGISTRY,
    ConservativeCostModel,
    CostModel,
    FixedBpsCostModel,
    IndiaCashCostModel,
    ZeroCostModel,
    default_india_conservative_cost_model,
)
from .dataset_binding import DatasetBinding
from .experiment_runner import build_experiment, run_experiment
from .leakage_scanner import LeakageScanResult, scan_leakage
from .promotion_gate import PromotionEvaluationResult, PromotionEvaluationStatus, evaluate_promotion
from .robustness import (
    build_robustness_report,
    cost_perturbation_score,
    parameter_perturbation_score,
    walk_forward_dispersion,
)
from .scorecard import build_scorecard
from .types import (
    BacktestResult,
    ExperimentLineage,
    FillAssumption,
    OverfitEvidence,
    ResearchFill,
    ResearchSignal,
    ResearchTrade,
    RobustnessReport,
    WalkForwardPlan,
    WalkForwardWindow,
)
from .walk_forward import build_rolling_plan, split_for_experiment

__all__ = [
    "BacktestConfiguration",
    "BacktestResult",
    "CONSERVATIVE_COST_MODEL_VERSION",
    "COST_MODEL_REGISTRY",
    "ConservativeCostModel",
    "CostModel",
    "DatasetBinding",
    "ExperimentLineage",
    "FillAssumption",
    "FixedBpsCostModel",
    "IndiaCashCostModel",
    "LeakageScanResult",
    "OverfitEvidence",
    "PromotionEvaluationResult",
    "PromotionEvaluationStatus",
    "ResearchFill",
    "ResearchSignal",
    "ResearchTrade",
    "RobustnessReport",
    "WalkForwardPlan",
    "WalkForwardWindow",
    "ZeroCostModel",
    "build_experiment",
    "build_lineage",
    "build_overfit_evidence",
    "build_robustness_report",
    "build_rolling_plan",
    "build_scorecard",
    "cost_perturbation_score",
    "cscv_evidence",
    "deflated_sharpe_ratio",
    "default_india_conservative_cost_model",
    "evaluate_promotion",
    "expected_max_sharpe",
    "parameter_perturbation_score",
    "pbo_evidence",
    "probabilistic_sharpe_ratio",
    "run_backtest",
    "run_experiment",
    "scan_leakage",
    "split_for_experiment",
    "walk_forward_dispersion",
]
