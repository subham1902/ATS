"""Live shadow tournament engine for imported binary strategies.

Feeds normalized market data from MarketDataFabric to all registered adapters.
Tracks shadow metrics independently per strategy.
Terminates strictly at shadow telemetry; NEVER routes to PaperBroker or order APIs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from ats.contracts.common import ClockProtocol, SystemClock
from ats.market.fabric import BarInterval, MarketDataFabric
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate

from .adapters import (
    MarketSnapshotContext,
    StrategyAdapterProtocol,
    create_all_adapters,
)
from .models import ShadowMetrics, StrategyDecision, StrategyStatus

LOGGER = logging.getLogger(__name__)

FRICTION_PER_TRADE = Decimal("40.00")  # Documented MCX Gold friction per trade


@dataclass
class ShadowTrajectory:
    """An open or closed shadow trade trajectory."""

    strategy_id: str
    direction: Literal["LONG", "SHORT"]
    entry_price: Decimal
    entry_time: datetime
    exit_price: Decimal | None = None
    exit_time: datetime | None = None
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    gross_pnl: Decimal = Decimal("0.00")
    costs: Decimal = FRICTION_PER_TRADE
    net_pnl: Decimal = Decimal("0.00")
    is_closed: bool = False
    mae: Decimal = Decimal("0.00")
    mfe: Decimal = Decimal("0.00")
    lifecycle_status: Literal["OPEN", "RESOLVED_VALID", "RESOLVED_INVALID"] = "OPEN"


class ShadowTournamentEngine:
    """Orchestrates shadow tournament for imported strategies over MarketDataFabric."""

    def __init__(
        self,
        fabric: MarketDataFabric,
        clock: ClockProtocol | None = None,
        adapters: list[StrategyAdapterProtocol] | None = None,
        include_native: bool = True,
        persistence_dir: Path | None = None,
    ) -> None:
        self._fabric = fabric
        self._clock = clock or SystemClock()
        self._adapters: dict[str, StrategyAdapterProtocol] = {
            a.strategy_id: a
            for a in (adapters or create_all_adapters(include_native=include_native))
        }
        self._metrics: dict[str, ShadowMetrics] = {
            a.strategy_id: ShadowMetrics(
                strategy_id=a.strategy_id,
                model_name=a.model_name,
                is_native=(a.strategy_id == "S17"),
            )
            for a in self._adapters.values()
        }
        self._open_trajectories: dict[str, ShadowTrajectory] = {}
        self._closed_trajectories: list[ShadowTrajectory] = []
        self._total_ticks_processed = 0
        self._persistence_dir = persistence_dir
        if self._persistence_dir:
            self._persistence_dir.mkdir(parents=True, exist_ok=True)
            self._metrics_file: Path | None = self._persistence_dir / "shadow_metrics.json"
            self._ledger_file: Path | None = self._persistence_dir / "shadow_ledger.jsonl"
        else:
            self._metrics_file = None
            self._ledger_file = None

    def load_state(self) -> None:
        """Hydrate metrics and closed trajectories from persistence."""
        if not self._persistence_dir or not self._metrics_file or not self._ledger_file:
            return

        # Load metrics
        if self._metrics_file.exists():
            try:
                with open(self._metrics_file, encoding="utf-8") as f:
                    metrics_data = json.load(f)
                    for k, v in metrics_data.items():
                        if k in self._metrics:
                            self._metrics[k] = ShadowMetrics.model_validate(v)
            except Exception as e:
                LOGGER.error("Failed to load metrics from %s: %s", self._metrics_file, e)

        # Load ledger for closed trajectories
        if self._ledger_file.exists():
            try:
                seen_hashes = set()
                with open(self._ledger_file, encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        # Content hashing to prevent duplicate prevention
                        traj_hash = hash(
                            (data["strategy_id"], data["entry_time"], data["exit_time"])
                        )
                        if traj_hash not in seen_hashes:
                            seen_hashes.add(traj_hash)
                            traj = ShadowTrajectory(
                                strategy_id=data["strategy_id"],
                                direction=data["direction"],
                                entry_price=Decimal(data["entry_price"]),
                                entry_time=datetime.fromisoformat(data["entry_time"]),
                                exit_price=(
                                    Decimal(data["exit_price"])
                                    if data.get("exit_price")
                                    else None
                                ),
                                exit_time=(
                                    datetime.fromisoformat(data["exit_time"])
                                    if data.get("exit_time")
                                    else None
                                ),
                                stop_price=(
                                    Decimal(data["stop_price"])
                                    if data.get("stop_price")
                                    else None
                                ),
                                target_price=(
                                    Decimal(data["target_price"])
                                    if data.get("target_price")
                                    else None
                                ),
                                gross_pnl=Decimal(data["gross_pnl"]),
                                costs=Decimal(data["costs"]),
                                net_pnl=Decimal(data["net_pnl"]),
                                is_closed=data["is_closed"],
                                mae=Decimal(data["mae"]),
                                mfe=Decimal(data["mfe"]),
                                lifecycle_status=data.get("lifecycle_status", "RESOLVED_VALID"),
                            )
                            self._closed_trajectories.append(traj)
            except Exception as e:
                LOGGER.error("Failed to load ledger from %s: %s", self._ledger_file, e)

    def save_state(self, new_closed_traj: ShadowTrajectory | None = None) -> None:
        """Persist metrics and optionally append a closed trajectory to the ledger."""
        if not self._persistence_dir or not self._metrics_file or not self._ledger_file:
            return

        try:
            metrics_dict = {k: json.loads(v.model_dump_json()) for k, v in self._metrics.items()}
            with open(self._metrics_file, "w", encoding="utf-8") as f:
                json.dump(metrics_dict, f, indent=2)

            if new_closed_traj:
                data = asdict(new_closed_traj)
                # Convert Decimals and datetimes to string for JSON
                for k, v in data.items():
                    if isinstance(v, Decimal):
                        data[k] = str(v)
                    elif isinstance(v, datetime):
                        data[k] = v.isoformat()
                with open(self._ledger_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data) + "\n")
        except Exception as e:
            LOGGER.error("Failed to save state: %s", e)

    @property
    def metrics(self) -> dict[str, ShadowMetrics]:
        return dict(self._metrics)

    def on_tick(self, update: NormalizedFeedUpdate) -> dict[str, StrategyDecision | None]:
        """Process one normalized feed tick across all registered adapters."""
        self._total_ticks_processed += 1
        price = update.last_traded_price
        if price is None:
            return {}

        now = update.exchange_timestamp or update.received_at or self._clock.now()
        freshness_sec = max(0.0, (self._clock.now() - now).total_seconds())

        # Extract recent closes from fabric for indicator computation
        bars_5m = self._fabric.bars(update.instrument_key, BarInterval.M5)
        bars_1h = self._fabric.bars(update.instrument_key, BarInterval.H1)

        recent_5m_closes = tuple(b.close for b in bars_5m if b.close is not None)
        recent_5m_highs = tuple(b.high for b in bars_5m if b.high is not None)
        recent_5m_lows = tuple(b.low for b in bars_5m if b.low is not None)
        recent_5m_volumes = tuple(b.volume or 0 for b in bars_5m)
        recent_1h_closes = tuple(b.close for b in bars_1h if b.close is not None)

        # Context levels
        pdh = max(recent_5m_highs) if recent_5m_highs else None
        pdl = min(recent_5m_lows) if recent_5m_lows else None
        or_high = bars_5m[0].high if bars_5m and bars_5m[0].high is not None else None
        or_low = bars_5m[0].low if bars_5m and bars_5m[0].low is not None else None

        # Determine regime from price structure
        regime = "UNKNOWN"
        if len(recent_5m_closes) >= 5:
            c_first, c_last = recent_5m_closes[0], recent_5m_closes[-1]
            if c_last > c_first * Decimal("1.002"):
                regime = "TREND"
            elif c_last < c_first * Decimal("0.998"):
                regime = "TREND"
            else:
                regime = "RANGE"

        context = MarketSnapshotContext(
            instrument_key=update.instrument_key,
            timestamp=now,
            last_price=price,
            volume=update.volume,
            bid_price=update.bid_price,
            ask_price=update.ask_price,
            recent_5m_closes=recent_5m_closes,
            recent_5m_highs=recent_5m_highs,
            recent_5m_lows=recent_5m_lows,
            recent_5m_volumes=recent_5m_volumes,
            recent_1h_closes=recent_1h_closes,
            pdh=pdh,
            pdl=pdl,
            is_yesterday_nr7=True,  # Admitted via reference history
            opening_range_high=or_high,
            opening_range_low=or_low,
            open_interest=update.open_interest,
            open_interest_change=update.open_interest_change,
        )

        decisions: dict[str, StrategyDecision | None] = {}

        # Evaluate each adapter in complete sandbox isolation
        for strat_id, adapter in self._adapters.items():
            decision = None
            try:
                decision = adapter.on_market_event(context)
            except Exception as e:
                LOGGER.error("Strategy %s raised exception during evaluation: %s", strat_id, e)
                decision = None

            if getattr(adapter, "_in_error_state", False):
                m = self._metrics[strat_id]
                self._metrics[strat_id] = m.model_copy(
                    update={"status": StrategyStatus.RUNTIME_BLOCKED}
                )
                decisions[strat_id] = None
                continue

            decisions[strat_id] = decision
            if decision is not None:
                self._apply_decision(strat_id, decision, price, now, regime, freshness_sec)

            # Update open trajectory MFE/MAE
            if strat_id in self._open_trajectories:
                traj = self._open_trajectories[strat_id]
                diff = (
                    price - traj.entry_price
                    if traj.direction == "LONG"
                    else traj.entry_price - price
                )
                if diff > traj.mfe:
                    traj.mfe = diff
                if diff < traj.mae:
                    traj.mae = diff

        return decisions

    def _apply_decision(
        self,
        strategy_id: str,
        decision: StrategyDecision,
        current_price: Decimal,
        timestamp: datetime,
        regime: str = "UNKNOWN",
        freshness_sec: float = 0.0,
    ) -> None:
        m = self._metrics[strategy_id]
        new_signals = m.signals_generated + 1
        new_valid = m.valid_signals + 1
        new_long = m.long_count + (1 if decision.direction == "LONG" else 0)
        new_short = m.short_count + (1 if decision.direction == "SHORT" else 0)

        open_traj = self._open_trajectories.get(strategy_id)

        if decision.action in ["BUY", "SELL"] and open_traj is None:
            # Open a new shadow trajectory
            direction: Literal["LONG", "SHORT"] = (
                "LONG" if decision.direction == "LONG" else "SHORT"
            )
            traj = ShadowTrajectory(
                strategy_id=strategy_id,
                direction=direction,
                entry_price=decision.entry_reference or current_price,
                entry_time=timestamp,
                stop_price=decision.stop,
                target_price=decision.target,
            )
            self._open_trajectories[strategy_id] = traj
            self._metrics[strategy_id] = m.model_copy(
                update={
                    "signals_generated": new_signals,
                    "valid_signals": new_valid,
                    "long_count": new_long,
                    "short_count": new_short,
                    "open_trajectories": 1,
                    "regime": regime,
                    "data_freshness_sec": freshness_sec,
                    "status": StrategyStatus.SHADOW_RUNNING,
                }
            )

        elif decision.action == "CLOSE" and open_traj is not None:
            # Close existing shadow trajectory
            open_traj.exit_price = decision.entry_reference or current_price
            open_traj.exit_time = timestamp
            open_traj.is_closed = True
            open_traj.lifecycle_status = "RESOLVED_VALID"

            diff = (
                open_traj.exit_price - open_traj.entry_price
                if open_traj.direction == "LONG"
                else open_traj.entry_price - open_traj.exit_price
            )
            open_traj.gross_pnl = diff
            open_traj.net_pnl = diff - open_traj.costs

            is_win = open_traj.net_pnl > 0
            new_wins = m.wins + (1 if is_win else 0)
            new_losses = m.losses + (0 if is_win else 1)
            new_gross = m.gross_pnl + open_traj.gross_pnl
            new_costs = m.costs + open_traj.costs
            new_net = m.net_pnl + open_traj.net_pnl
            new_resolved = m.resolved_trajectories + 1
            win_rate = round(float(new_wins) / float(new_resolved), 4) if new_resolved > 0 else 0.0

            # Profit factor calculation
            gross_win = sum(
                t.gross_pnl
                for t in self._closed_trajectories
                if t.strategy_id == strategy_id and t.gross_pnl > 0
            ) + (open_traj.gross_pnl if open_traj.gross_pnl > 0 else Decimal("0.00"))
            gross_loss = abs(
                sum(
                    t.gross_pnl
                    for t in self._closed_trajectories
                    if t.strategy_id == strategy_id and t.gross_pnl < 0
                )
                + (open_traj.gross_pnl if open_traj.gross_pnl < 0 else Decimal("0.00"))
            )
            pf = (
                round(float(gross_win) / float(gross_loss), 2)
                if gross_loss > 0
                else (1.0 if gross_win == 0 else 99.99)
            )

            # Cost stress tests (Base, 1.5x, 2.0x)
            cost_base = new_costs
            cost_1_5x = new_costs * Decimal("1.5")
            cost_2_0x = new_costs * Decimal("2.0")

            # Holding time
            holding_time_sec = (
                (open_traj.exit_time - open_traj.entry_time).total_seconds()
                if (open_traj.exit_time and open_traj.entry_time)
                else 0.0
            )

            # Expectancy
            expectancy = (
                round(new_net / Decimal(str(new_resolved)), 2)
                if new_resolved > 0
                else Decimal("0.00")
            )

            self._closed_trajectories.append(open_traj)
            del self._open_trajectories[strategy_id]

            sample_status: Literal["INSUFFICIENT_EVIDENCE", "VALIDATED"] = (
                "VALIDATED" if new_resolved >= 20 else "INSUFFICIENT_EVIDENCE"
            )

            status = StrategyStatus.SHADOW_RUNNING
            if sample_status == "INSUFFICIENT_EVIDENCE":
                status = StrategyStatus.INSUFFICIENT_EVIDENCE
            elif (
                new_resolved >= 20
                and expectancy > 0
                and new_net > 0
                and (new_net - cost_2_0x) > 0
            ):
                # Passes all promotion gates: 20+ resolved, +ve expectancy, and cost
                # robustness (net > 0 even with 2x costs).
                status = StrategyStatus.REVIEW_REQUIRED
            elif new_net > 0:
                status = StrategyStatus.PROMISING_SHADOW
            else:
                status = StrategyStatus.REJECTED_SHADOW

            regime_class = (
                "INSUFFICIENT_EVIDENCE"
                if new_resolved < 20
                else ("GENERALIST" if win_rate > 0.5 else "UNSTABLE")
            )

            self._metrics[strategy_id] = m.model_copy(
                update={
                    "signals_generated": new_signals,
                    "valid_signals": new_valid,
                    "open_trajectories": 0,
                    "resolved_trajectories": new_resolved,
                    "support_count": new_resolved,
                    "wins": new_wins,
                    "losses": new_losses,
                    "gross_pnl": new_gross,
                    "costs": new_costs,
                    "net_pnl": new_net,
                    "cost_stress_base": cost_base,
                    "cost_stress_1_5x": cost_1_5x,
                    "cost_stress_2_0x": cost_2_0x,
                    "win_rate": win_rate,
                    "profit_factor": pf,
                    "expectancy": expectancy,
                    "holding_time_seconds": holding_time_sec,
                    "regime": regime,
                    "regime_classification": regime_class,
                    "data_freshness_sec": freshness_sec,
                    "sample_status": sample_status,
                    "status": status,
                }
            )
            self.save_state(new_closed_traj=open_traj)

    def get_leaderboard(self, include_native: bool = False) -> list[ShadowMetrics]:
        """Return shadow metrics sorted by net PnL, optionally including native candidates."""
        candidates = [m for m in self._metrics.values() if include_native or not m.is_native]
        return sorted(candidates, key=lambda m: m.net_pnl, reverse=True)


__all__ = ["ShadowMetrics", "ShadowTournamentEngine", "ShadowTrajectory"]
