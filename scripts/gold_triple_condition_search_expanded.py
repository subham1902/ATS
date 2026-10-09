"""Bounded observable-condition search; all output remains historical research."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import gold_triple_risk_research as base
import gold_triple_small_account as small
import numpy as np
import pandas as pd

OUT = small.OUT / "conditions-expanded-risk"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, a, quality = base.load()
    parents, _ = base.signals(b)
    sigs = {}
    updates = {}
    for resolution, look in itertools.product((60, 300), (1, 3)):
        sigs[(resolution, look)], updates[resolution] = small.tactical(b, parents, look, resolution)
    meta = json.loads((small.OUT / "broker-metadata.json").read_text())
    idx = b.index
    t = idx.astype("int64").to_numpy() // 10**9
    price_b = b[["open", "high", "low", "close"]].to_numpy()
    price_a = a[["open", "high", "low", "close"]].to_numpy()
    cuts = (
        [0]
        + [int(idx.searchsorted(pd.Timestamp(s, tz="UTC"))) for s in ("2025-09-01", "2026-03-01")]
        + [len(b)]
    )
    hours = idx.hour.to_numpy()
    weekdays = idx.dayofweek.to_numpy()
    spread = a.open.to_numpy() - b.open.to_numpy()
    filters = {
        "LONDON": (hours >= 7) & (hours < 12),
        "NEW_YORK": (hours >= 12) & (hours < 17),
        "OVERLAP": (hours >= 13) & (hours < 16),
        "TUE_THU": (weekdays >= 1) & (weekdays <= 3),
        "NO_FRIDAY": weekdays < 4,
        "SPREAD_035": spread <= 0.35,
        "SPREAD_060": spread <= 0.60,
        "LONDON_LOW_SPREAD": (hours >= 7) & (hours < 12) & (spread <= 0.60),
        "NY_TUE_THU": (hours >= 12) & (hours < 17) & (weekdays >= 1) & (weekdays <= 3),
    }
    filtered = {
        name: {key: np.where(mask[:, None, None], s, 0.0) for key, s in sigs.items()}
        for name, mask in filters.items()
    }
    previous = pd.read_csv(small.OUT / "search.csv")
    rows = []
    selected = []

    def run(cfg, cap, mask, condition, lo, hi, stress):
        arrays = (
            price_b,
            price_a,
            t,
            t // 86400,
            (idx.year * 12 + idx.month).to_numpy(),
            filtered[condition],
            updates,
            meta,
        )
        return small.evaluate(arrays, cfg, cap, mask, lo, hi, stress)

    for cap in (500.0, 750.0, 1000.0):
        for name, mask in (
            ("S1", (1, 0, 0)),
            ("S2", (0, 1, 0)),
            ("S3", (0, 0, 1)),
            ("PORTFOLIO", (1, 1, 1)),
        ):
            prior = previous[
                (previous.account == cap)
                & (previous.strategy == name)
                & (previous["split"] == "TRAIN")
                & (previous.trades >= 10)
            ].copy()
            prior["score"] = prior.equity_return_pct - 2 * prior.max_drawdown_pct
            shortlist = prior.nlargest(6, "score")
            candidates = []
            expanded = []
            for _, row in shortlist.iterrows():
                for expanded_risk in (0.0125, 0.015, 0.02):
                    clone = row.copy()
                    clone["risk"] = expanded_risk
                    expanded.append(clone)
            for r in expanded:
                cfg = dict(
                    bar_seconds=int(r.bar_seconds),
                    lookback=int(r.lookback),
                    risk=float(r.risk),
                    rr=float(r.rr),
                    protect=bool(r.protect),
                    hold=int(r.hold),
                )
                for condition in filters:
                    base_met, _ = run(cfg, cap, mask, condition, 0, cuts[1], False)
                    stress_met, _ = run(cfg, cap, mask, condition, 0, cuts[1], True)
                    for cost, met in (("BASE", base_met), ("STRESS", stress_met)):
                        rows.append(
                            dict(
                                account=cap,
                                strategy=name,
                                config=int(r.config),
                                condition=condition,
                                split="TRAIN",
                                cost=cost,
                                **cfg,
                                **met,
                            )
                        )
                    if all(
                        m["trades"] >= 10
                        and m["realized_return_pct"] > 0
                        and not m["daily_breach"]
                        and not m["monthly_breach"]
                        for m in (base_met, stress_met)
                    ):
                        candidates.append(
                            dict(
                                cfg=cfg,
                                config=int(r.config),
                                condition=condition,
                                score=min(
                                    m["equity_return_pct"] - 2 * m["max_drawdown_pct"]
                                    for m in (base_met, stress_met)
                                ),
                            )
                        )
            candidates = sorted(candidates, key=lambda r: r["score"], reverse=True)[:5]
            eligible = []
            for candidate in candidates:
                mets = []
                for stress in (False, True):
                    met, _ = run(
                        candidate["cfg"],
                        cap,
                        mask,
                        candidate["condition"],
                        cuts[1],
                        cuts[2],
                        stress,
                    )
                    rows.append(
                        dict(
                            account=cap,
                            strategy=name,
                            config=candidate["config"],
                            condition=candidate["condition"],
                            split="VALIDATION",
                            cost="STRESS" if stress else "BASE",
                            **candidate["cfg"],
                            **met,
                        )
                    )
                    mets.append(met)
                if all(
                    m["trades"] >= 3
                    and m["realized_return_pct"] > 0
                    and not m["daily_breach"]
                    and not m["monthly_breach"]
                    for m in mets
                ):
                    eligible.append(
                        {
                            **candidate,
                            "validation_score": min(
                                m["equity_return_pct"] - 2 * m["max_drawdown_pct"] for m in mets
                            ),
                        }
                    )
            if not eligible:
                selected.append(dict(account=cap, strategy=name, status="NO_ELIGIBLE_CONDITION"))
                print("NONE", cap, name, flush=True)
                continue
            best = max(eligible, key=lambda r: r["validation_score"])
            result = dict(account=cap, strategy=name, **best, results=[])
            for split, lo, hi in (("TEST", cuts[2], cuts[3]), ("FULL", 0, len(idx))):
                for stress in (False, True):
                    met, raw = run(best["cfg"], cap, mask, best["condition"], lo, hi, stress)
                    cost = "STRESS" if stress else "BASE"
                    rows.append(
                        dict(
                            account=cap,
                            strategy=name,
                            config=best["config"],
                            condition=best["condition"],
                            split=split,
                            cost=cost,
                            **best["cfg"],
                            **met,
                        )
                    )
                    result["results"].append(dict(split=split, cost=cost, **met))
                    tr, eq, bal, *_ = raw
                    ledger = pd.DataFrame(
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
                    if len(tr):
                        ledger["entry_time"] = [str(idx[lo + int(j)]) for j in ledger.entry_idx]
                        ledger["exit_time"] = [str(idx[lo + int(j)]) for j in ledger.exit_idx]
                    prefix = f"{int(cap)}-{name}-{split}-{cost}"
                    ledger.to_csv(OUT / f"{prefix}-trades.csv", index=False)
                    pd.DataFrame(dict(equity=eq, balance=bal), index=idx[lo:hi]).resample(
                        "D"
                    ).last().dropna().to_csv(OUT / f"{prefix}-daily.csv")
            later = [m for m in result["results"] if m["split"] == "TEST"]
            result["status"] = (
                "HISTORICAL_FORWARD_CANDIDATE"
                if all(
                    m["trades"] >= 5
                    and m["realized_return_pct"] > 0
                    and not m["daily_breach"]
                    and not m["monthly_breach"]
                    for m in later
                )
                else "NOT_READY"
            )
            selected.append(result)
            print("SELECT", cap, name, result["status"], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "search.csv", index=False)
    (OUT / "selected.json").write_text(json.dumps(selected, indent=2))
    quality.update(
        condition_engine_hash=base.digest(Path(__file__)),
        small_engine_hash=base.digest(Path(small.__file__)),
        filters=list(filters),
        selection="TRAIN+VALIDATION_ONLY; LATER_PERIOD_PREVIOUSLY_EXPOSED",
    )
    (OUT / "quality.json").write_text(json.dumps(quality, indent=2))
    print("COMPLETE", flush=True)


if __name__ == "__main__":
    main()
