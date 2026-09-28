"""Historical validation of every agent mandate before it touches capital.

This turns the ten strategies from *plausible hypotheses* into *evidence-backed
candidates*. Per mandate it answers: does this strategy have positive net
expectancy on real historical data, after costs and realistic execution?

Anti-overfit rules:
  * Chronological split: 70% in-sample, 30% out-of-sample. Only OOS evidence
    may seed the live edge registry.
  * No look-ahead: signals are computed from completed bars only.
  * Costs are mandatory: statutory-equivalent cost plus adverse slippage.
  * Abstention is free and not penalised.

Data note: the repo's ``mcx_gold_15min_normalized_research.parquet`` is a 16-byte
empty file and is rejected outright rather than silently used. The real series
is the 1-minute XAU/USD CSV in ``ATS trade data/``.

Usage:
    python -m scripts.validate_strategies
    python -m scripts.validate_strategies --limit 150000 --oos 0.3
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ats.agents.execution import ExecutionConfig, ExecutionModel
from ats.agents.features import Bar, TickAggregator, atr_geometry
from ats.agents.portfolio import MANDATES

#: Real historical data, searched relative to CWD and the repository root.
DATA_CANDIDATES = (
    Path("ATS trade data/xauusd-m1-ask-source-rechecked.csv"),
    Path("../ATS trade data/xauusd-m1-ask-source-rechecked.csv"),
    Path("../../ATS trade data/xauusd-m1-ask-source-rechecked.csv"),
)
DEFAULT_DATA = DATA_CANDIDATES[0]


def resolve_data_path(explicit: Path | None = None) -> Path:
    """Locate the historical CSV without depending on the working directory."""
    if explicit is not None:
        return explicit
    for candidate in DATA_CANDIDATES:
        if candidate.exists():
            return candidate
    return DEFAULT_DATA

#: XAU/USD spot cost model, expressed in price points per round trip.
XAU_SPREAD_POINTS = 0.35
XAU_COMMISSION_POINTS = 0.15
XAU_ROUND_TRIP_POINTS = XAU_SPREAD_POINTS + XAU_COMMISSION_POINTS

#: Edge-to-cost multiple required, matching the live default.
MIN_EDGE_MULTIPLE = 3.0

#: Minimum trades before a strategy may be declared deployable.
MIN_DEPLOY_TRADES = 100

#: Profit factor floor for graduation.
MIN_PROFIT_FACTOR = 1.15


@dataclass
class ValidationResult:
    """Validation outcome for one mandate over one data segment."""

    agent: str
    family: str
    signal_source: str
    bar_seconds: float = 300.0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    abstentions: int = 0
    gross_points: float = 0.0
    cost_points: float = 0.0
    net_points: float = 0.0
    win_points: float = 0.0
    loss_points: float = 0.0
    max_drawdown: float = 0.0
    bars_held_total: int = 0
    exit_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return 100.0 * self.wins / self.trades if self.trades else 0.0

    @property
    def expectancy(self) -> float:
        return self.net_points / self.trades if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        if self.trades == 0:
            return 0.0
        if self.loss_points <= 0:
            return 999.0 if self.win_points > 0 else 0.0
        return self.win_points / self.loss_points

    @property
    def avg_bars_held(self) -> float:
        return self.bars_held_total / self.trades if self.trades else 0.0

    @property
    def verdict(self) -> str:
        if self.trades == 0:
            return "NO_SIGNAL"
        if self.trades < 30:
            return "INSUFFICIENT_SAMPLE"
        if self.expectancy <= 0:
            return "NEGATIVE_EXPECTANCY"
        if self.trades < MIN_DEPLOY_TRADES:
            return "PROMISING"
        if self.profit_factor >= MIN_PROFIT_FACTOR:
            return "GRADUATED"
        return "PROMISING"

    @property
    def deployable(self) -> bool:
        """Only graduated strategies may be pointed at capital."""
        return self.verdict == "GRADUATED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "family": self.family,
            "signal_source": self.signal_source,
            "bar_seconds": self.bar_seconds,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 1),
            "gross_points": round(self.gross_points, 2),
            "cost_points": round(self.cost_points, 2),
            "net_points": round(self.net_points, 2),
            "expectancy": round(self.expectancy, 4),
            "profit_factor": round(self.profit_factor, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "avg_bars_held": round(self.avg_bars_held, 1),
            "abstentions": self.abstentions,
            "exit_reasons": dict(self.exit_reasons),
            "verdict": self.verdict,
            "deployable": self.deployable,
        }


def parse_epoch(text: str) -> float:
    """Parse an ISO-8601 UTC timestamp to epoch seconds."""
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).timestamp()


def load_bars(
    path: Path = DEFAULT_DATA,
    *,
    limit: int | None = None,
    bar_seconds: float = 300.0,
) -> list[Bar]:
    """Load 1-minute CSV rows and re-aggregate into ``bar_seconds`` bars.

    Re-aggregating from the raw 1-minute series lets every mandate be validated
    on its own bar size from one underlying dataset.
    """
    if not path.exists():
        raise FileNotFoundError(f"Historical data not found: {path}")
    size = path.stat().st_size
    if size < 10_000:
        raise ValueError(f"{path} is too small to contain bars ({size} bytes)")

    agg = TickAggregator(interval_seconds=bar_seconds, max_bars=5_000_000)
    seen = 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                agg.update_ohlc(
                    open_=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    timestamp=parse_epoch(row["timestamp"]),
                    volume=float(row.get("volume") or 0.0),
                )
            except (TypeError, ValueError, KeyError):
                continue
            seen += 1
            if limit is not None and seen >= limit:
                break

    agg.flush()
    return agg.closed_bars


def simulate(
    bars: Sequence[Bar],
    *,
    agent: str,
    family: str,
    signal_source: str,
    atr_multiplier: float,
    risk_reward: float,
    max_hold_bars: int,
    min_confidence: float = 0.45,
    seed: int = 7,
) -> ValidationResult:
    """Walk a mandate through history, paying cost and slippage on every trade."""
    from ats.agents.strategies import evaluate_strategy

    exec_model = ExecutionModel(ExecutionConfig(reject_probability=0.0, seed=seed))
    res = ValidationResult(agent=agent, family=family, signal_source=signal_source)

    pending: dict[str, Any] | None = None
    held = 0
    equity = 0.0
    peak = 0.0

    # Only the most recent lookback can affect any indicator, so keep a bounded
    # rolling window. Slicing the full history per bar would be O(n^2) and turns
    # a 700k-bar validation into an unrunnable job.
    window_max = 260

    for i in range(12, len(bars)):
        # ---- manage an open position ------------------------------------
        if pending is not None:
            bar = bars[i]
            held += 1
            reason = ""
            raw = bar.close
            d = pending["direction"]
            if d == "LONG":
                if bar.high >= pending["target"]:
                    reason, raw = "PROFIT_TARGET", pending["target"]
                elif bar.low <= pending["stop"]:
                    reason, raw = "STOP_LOSS", pending["stop"]
            else:
                if bar.low <= pending["target"]:
                    reason, raw = "PROFIT_TARGET", pending["target"]
                elif bar.high >= pending["stop"]:
                    reason, raw = "STOP_LOSS", pending["stop"]
            if not reason and held >= max_hold_bars:
                reason = "TIME_EXIT"

            if reason:
                fill = exec_model.apply_exit(
                    price=raw, direction=d, order_id=f"{agent}-{i}", reason=reason
                )
                gross = (
                    (fill.price - pending["entry"])
                    if d == "LONG"
                    else (pending["entry"] - fill.price)
                )
                net = gross - XAU_ROUND_TRIP_POINTS
                res.trades += 1
                res.gross_points += gross
                res.cost_points += XAU_ROUND_TRIP_POINTS
                res.net_points += net
                res.bars_held_total += held
                res.exit_reasons[reason] = res.exit_reasons.get(reason, 0) + 1
                if net > 0:
                    res.wins += 1
                    res.win_points += net
                else:
                    res.losses += 1
                    res.loss_points += abs(net)
                equity += net
                peak = max(peak, equity)
                res.max_drawdown = max(res.max_drawdown, peak - equity)
                pending = None
                held = 0
            continue

        # ---- flat: evaluate on completed bars only ----------------------
        window = list(bars[max(0, i - window_max) : i])
        signal = evaluate_strategy(signal_source, window, tick_size=0.01)
        if not signal.has_signal or signal.direction is None:
            res.abstentions += 1
            continue
        if signal.confidence < min_confidence:
            res.abstentions += 1
            continue

        geom = signal.geometry or atr_geometry(
            window,
            atr_multiplier=atr_multiplier,
            risk_reward=risk_reward,
            tick_size=0.01,
        )
        # The same cost gate the live system enforces, in points.
        if geom.target_points <= XAU_ROUND_TRIP_POINTS * MIN_EDGE_MULTIPLE:
            res.abstentions += 1
            continue

        d = signal.direction
        entry_fill = exec_model.apply_entry(
            price=bars[i - 1].close, direction=d, order_id=f"{agent}-{i}-e"
        )
        ep = entry_fill.price
        pending = {
            "direction": d,
            "entry": ep,
            "target": ep + geom.target_points if d == "LONG" else ep - geom.target_points,
            "stop": ep - geom.stop_points if d == "LONG" else ep + geom.stop_points,
        }
        held = 0

    return res


def _mandate_params(horizon: str) -> dict[str, Any]:
    """Swing mandates carry wider stops and longer holds, matching the live config."""
    if horizon == "LONG_TERM_SWING":
        return {
            "atr_multiplier": 2.0,
            "risk_reward": 2.5,
            "max_hold_bars": 192,
        }
    return {"atr_multiplier": 1.5, "risk_reward": 2.0, "max_hold_bars": 48}


def run_validation(
    *,
    path: Path = DEFAULT_DATA,
    limit: int | None = None,
    oos_fraction: float = 0.30,
    data_split: str = "HISTORICAL_OOS",
) -> dict[str, Any]:
    """Validate every mandate with a chronological IS/OOS split.

    Returns a report dictionary. Only the out-of-sample segment is treated as
    admissible evidence for deployment.
    """
    is_results: dict[str, ValidationResult] = {}
    oos_results: dict[str, ValidationResult] = {}

    for mandate in MANDATES:
        bars = load_bars(path, limit=limit, bar_seconds=mandate.bar_seconds)
        params = _mandate_params(mandate.horizon)

        if len(bars) < 120:
            blank = ValidationResult(
                agent=mandate.agent,
                family=mandate.family,
                signal_source=mandate.signal_source,
                bar_seconds=mandate.bar_seconds,
            )
            is_results[mandate.agent] = blank
            oos_results[mandate.agent] = blank
            continue

        split = int(len(bars) * (1.0 - oos_fraction))

        common = {
            "agent": mandate.agent,
            "family": mandate.family,
            "signal_source": mandate.signal_source,
            **params,
        }
        is_results[mandate.agent] = simulate(bars=bars[:split], seed=7, **common)
        oos_res = simulate(bars=bars[split:], seed=11, **common)
        oos_res.bar_seconds = mandate.bar_seconds
        oos_results[mandate.agent] = oos_res

    verdicts = {
        agent: oos_results[agent].as_dict() for agent in oos_results
    }
    deployable = sorted(a for a, v in verdicts.items() if v["deployable"])

    return {
        "data_source": str(path),
        "data_split": data_split,
        "oos_fraction": oos_fraction,
        "round_trip_cost_points": XAU_ROUND_TRIP_POINTS,
        "min_edge_multiple": MIN_EDGE_MULTIPLE,
        "min_deploy_trades": MIN_DEPLOY_TRADES,
        "is": {a: r.as_dict() for a, r in is_results.items()},
        "oos": verdicts,
        "deployable": deployable,
        "not_deployable": sorted(set(verdicts) - set(deployable)),
    }


def print_report(report: dict[str, Any]) -> None:
    print("=" * 118)
    print("ATS AGENTS PLAYGROUND - HISTORICAL STRATEGY VALIDATION")
    print("=" * 118)
    print(f"Data          : {report['data_source']}")
    print(f"Split         : {report['data_split']} "
          f"(IS {1 - report['oos_fraction']:.0%} / OOS {report['oos_fraction']:.0%})")
    print(f"Round-trip cost: {report['round_trip_cost_points']} points "
          f"(spread+commission) + modelled slippage")
    print(f"Deploy rule   : >= {report['min_deploy_trades']} OOS trades, "
          f"positive expectancy, profit factor >= {MIN_PROFIT_FACTOR}")

    for label, key in (("IN-SAMPLE", "is"), ("OUT-OF-SAMPLE (deployable evidence)", "oos")):
        print()
        print(f"--- {label} ---")
        header = (
            f"{'Agent':8s} {'Family':15s} {'Trades':>7s} {'Win%':>6s} {'Gross':>10s} "
            f"{'Cost':>9s} {'Net':>10s} {'Expct':>8s} {'PF':>6s} {'MaxDD':>9s} "
            f"{'Abstain':>8s} {'Verdict':20s}"
        )
        print(header)
        print("-" * len(header))
        for agent, r in sorted(
            report[key].items(), key=lambda kv: kv[1]["net_points"], reverse=True
        ):
            print(
                f"{agent:8s} {r['family'][:14]:15s} {r['trades']:7d} {r['win_rate']:6.1f} "
                f"{r['gross_points']:10,.1f} {r['cost_points']:9,.1f} {r['net_points']:10,.1f} "
                f"{r['expectancy']:8.3f} {r['profit_factor']:6.2f} {r['max_drawdown']:9,.1f} "
                f"{r['abstentions']:8d} {r['verdict']:20s}"
            )

    print()
    print("=" * 118)
    print("DEPLOYMENT DECISION (based on out-of-sample evidence only)")
    print("=" * 118)
    if report["deployable"]:
        print("Graduated (may trade): " + ", ".join(report["deployable"]))
    else:
        print("Graduated: NONE - no mandate cleared the deployment bar.")
    print("Held back          : " + (", ".join(report["not_deployable"]) or "none"))
    print()
    print("Interpretation:")
    print("  * A mandate that is NO_SIGNAL simply never fired on this data; that is")
    print("    safe behaviour, not a defect - but it is also not evidence of edge.")
    print("  * A mandate that abstained heavily is being filtered by its own cost gate,")
    print("    which is the system working as designed.")
    print("  * Positive in-sample but negative out-of-sample is overfitting. Such a")
    print("    mandate is explicitly NOT deployable.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate every agent mandate on history")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Max 1-minute rows to read")
    parser.add_argument("--oos", type=float, default=0.30)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    report = run_validation(
        path=resolve_data_path(args.data), limit=args.limit, oos_fraction=args.oos
    )
    print_report(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.json_out}")


if __name__ == "__main__":
    main()
