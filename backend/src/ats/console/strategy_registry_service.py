"""Strategy Performance Registry service — loads data, computes ratings, ranks strategies."""

from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ats.strategies.identity import resolve_strategy_id

from .strategy_registry_models import (
    BestPerformanceSnapshot,
    EvidenceTier,
    ExecutionContext,
    LeaderboardEntry,
    LeaderboardResponse,
    PerformanceRecord,
    RatingBreakdown,
    StrategyBadge,
    StrategyClassification,
    StrategyPerformanceReport,
    StrategyRating,
    StrategyRegistryEntry,
    StrategyRegistryOverview,
)

_PROJECT_ROOT = Path(r"D:\Projects\ATS")

# Data source paths
_VALIDATION_MANIFEST = _PROJECT_ROOT / "ATS_STRATEGY_VALIDATION_MANIFEST.json"
_TOURNAMENT_RESULTS = _PROJECT_ROOT / "ATS_ALL_STRATEGY_LIVE_TOURNAMENT_RESULTS.csv"
_BIN_TOURNAMENT = _PROJECT_ROOT / "ATS_STRATEGY_TOURNAMENT_RESULTS.csv"
_EVIDENCE_DIR = _PROJECT_ROOT / "evidence" / "strategy_registry"


# ---------------------------------------------------------------------------
# Badge assignment logic
# ---------------------------------------------------------------------------

_FAMILY_TO_BADGE: dict[str, StrategyBadge] = {
    "Baseline": StrategyBadge.BASELINE,
    "Trend": StrategyBadge.INTRADAY,
    "Momentum": StrategyBadge.INTRADAY,
    "Breakout": StrategyBadge.SCALPING,
    "Volatility": StrategyBadge.INTRADAY,
    "Orderflow / State Machine": StrategyBadge.SCALPING,
    "Session": StrategyBadge.INTRADAY,
    "Routing / Meta": StrategyBadge.META_ROUTER,
    "Macro": StrategyBadge.SWING,
    "Cross-Exchange": StrategyBadge.SWING,
    "Fair Value": StrategyBadge.SWING,
    "FX / Currency": StrategyBadge.SWING,
    "Intermarket": StrategyBadge.SWING,
    "Calendar / Carry": StrategyBadge.POSITIONAL,
    "Structural": StrategyBadge.POSITIONAL,
    "Options": StrategyBadge.INTRADAY,
    "Seasonal / Calendar": StrategyBadge.POSITIONAL,
    "Microstructure": StrategyBadge.SCALPING,
    "Liquidity": StrategyBadge.SCALPING,
    "Meta": StrategyBadge.META_ROUTER,
}

# Full strategy family catalogue (40 strategies)
_STRATEGY_FAMILIES: dict[str, str] = {
    "S01": "Trend",
    "S02": "Momentum",
    "S03": "Breakout",
    "S04": "Volatility",
    "S05": "Macro",
    "S06": "Session",
    "S07": "Session",
    "S08": "Session",
    "S09": "Macro",
    "S10": "Cross-Exchange",
    "S11": "Fair Value",
    "S12": "FX / Currency",
    "S13": "Intermarket",
    "S14": "Intermarket",
    "S15": "Microstructure",
    "S16": "Cross-Exchange",
    "S17": "Orderflow / State Machine",
    "S18": "Microstructure",
    "S19": "Microstructure",
    "S20": "Liquidity",
    "S21": "Liquidity",
    "S22": "Calendar / Carry",
    "S23": "Calendar / Carry",
    "S24": "Calendar / Carry",
    "S25": "Structural",
    "S26": "Seasonal / Calendar",
    "S27": "Macro",
    "S28": "Structural",
    "S29": "Session",
    "S30": "Session",
    "S31": "Options",
    "S32": "Options",
    "S33": "Volatility",
    "S34": "Routing / Meta",
    "S35": "Meta",
    "B00": "Baseline",
    "B01": "Baseline",
    "B02": "Baseline",
    "B03": "Baseline",
    "B04": "Baseline",
}

_STRATEGY_FULL_NAMES: dict[str, str] = {
    "S01": "Multi-Timescale Trend Agreement",
    "S02": "Time-Series Momentum (TSMOM)",
    "S03": "Donchian / ATR Breakout",
    "S04": "Volatility Targeting Overlay",
    "S05": "Event Abstention",
    "S06": "London / Europe Session Breakout",
    "S07": "NY Overlap Trend vs Late-Session Fade",
    "S08": "Overnight Gap Digestion",
    "S09": "Real-Yield-Shock Conditioned Momentum",
    "S10": "COMEX Impulse → MCX Continuation",
    "S11": "XAUUSD × USDINR Fair-Value Residual",
    "S12": "USDINR Shock Decomposition",
    "S13": "DXY Divergence Filter",
    "S14": "Gold/Silver Ratio Regime Filter",
    "S15": "GOLDM vs GOLD Micro-Basis / Liquidity Stress",
    "S16": "SGE Night → MCX Morning",
    "S17": "Price × OI × Volume State Machine",
    "S18": "Spread Percentile Gate",
    "S19": "Depth / Order-Book Imbalance",
    "S20": "Liquidity Vacuum Continuation",
    "S21": "Roll-Week Liquidity Vacuum",
    "S22": "Delivery-Week Fair-Value Dislocation",
    "S23": "Term Structure / Carry",
    "S24": "Calendar Spread Relative Value",
    "S25": "Duty-Regime Local Premium Overshoot",
    "S26": "Festival-Season Liquidity / Volume Regime",
    "S27": "RBI / USDINR Defence Day Regime",
    "S28": "Indian Physical Premium Crowding",
    "S29": "Weekend Global-Gold Move → Monday MCX Gap",
    "S30": "DST-Aware Close / Session Effect",
    "S31": "GOLDM Options IV Crush After US Macro Print",
    "S32": "GOLDM Options Skew / IV Signal",
    "S33": "Realized vs Implied Volatility",
    "S34": "Regime-Conditioned Strategy Router",
    "S35": "Meta-Label Filter",
    "B00": "No Trade (Zero Risk)",
    "B01": "Random Entry Same Exit Logic",
    "B02": "Naive Breakout",
    "B03": "Simple Trend",
    "B04": "Buy & Hold Intraday Reference",
}


def _safe_decimal(value: Any, default: str = "0") -> Decimal:
    """Safely parse a value to Decimal."""
    if value is None or value == "" or value == "N/A":
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely parse a value to float."""
    if value is None or value == "" or value == "N/A":
        return default
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return default


def _assign_badge(strategy_id: str, family: str) -> StrategyBadge:
    """Assign a badge to a strategy based on its family."""
    if strategy_id.startswith("B"):
        return StrategyBadge.BASELINE
    return _FAMILY_TO_BADGE.get(family, StrategyBadge.INTRADAY)


# ---------------------------------------------------------------------------
# Rating computation
# ---------------------------------------------------------------------------


def _compute_rating(records: list[PerformanceRecord]) -> StrategyRating:
    """Compute composite rating (0-100) from performance records."""
    if not records:
        return StrategyRating(overall=Decimal("0"), grade="F")

    # Filter records with actual trades
    traded = [r for r in records if r.trades_count > 0]
    if not traded:
        return StrategyRating(overall=Decimal("0"), grade="F")

    # 1. Net expectancy score (0-100): based on per-trade EV
    avg_ev = sum(float(r.ev_per_trade) for r in traded) / len(traded)
    # Scale: -500 → 0, 0 → 40, +500 → 100
    net_exp_raw = max(0, min(100, 40 + avg_ev * 0.12))
    net_expectancy_score = Decimal(str(round(net_exp_raw, 2)))

    # 2. Consistency score (0-100): based on win rate stability
    win_rates = [float(r.win_rate) for r in traded if r.win_rate > 0]
    if win_rates:
        avg_wr = sum(win_rates) / len(win_rates)
        consistency_raw = min(100, avg_wr * 100 * 1.5)  # Scale 50% WR → 75 score
    else:
        consistency_raw = 0
    consistency_score = Decimal(str(round(consistency_raw, 2)))

    # 3. Cost resilience (0-100): can it survive 1.5x and 2x cost multipliers?
    cost_scores: list[float] = []
    for r in traded:
        if r.cost_1_5x_net is not None and r.cost_2_0x_net is not None:
            # Both positive → 100, one negative → 50, both negative → 0
            s = 0.0
            if r.cost_1_5x_net > 0:
                s += 50
            if r.cost_2_0x_net > 0:
                s += 50
            cost_scores.append(s)
        elif r.net_pnl > 0:
            cost_scores.append(30)  # Positive but untested cost stress
        else:
            cost_scores.append(0)
    cost_resilience_score = Decimal(str(round(sum(cost_scores) / max(1, len(cost_scores)), 2)))

    # 4. Drawdown score (0-100): inverse of max drawdown as % of budget
    drawdown_fracs: list[float] = []
    for r in traded:
        if r.capital_budget > 0 and r.max_drawdown != 0:
            dd_frac = abs(float(r.max_drawdown)) / float(r.capital_budget)
            drawdown_fracs.append(dd_frac)
    if drawdown_fracs:
        avg_dd = sum(drawdown_fracs) / len(drawdown_fracs)
        dd_raw = max(0, 100 - avg_dd * 200)  # 50% DD → 0 score
    else:
        dd_raw = 50  # Unknown → median
    drawdown_score = Decimal(str(round(dd_raw, 2)))

    # 5. Sample quality (0-100): based on trade count
    total_trades = sum(r.trades_count for r in traded)
    # Scale: 0 → 0, 20 → 50, 100 → 90, 200+ → 100
    if total_trades >= 200:
        sq_raw = 100.0
    elif total_trades >= 100:
        sq_raw = 90.0
    elif total_trades >= 50:
        sq_raw = 70.0
    elif total_trades >= 20:
        sq_raw = 50.0
    elif total_trades >= 10:
        sq_raw = 30.0
    else:
        sq_raw = max(5, total_trades * 3.0)
    sample_quality_score = Decimal(str(round(sq_raw, 2)))

    # Weighted composite
    overall_raw = (
        float(net_expectancy_score) * 0.30
        + float(consistency_score) * 0.20
        + float(cost_resilience_score) * 0.20
        + float(drawdown_score) * 0.15
        + float(sample_quality_score) * 0.15
    )
    overall = Decimal(str(round(max(0, min(100, overall_raw)), 1)))

    # Grade
    grade: str
    if overall >= 85:
        grade = "S"
    elif overall >= 70:
        grade = "A"
    elif overall >= 55:
        grade = "B"
    elif overall >= 40:
        grade = "C"
    elif overall >= 25:
        grade = "D"
    else:
        grade = "F"

    breakdown = RatingBreakdown(
        net_expectancy_score=net_expectancy_score,
        consistency_score=consistency_score,
        cost_resilience_score=cost_resilience_score,
        drawdown_score=drawdown_score,
        sample_quality_score=sample_quality_score,
    )

    return StrategyRating(overall=overall, grade=grade, breakdown=breakdown)  # type: ignore[arg-type]


def _find_best_performance(records: list[PerformanceRecord]) -> BestPerformanceSnapshot | None:
    """Select the best performance record based on net PnL."""
    if not records:
        return None
    traded = [r for r in records if r.trades_count > 0]
    if not traded:
        return None
    best = max(traded, key=lambda r: float(r.net_pnl))
    return BestPerformanceSnapshot(
        timeframe=best.timeframe,
        execution_context=best.execution_context,
        capital_budget=best.capital_budget,
        net_pnl=best.net_pnl,
        win_rate=best.win_rate,
        profit_factor=best.profit_factor,
        max_drawdown=best.max_drawdown,
        trades_count=best.trades_count,
        measured_at=best.measured_at,
    )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_validation_manifest() -> dict[str, dict[str, Any]]:
    """Load the ATS_STRATEGY_VALIDATION_MANIFEST.json."""
    if not _VALIDATION_MANIFEST.exists():
        return {}
    try:
        with open(_VALIDATION_MANIFEST, encoding="utf-8") as f:
            data = json.load(f)
        result: dict[str, dict[str, Any]] = {}
        for s in data.get("strategies", []):
            sid = s.get("strategy_id", "")
            if sid:
                result[sid] = s
        return result
    except (json.JSONDecodeError, KeyError):
        return {}


def _load_tournament_csv(path: Path) -> dict[str, dict[str, Any]]:
    """Load a tournament CSV file into a dict keyed by strategy id."""
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            result: dict[str, dict[str, Any]] = {}
            for row in reader:
                sid = row.get("Strategy") or row.get("strategy_id") or ""
                if sid:
                    result[sid] = dict(row)
            return result
    except (csv.Error, KeyError):
        return {}


def _build_performance_record_from_manifest(
    strategy_id: str, manifest_entry: dict[str, Any]
) -> PerformanceRecord:
    """Convert a validation manifest entry to a PerformanceRecord."""
    trades = int(manifest_entry.get("trades_count", 0))
    win_rate = _safe_decimal(manifest_entry.get("win_rate"))
    wins = round(trades * float(win_rate)) if trades > 0 else 0

    return PerformanceRecord(
        run_id=f"manifest-{strategy_id}",
        strategy_id=strategy_id,
        timeframe="5m",
        execution_context=ExecutionContext.BACKTEST,
        dataset=str(manifest_entry.get("dataset", "")),
        capital_budget=Decimal("100000"),
        trades_count=trades,
        wins=wins,
        losses=trades - wins,
        win_rate=win_rate,
        gross_pnl=_safe_decimal(manifest_entry.get("gross_pnl_inr")),
        total_costs=_safe_decimal(manifest_entry.get("total_costs_inr")),
        net_pnl=_safe_decimal(manifest_entry.get("net_pnl_inr")),
        profit_factor=_safe_decimal(manifest_entry.get("profit_factor")),
        max_drawdown=_safe_decimal(manifest_entry.get("max_drawdown_inr")),
        ev_per_trade=_safe_decimal(manifest_entry.get("ev_per_trade_inr")),
        t_statistic=_safe_decimal(manifest_entry.get("t_statistic")),
        cost_1_5x_net=_safe_decimal(manifest_entry.get("cost_1_5x_net_inr")),
        cost_2_0x_net=_safe_decimal(manifest_entry.get("cost_2_0x_net_inr")),
        span_start="2026-08-13",
        span_end="2026-09-11",
    )


def _build_performance_record_from_tournament(
    strategy_id: str, row: dict[str, Any]
) -> PerformanceRecord:
    """Convert a tournament CSV row to a PerformanceRecord."""
    trades = int(_safe_float(row.get("Ungated_Trades") or row.get("trades", "0")))
    wins = int(_safe_float(row.get("Wins") or row.get("wins", "0")))
    losses = int(_safe_float(row.get("Losses") or row.get("losses", "0")))

    win_rate_raw = row.get("Win_Rate") or row.get("hit_rate") or "0"
    if isinstance(win_rate_raw, str) and "%" in win_rate_raw:
        wr = _safe_decimal(win_rate_raw.replace("%", "")) / Decimal("100")
    else:
        wr = _safe_decimal(win_rate_raw)
        if wr > 1:
            wr = wr / Decimal("100")

    return PerformanceRecord(
        run_id=f"tournament-{strategy_id}",
        strategy_id=strategy_id,
        timeframe="15m",
        execution_context=ExecutionContext.SHADOW,
        dataset=str(row.get("dataset", "LIVE_TOURNAMENT")),
        capital_budget=Decimal("100000"),
        trades_count=trades,
        wins=wins,
        losses=losses,
        win_rate=wr,
        gross_pnl=_safe_decimal(row.get("Gross_PnL") or row.get("gross_pnl")),
        total_costs=_safe_decimal(row.get("Costs") or row.get("costs")),
        net_pnl=_safe_decimal(row.get("Net_PnL") or row.get("net_pnl")),
        profit_factor=_safe_decimal(row.get("profit_factor", "0")),
        max_drawdown=_safe_decimal(row.get("Max_Drawdown") or row.get("max_drawdown")),
        ev_per_trade=_safe_decimal(row.get("expectancy", "0")),
        cost_1_5x_net=_safe_decimal(row.get("cost_x1_5_net")),
        cost_2_0x_net=_safe_decimal(row.get("cost_x2_net")),
    )


def _build_performance_from_bin_tournament(
    strategy_id: str, row: dict[str, Any]
) -> PerformanceRecord:
    """Convert a BIN strategy tournament row to a PerformanceRecord."""
    trades = int(_safe_float(row.get("trades", "0")))
    hit_rate = _safe_decimal(row.get("hit_rate", "0"))
    if hit_rate > 1:
        hit_rate = hit_rate / Decimal("100")

    return PerformanceRecord(
        run_id=f"bin-tournament-{strategy_id}",
        strategy_id=strategy_id,
        timeframe="15m",
        execution_context=ExecutionContext.PAPER_TRADE,
        dataset=str(row.get("dataset", "")),
        capital_budget=Decimal("100000"),
        trades_count=trades,
        wins=0,
        losses=0,
        win_rate=hit_rate,
        gross_pnl=_safe_decimal(row.get("gross_pnl")),
        total_costs=_safe_decimal(row.get("costs")),
        net_pnl=_safe_decimal(row.get("net_pnl")),
        profit_factor=_safe_decimal(row.get("profit_factor")),
        max_drawdown=_safe_decimal(row.get("max_drawdown")),
        ev_per_trade=_safe_decimal(row.get("expectancy")),
        cost_1_5x_net=_safe_decimal(row.get("cost_x1_5_net")),
        cost_2_0x_net=_safe_decimal(row.get("cost_x2_net")),
        sample_quality=str(row.get("sample_quality", "")),
    )


# ---------------------------------------------------------------------------
# Main registry service
# ---------------------------------------------------------------------------


class StrategyRegistryService:
    """Service that loads, computes, and serves strategy performance data."""

    def __init__(self) -> None:
        self._entries: dict[str, StrategyRegistryEntry] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_all()
            self._loaded = True

    def _load_all(self) -> None:
        """Load all strategy data from canonical sources."""
        manifest = _load_validation_manifest()
        tournament = _load_tournament_csv(_TOURNAMENT_RESULTS)
        bin_tournament = _load_tournament_csv(_BIN_TOURNAMENT)

        # Build entries for all known strategies
        all_ids = set(_STRATEGY_FULL_NAMES.keys())
        all_ids.update(manifest.keys())
        all_ids.update(tournament.keys())

        for sid in sorted(all_ids):
            name = _STRATEGY_FULL_NAMES.get(sid, manifest.get(sid, {}).get("name", sid))
            family = _STRATEGY_FAMILIES.get(sid, "")
            badge = _assign_badge(sid, family)

            # Build performance records from all sources
            records: list[PerformanceRecord] = []

            # From validation manifest (backtest)
            if sid in manifest:
                m = manifest[sid]
                if m.get("trades_count", 0) > 0:
                    records.append(_build_performance_record_from_manifest(sid, m))

            # From live tournament (shadow)
            if sid in tournament:
                t = tournament[sid]
                ungated = int(_safe_float(t.get("Ungated_Trades", "0")))
                if ungated > 0:
                    records.append(_build_performance_record_from_tournament(sid, t))

            # From BIN tournament (paper)
            if sid in bin_tournament:
                records.append(_build_performance_from_bin_tournament(sid, bin_tournament[sid]))

            # Determine classification
            mdata = manifest.get(sid, {})
            classification_raw = mdata.get("classification", "")
            classification_map: dict[str, StrategyClassification] = {
                "REJECTED": StrategyClassification.REJECTED,
                "BLOCKED": StrategyClassification.BLOCKED,
                "VALIDATED": StrategyClassification.VALIDATED,
                "DATA-EVALUABLE": StrategyClassification.DATA_EVALUABLE,
                "BACKTESTABLE": StrategyClassification.BACKTESTABLE,
            }
            classification = classification_map.get(
                classification_raw, StrategyClassification.RESEARCH_ONLY
            )

            # Tournament evidence status
            t_row = tournament.get(sid, {})
            evidence_raw = t_row.get("Evidence_Status", "")
            data_blocked = (
                classification == StrategyClassification.BLOCKED
                or evidence_raw == "DATA_BLOCKED"
            )

            # Implementation status
            impl_status = t_row.get("Implementation", "UNKNOWN")

            # Determine evidence tier
            evidence_tier: EvidenceTier
            if data_blocked:
                evidence_tier = EvidenceTier.DATA_BLOCKED
            elif classification == StrategyClassification.REJECTED:
                evidence_tier = EvidenceTier.REJECTED
            elif sid.startswith("B"):
                evidence_tier = EvidenceTier.BASELINE
            elif sid in bin_tournament:
                evidence_tier = EvidenceTier.ROBUST_FORWARD_CANDIDATE
            elif classification == StrategyClassification.VALIDATED:
                evidence_tier = EvidenceTier.PROSPECTIVE_SHADOW
            else:
                evidence_tier = EvidenceTier.RESEARCH_ACTIVE

            # Compute rating
            rating = _compute_rating(records)
            best = _find_best_performance(records)

            # Aggregated stats
            total_trades = sum(r.trades_count for r in records)
            total_net_pnl = sum((r.net_pnl for r in records), Decimal("0"))
            traded_records = [r for r in records if r.trades_count > 0]
            avg_win_rate = (
                Decimal(
                    str(
                        round(
                            sum(float(r.win_rate) for r in traded_records)
                            / len(traded_records),
                            4,
                        )
                    )
                )
                if traded_records
                else Decimal("0")
            )

            entry = StrategyRegistryEntry(
                strategy_id=sid,
                name=name,
                family=family,
                hypothesis=mdata.get("hypothesis", ""),
                badge=badge,
                classification=classification,
                classification_reason=mdata.get("classification_reason", ""),
                evidence_tier=evidence_tier,
                implementation_status=impl_status,
                rating=rating,
                best_performance=best,
                performance_records=records,
                data_blocked=data_blocked,
                blocker_reason=mdata.get("classification_reason", "") if data_blocked else "",
                shadow_status=t_row.get("Evidence_Status", ""),
                paper_readiness=(
                    "PAPER_CANDIDATE"
                    if evidence_tier == EvidenceTier.ROBUST_FORWARD_CANDIDATE
                    else "NOT_READY"
                ),
                total_trades=total_trades,
                total_net_pnl=total_net_pnl,
                avg_win_rate=avg_win_rate,
            )
            self._entries[sid] = entry

    def reload(self) -> None:
        """Force reload from disk."""
        self._entries.clear()
        self._loaded = False
        self._ensure_loaded()

    def get_registry(self) -> StrategyRegistryOverview:
        """Return the full registry overview."""
        self._ensure_loaded()
        entries = list(self._entries.values())

        rated = [e for e in entries if e.rating.overall > 0]
        blocked = sum(1 for e in entries if e.data_blocked)
        rejected = sum(1 for e in entries if e.classification == StrategyClassification.REJECTED)
        validated = sum(
            1
            for e in entries
            if e.classification
            in {StrategyClassification.VALIDATED, StrategyClassification.DATA_EVALUABLE}
        )

        avg_rating = (
            Decimal(str(round(sum(float(e.rating.overall) for e in rated) / len(rated), 1)))
            if rated
            else Decimal("0")
        )

        badge_dist: dict[str, int] = {}
        for e in entries:
            badge_dist[e.badge.value] = badge_dist.get(e.badge.value, 0) + 1

        return StrategyRegistryOverview(
            total_strategies=len(entries),
            rated_count=len(rated),
            data_blocked_count=blocked,
            rejected_count=rejected,
            validated_count=validated,
            avg_rating=avg_rating,
            top_badge_distribution=badge_dist,
            strategies=entries,
        )

    def get_strategy(self, strategy_id: str) -> StrategyRegistryEntry | None:
        """Get a single strategy entry."""
        self._ensure_loaded()
        return self._entries.get(strategy_id)

    def get_strategy_report(self, strategy_id: str) -> StrategyPerformanceReport | None:
        """Build a detailed performance report for a strategy."""
        self._ensure_loaded()
        entry = self._entries.get(strategy_id)
        if entry is None:
            return None

        by_tf: dict[str, list[PerformanceRecord]] = {}
        by_ctx: dict[str, list[PerformanceRecord]] = {}
        for r in entry.performance_records:
            by_tf.setdefault(r.timeframe, []).append(r)
            by_ctx.setdefault(r.execution_context.value, []).append(r)

        cost_summary: dict[str, str] = {}
        for r in entry.performance_records:
            if r.cost_1_5x_net is not None:
                label = "PASS" if r.cost_1_5x_net > 0 else "FAIL"
                cost_summary[f"{r.timeframe}_1.5x"] = f"{label} (₹{r.cost_1_5x_net})"
            if r.cost_2_0x_net is not None:
                label = "PASS" if r.cost_2_0x_net > 0 else "FAIL"
                cost_summary[f"{r.timeframe}_2.0x"] = f"{label} (₹{r.cost_2_0x_net})"

        return StrategyPerformanceReport(
            strategy=entry,
            performance_by_timeframe=by_tf,
            performance_by_context=by_ctx,
            cost_stress_summary=cost_summary,
        )

    def get_leaderboard(
        self,
        *,
        timeframe: str | None = None,
        context: str | None = None,
        badge: str | None = None,
    ) -> LeaderboardResponse:
        """Build a ranked leaderboard with optional filters."""
        self._ensure_loaded()

        candidates: list[tuple[StrategyRegistryEntry, PerformanceRecord | None]] = []

        for entry in self._entries.values():
            # Filter by badge
            if badge and entry.badge.value != badge:
                continue

            # Find relevant performance records
            relevant = entry.performance_records
            if timeframe:
                relevant = [r for r in relevant if r.timeframe == timeframe]
            if context:
                relevant = [r for r in relevant if r.execution_context.value == context]

            # Use the best relevant record, or None
            if relevant:
                best = max(relevant, key=lambda r: float(r.net_pnl))
                candidates.append((entry, best))
            elif not timeframe and not context:
                # Include all strategies even without records for full view
                candidates.append((entry, None))

        # Sort by rating (descending), then by net PnL of best record
        candidates.sort(
            key=lambda x: (
                float(x[0].rating.overall),
                float(x[1].net_pnl) if x[1] else -999999,
            ),
            reverse=True,
        )

        entries: list[LeaderboardEntry] = []
        for rank, (entry, best_rec) in enumerate(candidates, 1):
            best_snapshot = entry.best_performance
            le = LeaderboardEntry(
                rank=rank,
                strategy_id=entry.strategy_id,
                name=entry.name,
                badge=entry.badge,
                rating=entry.rating,
                best_performance=best_snapshot,
                net_pnl=best_rec.net_pnl if best_rec else Decimal("0"),
                win_rate=best_rec.win_rate if best_rec else Decimal("0"),
                profit_factor=best_rec.profit_factor if best_rec else Decimal("0"),
                max_drawdown=best_rec.max_drawdown if best_rec else Decimal("0"),
                trades_count=best_rec.trades_count if best_rec else 0,
                execution_context=(
                    best_rec.execution_context if best_rec else ExecutionContext.BACKTEST
                ),
                timeframe=best_rec.timeframe if best_rec else "",
                capital_budget=best_rec.capital_budget if best_rec else Decimal("0"),
            )
            entries.append(le)

        return LeaderboardResponse(
            timeframe_filter=timeframe,
            context_filter=context,
            badge_filter=badge,
            total_ranked=len(entries),
            entries=entries,
        )

    def update_live_strategy_performance(
        self,
        strategy_id: str,
        net_pnl: float,
        win_rate: float,
        profit_factor: float,
        trades_count: int,
        lab_status: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        """Dynamically update a strategy's live performance and rating from
        Strategy Lab and Live Agents.
        """
        self._ensure_loaded()
        # Exact full-ID match only. A prefix such as "S02" is not an identity:
        # it would attribute this strategy's live performance to another.
        canonical = resolve_strategy_id(strategy_id, self._entries)
        entry = self._entries[canonical] if canonical is not None else None

        if entry is None:
            # Custom candidate introduced in lab: create a registry entry dynamically
            entry = StrategyRegistryEntry(
                strategy_id=strategy_id,
                name=strategy_id.replace("_", " ").title(),
                family="Incubator",
                hypothesis=(
                    f"Dynamic strategy candidate validated by {agent_name or 'Strategy Lab'}"
                ),
                badge=StrategyBadge.INTRADAY,
                classification=StrategyClassification.DATA_EVALUABLE,
                classification_reason="Live Strategy Lab incubator candidate",
                evidence_tier=EvidenceTier.ROBUST_FORWARD_CANDIDATE,
                implementation_status="LIVE_TESTING",
                rating=StrategyRating(overall=Decimal("50"), grade="C"),
                best_performance=None,
                performance_records=[],
                data_blocked=False,
                blocker_reason="",
                shadow_status=lab_status or "TESTING",
                paper_readiness="PAPER_CANDIDATE",
                total_trades=trades_count,
                total_net_pnl=Decimal(str(round(net_pnl, 2))),
                avg_win_rate=Decimal(
                    str(round(win_rate / 100.0 if win_rate > 1.0 else win_rate, 4))
                ),
            )
            self._entries[strategy_id] = entry

        d_pnl = Decimal(str(round(net_pnl, 2)))
        norm_wr = win_rate / 100.0 if win_rate > 1.0 else win_rate
        d_wr = Decimal(str(round(norm_wr, 4)))
        d_pf = Decimal(str(round(profit_factor, 2)))
        d_ev = Decimal(str(round(net_pnl / max(trades_count, 1), 2)))

        # Models are frozen: build updated copies and swap them in, so a partly
        # applied update can never leave a shared record list half-mutated.
        live_contexts = (ExecutionContext.LIVE_FORWARD, ExecutionContext.REAL_ACCOUNT)
        records = list(entry.performance_records)
        live_idx = next(
            (i for i, r in enumerate(records) if r.execution_context in live_contexts), None
        )
        if live_idx is not None:
            records[live_idx] = records[live_idx].model_copy(
                update={
                    "trades_count": trades_count,
                    "win_rate": d_wr,
                    "profit_factor": d_pf,
                    "ev_per_trade": d_ev,
                    "net_pnl": d_pnl,
                }
            )
        else:
            live_record_fields: dict[str, Any] = {
                "run_id": f"live-forward-{entry.strategy_id}",
                "strategy_id": entry.strategy_id,
                "timeframe": "1m_live",
                "execution_context": ExecutionContext.LIVE_FORWARD,
                "trades_count": trades_count,
                "win_rate": d_wr,
                "profit_factor": d_pf,
                "net_pnl": d_pnl,
                "max_drawdown": Decimal(
                    str(round(abs(net_pnl) * 0.3 if net_pnl < 0 else 250.0, 2))
                ),
                "ev_per_trade": d_ev,
                # `PerformanceRecord` forbids extra fields; the provenance of this
                # measurement belongs in the documented `dataset` slot.
                "dataset": "Live Market Feed",
            }
            records.append(PerformanceRecord(**live_record_fields))

        updates: dict[str, Any] = {
            "performance_records": records,
            "rating": _compute_rating(records),
            "total_trades": sum(r.trades_count for r in records),
            "total_net_pnl": sum((r.net_pnl for r in records), Decimal("0")),
            "best_performance": _find_best_performance(records),
        }
        traded = [r for r in records if r.trades_count > 0]
        if traded:
            updates["avg_win_rate"] = Decimal(
                str(round(sum(float(r.win_rate) for r in traded) / len(traded), 4))
            )
        if lab_status:
            updates["shadow_status"] = lab_status
        self._entries[entry.strategy_id] = entry.model_copy(update=updates)

    def get_strategy_scores_dict(self) -> dict[str, dict[str, Any]]:
        """Return dict of live strategy leaderboard scores, ranks, and ratings."""
        self._ensure_loaded()
        lb = self.get_leaderboard()
        result: dict[str, dict[str, Any]] = {}
        for le in lb.entries:
            score_data = {
                "rank": le.rank,
                "score": float(le.rating.overall),
                "grade": le.rating.grade,
                "badge": le.badge.value,
                "net_pnl": float(le.net_pnl),
                "win_rate": float(le.win_rate),
                "trades_count": le.trades_count,
            }
            result[le.strategy_id] = score_data
        return result


# Module-level singleton
_service: StrategyRegistryService | None = None


def get_registry_service() -> StrategyRegistryService:
    """Return the module-level singleton; create on first call."""
    global _service
    if _service is None:
        _service = StrategyRegistryService()
    return _service


__all__ = ["StrategyRegistryService", "get_registry_service"]
