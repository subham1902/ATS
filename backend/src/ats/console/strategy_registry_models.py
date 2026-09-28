"""Strategy Performance Registry models — ratings, badges, leaderboard, and reports."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from ats.contracts.common import ATSBaseModel
from ats.contracts.enums import ATSStringEnum

# ---------------------------------------------------------------------------
# Badge and context enums
# ---------------------------------------------------------------------------


class StrategyBadge(ATSStringEnum):
    """Classification badge based on strategy holding behaviour."""

    SCALPING = "SCALPING"
    INTRADAY = "INTRADAY"
    SWING = "SWING"
    POSITIONAL = "POSITIONAL"
    LONG_TERM = "LONG_TERM"
    META_ROUTER = "META_ROUTER"
    BASELINE = "BASELINE"


class ExecutionContext(ATSStringEnum):
    """Where the strategy performance was measured."""

    BACKTEST = "BACKTEST"
    PAPER_TRADE = "PAPER_TRADE"
    SHADOW = "SHADOW"
    LIVE_FORWARD = "LIVE_FORWARD"
    REAL_ACCOUNT = "REAL_ACCOUNT"


class StrategyClassification(ATSStringEnum):
    """Current validation classification status."""

    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    VALIDATED = "VALIDATED"
    DATA_EVALUABLE = "DATA_EVALUABLE"
    BACKTESTABLE = "BACKTESTABLE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SURVIVOR = "SURVIVOR"


class EvidenceTier(ATSStringEnum):
    """Final evidence quality tier."""

    ROBUST_FORWARD_CANDIDATE = "ROBUST_FORWARD_CANDIDATE"
    PROSPECTIVE_SHADOW = "PROSPECTIVE_SHADOW"
    RESEARCH_ACTIVE = "RESEARCH_ACTIVE"
    DATA_BLOCKED = "DATA_BLOCKED"
    REJECTED = "REJECTED"
    BASELINE = "BASELINE"


# ---------------------------------------------------------------------------
# Performance record — one per strategy-run combination
# ---------------------------------------------------------------------------


class PerformanceRecord(ATSBaseModel):
    """A single performance measurement of a strategy in a specific context."""

    run_id: str = Field(description="Unique identifier for this performance run")
    strategy_id: str
    timeframe: str = Field(description="Bar timeframe: 5m, 15m, 1h, 4h, daily")
    execution_context: ExecutionContext
    dataset: str = Field(default="", description="Dataset used for this run")

    # Capital
    capital_budget: Decimal = Decimal("0")
    capital_currency: str = "INR"

    # Core metrics
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    flat: int = 0
    win_rate: Decimal = Decimal("0")
    gross_pnl: Decimal = Decimal("0")
    total_costs: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None
    ev_per_trade: Decimal = Decimal("0")
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    payoff_ratio: Decimal = Decimal("0")

    # Cost stress
    cost_1_5x_net: Decimal | None = None
    cost_2_0x_net: Decimal | None = None

    # Statistical
    t_statistic: Decimal | None = None
    sample_quality: str = ""

    # Timing
    measured_at: str = ""
    span_start: str = ""
    span_end: str = ""


# ---------------------------------------------------------------------------
# Strategy rating
# ---------------------------------------------------------------------------


class RatingBreakdown(ATSBaseModel):
    """Component scores making up the overall strategy rating."""

    net_expectancy_score: Decimal = Decimal("0")
    consistency_score: Decimal = Decimal("0")
    cost_resilience_score: Decimal = Decimal("0")
    drawdown_score: Decimal = Decimal("0")
    sample_quality_score: Decimal = Decimal("0")


class StrategyRating(ATSBaseModel):
    """Composite quality rating for a strategy (0-100)."""

    overall: Decimal = Decimal("0")
    grade: Literal["S", "A", "B", "C", "D", "F"] = "F"
    breakdown: RatingBreakdown = Field(default_factory=RatingBreakdown)


# ---------------------------------------------------------------------------
# Best performance snapshot
# ---------------------------------------------------------------------------


class BestPerformanceSnapshot(ATSBaseModel):
    """The single best performance record summary for display."""

    timeframe: str = ""
    execution_context: ExecutionContext = ExecutionContext.BACKTEST
    capital_budget: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    trades_count: int = 0
    measured_at: str = ""


# ---------------------------------------------------------------------------
# Registry entry — one per strategy
# ---------------------------------------------------------------------------


class StrategyRegistryEntry(ATSBaseModel):
    """Full registry record for one strategy."""

    strategy_id: str
    name: str
    family: str = ""
    hypothesis: str = ""
    badge: StrategyBadge = StrategyBadge.INTRADAY
    classification: StrategyClassification = StrategyClassification.RESEARCH_ONLY
    classification_reason: str = ""
    evidence_tier: EvidenceTier = EvidenceTier.RESEARCH_ACTIVE
    implementation_status: str = ""

    # Computed fields
    rating: StrategyRating = Field(default_factory=StrategyRating)
    best_performance: BestPerformanceSnapshot | None = None
    performance_records: list[PerformanceRecord] = Field(default_factory=list)

    # Data dependency
    data_blocked: bool = False
    blocker_reason: str = ""

    # Tournament
    shadow_status: str = ""
    paper_readiness: str = ""

    # Aggregated stats across all runs
    total_trades: int = 0
    total_net_pnl: Decimal = Decimal("0")
    avg_win_rate: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Leaderboard entry — ranked strategy for display
# ---------------------------------------------------------------------------


class LeaderboardEntry(ATSBaseModel):
    """One row on the strategy leaderboard."""

    rank: int
    strategy_id: str
    name: str
    badge: StrategyBadge
    rating: StrategyRating
    best_performance: BestPerformanceSnapshot | None = None

    # Key display metrics from best run
    net_pnl: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    trades_count: int = 0
    sharpe_ratio: Decimal | None = None
    execution_context: ExecutionContext = ExecutionContext.BACKTEST
    timeframe: str = ""
    capital_budget: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StrategyRegistryOverview(ATSBaseModel):
    """Full registry overview response."""

    total_strategies: int
    rated_count: int
    data_blocked_count: int
    rejected_count: int
    validated_count: int
    avg_rating: Decimal = Decimal("0")
    top_badge_distribution: dict[str, int] = Field(default_factory=dict)
    strategies: list[StrategyRegistryEntry]


class LeaderboardResponse(ATSBaseModel):
    """Leaderboard response with filter metadata."""

    timeframe_filter: str | None = None
    context_filter: str | None = None
    badge_filter: str | None = None
    total_ranked: int = 0
    entries: list[LeaderboardEntry]


class StrategyPerformanceReport(ATSBaseModel):
    """Detailed performance report for a single strategy."""

    strategy: StrategyRegistryEntry
    performance_by_timeframe: dict[str, list[PerformanceRecord]] = Field(default_factory=dict)
    performance_by_context: dict[str, list[PerformanceRecord]] = Field(default_factory=dict)
    cost_stress_summary: dict[str, str] = Field(default_factory=dict)
    regime_analysis: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "BestPerformanceSnapshot",
    "EvidenceTier",
    "ExecutionContext",
    "LeaderboardEntry",
    "LeaderboardResponse",
    "PerformanceRecord",
    "RatingBreakdown",
    "StrategyBadge",
    "StrategyClassification",
    "StrategyPerformanceReport",
    "StrategyRating",
    "StrategyRegistryEntry",
    "StrategyRegistryOverview",
]
