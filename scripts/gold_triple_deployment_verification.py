"""Re-evaluate only selected conditions on the native target grid. No new search."""

from __future__ import annotations

import json
from pathlib import Path

import gold_triple_risk_research as base
import gold_triple_small_account as small
import numpy as np
import pandas as pd


def main():
    source = small.OUT / "conditions-expanded-risk"
    output = small.OUT / "deployment-verification"
    output.mkdir(parents=True, exist_ok=True)
    selection = json.loads((source / "selected.json").read_text())
    selected = [r for r in selection if r["account"] == 1000 and r["strategy"] in {"S2", "S3"}]
    b, a, quality = base.load()
    parents, _ = base.signals(b)
    idx = b.index
    times = idx.astype("int64").to_numpy() // 10**9
    meta = json.loads((small.OUT / "broker-metadata.json").read_text())
    price_b = b[["open", "high", "low", "close"]].to_numpy()
    price_a = a[["open", "high", "low", "close"]].to_numpy()
    later = int(idx.searchsorted(pd.Timestamp("2026-03-01", tz="UTC")))
    result = []
    for selected_run in selected:
        cfg = {**selected_run["cfg"], "snap_target": True}
        tactical, updates = small.tactical(b, parents, cfg["lookback"], cfg["bar_seconds"])
        allowed = (idx.hour >= 12) & (idx.hour < 17)
        if selected_run["condition"] == "NY_TUE_THU":
            allowed &= (idx.dayofweek >= 1) & (idx.dayofweek <= 3)
        elif selected_run["condition"] != "NEW_YORK":
            raise ValueError("UNSUPPORTED_SELECTED_CONDITION")
        tactical = np.where(allowed[:, None, None], tactical, 0.0)
        key = (cfg["bar_seconds"], cfg["lookback"])
        arrays = (
            price_b,
            price_a,
            times,
            times // 86400,
            (idx.year * 12 + idx.month).to_numpy(),
            {key: tactical},
            {cfg["bar_seconds"]: updates},
            meta,
        )
        strategy = selected_run["strategy"]
        mask = (0, 1, 0) if strategy == "S2" else (0, 0, 1)
        current = {
            "account": 1000,
            "strategy": strategy,
            "condition": selected_run["condition"],
            "cfg": cfg,
            "results": [],
        }
        for split, lo in (("TEST", later), ("FULL", 0)):
            for cost, stress in (("BASE", False), ("STRESS", True)):
                metrics, raw = small.evaluate(arrays, cfg, 1000.0, mask, lo, len(b), stress)
                current["results"].append({"split": split, "cost": cost, **metrics})
                tr, equity, balance, *_ = raw
                trades = pd.DataFrame(
                    tr,
                    columns=[
                        "strategy",
                        "entry_idx",
                        "exit_idx",
                        "side",
                        "entry",
                        "exit",
                        "lots",
                        "net",
                        "exit_reason",
                        "initial_risk",
                        "close_mfe_price",
                        "close_mae_price",
                        "ambiguous",
                        "parent_index",
                    ],
                )
                if len(trades):
                    trades["entry_time"] = [str(idx[lo + int(i)]) for i in trades.entry_idx]
                    trades["exit_time"] = [str(idx[lo + int(i)]) for i in trades.exit_idx]
                prefix = f"1000-{strategy}-{split}-{cost}"
                trades.to_csv(output / f"{prefix}-trades.csv", index=False)
                pd.DataFrame({"equity": equity, "balance": balance}, index=idx[lo:]).resample(
                    "D"
                ).last().dropna().to_csv(output / f"{prefix}-daily.csv")
                print(
                    strategy,
                    split,
                    cost,
                    metrics["trades"],
                    metrics["realized_return_pct"],
                    flush=True,
                )
        current["status"] = (
            "HISTORICAL_FORWARD_CANDIDATE"
            if all(
                r["trades"] >= 5
                and r["realized_return_pct"] > 0
                and not r["daily_breach"]
                and not r["monthly_breach"]
                for r in current["results"]
                if r["split"] == "TEST"
            )
            else "NOT_READY"
        )
        result.append(current)
    quality.update(
        method="SELECTED-PRESET-BROKER-TARGET-GRID-V3",
        selection_hash=base.digest(source / "selected.json"),
        verifier_hash=base.digest(Path(__file__)),
        replay_hash=base.digest(Path(small.__file__)),
        parent_hash=base.digest(Path(base.__file__)),
        target_policy="TOWARD_ENTRY_ON_OBSERVED_TICK_GRID",
        pristine_holdout=False,
        physical_native_parity="NOT_ESTABLISHED",
    )
    (output / "quality.json").write_text(json.dumps(quality, indent=2) + "\n")
    (output / "selected.json").write_text(json.dumps(result, indent=2) + "\n")
    print("COMPLETE: selected-condition verification only", flush=True)


if __name__ == "__main__":
    main()
