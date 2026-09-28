"""Evolutionary parameter search for signal families.

This is the "training" loop: it searches each family's parameter space against
a training split, ranks candidates, then evaluates the survivors on a
held-out split that was never used for selection.

Anti-overfit design
-------------------
* **Train split (60%)** - candidate generation and fitness scoring.
* **Validation split (20%)** - selection pressure and survivor ranking.
* **Test split (20%)** - touched only to report the final, honest number.

A family is only reported as IMPROVED if it wins on the *test* split too. The
whole point of the three-way split is to break the loop where tuning on the same
data it is scored on manufactures fake edge. Any search that does this is just
curve-fitting with extra steps.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ats.agents.families import DIVERSE_FAMILIES

from scripts.validate_strategies import (
    _mandate_params,
    load_bars,
    resolve_data_path,
    simulate,
)

#: Parameters to sweep per family, as ``(name, [candidate values])``.
#: Kept coarse: a fine grid multiplies compute and usually overfits.
PARAM_GRID: dict[str, dict[str, list[Any]]] = {
    "hurst_regime": {
        "q": [3, 5, 8],
        "vr_trend_threshold": [1.05, 1.15, 1.30],
        "vr_reversion_threshold": [0.85, 0.95],
    },
    "moment_skew": {
        "skew_threshold": [0.2, 0.4, 0.8, 1.2],
        "risk_reward": [1.5, 2.0, 3.0],
    },
    "volume_divergence": {
        "min_ratio": [0.5, 0.7, 0.9],
        "lookback": [10, 20, 40],
    },
    "squeeze": {
        "compress_percentile": [0.1, 0.2, 0.3, 0.4],
        "risk_reward": [2.0, 2.5, 3.5],
    },
    "close_location": {
        "run_length": [2, 3, 4, 6],
        "clv_threshold": [0.2, 0.45, 0.7],
    },
    "session_seasonality": {
        "bucket_hours": [1.0, 2.0, 4.0],
        "min_mean_move": [0.0002, 0.0008, 0.002, 0.004],
        "min_samples": [4, 8],
    },
}

#: Minimum trades for a candidate to be considered at all.
MIN_CANDIDATE_TRADES = 25


@dataclass
class Candidate:
    """One parameter combination and its scores across the three splits."""

    family: str
    params: dict[str, Any]
    train_expectancy: float
    train_trades: int
    val_expectancy: float
    val_trades: int
    test_expectancy: float = 0.0
    test_trades: int = 0
    fitness: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "params": self.params,
            "train_expectancy": round(self.train_expectancy, 4),
            "train_trades": self.train_trades,
            "val_expectancy": round(self.val_expectancy, 4),
            "val_trades": self.val_trades,
            "test_expectancy": round(self.test_expectancy, 4),
            "test_trades": self.test_trades,
            "fitness": round(self.fitness, 4),
        }


def _bind_params(fn, params: dict[str, Any]):
    """Return a callable that forces ``params`` regardless of caller kwargs."""
    import functools

    @functools.wraps(fn)
    def wrapper(bars, **kwargs):
        merged = dict(kwargs)
        merged.update(params)
        return fn(bars, **merged)

    return wrapper


def _simulate_raw(bars, family: str, params: dict[str, Any], seed: int):
    """Run the standard simulate() using a temporary bound strategy."""
    from ats.agents.strategies import STRATEGY_REGISTRY, ensure_diverse_families_loaded

    ensure_diverse_families_loaded()
    original = STRATEGY_REGISTRY[family]
    bound = _bind_params(original, params)
    STRATEGY_REGISTRY[family] = bound
    try:
        return simulate(
            bars,
            agent=family,
            family=family,
            signal_source=family,
            **_mandate_params("TACTICAL_INTRADAY"),
            seed=seed,
        )
    finally:
        STRATEGY_REGISTRY[family] = original


def evaluate_family(
    family: str,
    bars,
    train_end: int,
    val_end: int,
    *,
    seed: int = 5,
    top_k: int = 3,
) -> list[Candidate]:
    """Search one family's parameter space and return the best candidates."""
    grid = PARAM_GRID.get(family, {})
    if not grid:
        return []
    keys = list(grid.keys())
    combos = [dict(zip(keys, vals, strict=True)) for vals in itertools.product(*grid.values())]

    train_bars = bars[:train_end]
    val_bars = bars[train_end:val_end]

    candidates: list[Candidate] = []
    for params in combos:
        tr = _simulate_raw(train_bars, family, params, seed)
        if tr.trades < MIN_CANDIDATE_TRADES:
            continue
        va = _simulate_raw(val_bars, family, params, seed + 1)
        # Fitness rewards validation expectancy, penalises over-trading and
        # rewards consistency between train and validation.
        consistency = 1.0 - min(abs(tr.expectancy - va.expectancy), 3.0) / 3.0
        fitness = va.expectancy * 1.0 + 0.3 * consistency - 0.002 * tr.trades / 100
        candidates.append(
            Candidate(
                family=family,
                params=params,
                train_expectancy=tr.expectancy,
                train_trades=tr.trades,
                val_expectancy=va.expectancy,
                val_trades=va.trades,
                fitness=fitness,
            )
        )

    candidates.sort(key=lambda c: c.fitness, reverse=True)
    return candidates[:top_k]


def score_on_test(candidates: list[Candidate], test_bars, *, seed: int = 9) -> None:
    """Score candidates on the held-out test split (in place)."""
    for c in candidates:
        te = _simulate_raw(test_bars, c.family, c.params, seed)
        c.test_expectancy = te.expectancy
        c.test_trades = te.trades


def run(
    *,
    data: Path | None = None,
    limit: int = 250_000,
    bar_seconds: float = 300.0,
    top_k: int = 3,
) -> dict[str, Any]:
    data = resolve_data_path(data)
    bars = load_bars(data, limit=limit, bar_seconds=bar_seconds)
    n = len(bars)
    train_end = int(n * 0.60)
    val_end = int(n * 0.80)
    test_bars = bars[val_end:]

    all_best: dict[str, list[Candidate]] = {}
    for family in DIVERSE_FAMILIES:
        cands = evaluate_family(family, bars, train_end, val_end, top_k=top_k)
        if cands:
            score_on_test(cands, test_bars)
            all_best[family] = cands

    return {
        "data_source": str(data),
        "bars": n,
        "bar_seconds": bar_seconds,
        "split": {"train_end": train_end, "val_end": val_end, "test_start": val_end},
        "results": {f: [c.as_dict() for c in cs] for f, cs in all_best.items()},
    }


def print_report(report: dict[str, Any]) -> None:
    print("=" * 100)
    print("EVOLUTIONARY PARAMETER SEARCH (60/20/20 train/val/test)")
    print("=" * 100)
    print(f"Data: {report['data_source']}  bars={report['bars']}")
    print()
    for family, cands in report["results"].items():
        print(f"--- {family} ---")
        for c in cands:
            improved = "HOLDS" if c["test_expectancy"] > 0 else "FAILS test"
            print(
                f"  train={c['train_expectancy']:+7.3f} val={c['val_expectancy']:+7.3f} "
                f"TEST={c['test_expectancy']:+7.3f} [{improved}]  {c['params']}"
            )
        print()

    survivors = {
        f: c[0]
        for f, c in report["results"].items()
        if c and c[0]["test_expectancy"] > 0 and c[0]["test_trades"] >= MIN_CANDIDATE_TRADES
    }
    print("=" * 100)
    print("FAMILIES WHOSE BEST PARAMS HOLD ON THE HELD-OUT TEST SPLIT")
    print("=" * 100)
    if survivors:
        for f, c in survivors.items():
            print(f"  {f}: {c['params']}  test_expct={c['test_expectancy']:+.3f}")
    else:
        print("  NONE at these default settings. The families are not merely")
        print("  mis-parameterised; on this dataset they have no testable edge.")
        print("  This is the honest outcome, and the gate correctly holds the fleet.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=250_000)
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args()
    report = run(limit=args.limit, top_k=args.top_k)
    print_report(report)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWritten to {args.json_out}")


if __name__ == "__main__":
    main()
