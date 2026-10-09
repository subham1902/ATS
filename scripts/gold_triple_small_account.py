"""Explicit new intraday versions of the source hypotheses, offline research only.

Source H1/H4/M15 signals are retained; completed M5 retest entries define new stops.
Never truncates a required stop, rounds up volume, or imports an execution SDK.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import gold_triple_risk_research as base
import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "small-account-research"


def tactical(b, parents, lookback, bar_seconds=300):
    """Causal retest on completed M1/M5; never uses entry-minute extrema."""
    m = base.aggregate(b, bar_seconds, True)
    sig = np.zeros((len(b), 3, 5))
    update = np.full((len(b), 4), np.nan)
    dest = b.index.searchsorted(m.end)
    valid = dest < len(b)
    safe = np.minimum(dest, len(b) - 1)
    delays = (b.index[safe] - pd.DatetimeIndex(m.end)).total_seconds()
    valid &= (delays >= 0) & (delays <= 60)
    valid &= np.isfinite(m.atr.to_numpy())
    valid[: max(14, lookback)] = False
    if lookback > 1:
        continuous = (
            m.index.to_series().diff(lookback - 1).dt.total_seconds().to_numpy()
            == (lookback - 1) * bar_seconds
        )
        valid &= continuous
    update[dest[valid]] = m[["high", "low", "close", "atr"]].to_numpy()[valid]
    lower = (m.low.rolling(lookback).min() - 0.1 * m.atr).to_numpy()
    upper = (m.high.rolling(lookback).max() + 0.1 * m.atr).to_numpy()
    end_ns = m.end.astype("int64").to_numpy()
    epoch = b.index.astype("int64").to_numpy()
    for strategy in range(3):
        indices = np.flatnonzero(parents[:, strategy, 0])
        for j, pi in enumerate(indices):
            side, _, _, _, level = parents[pi, strategy]
            start = epoch[pi] + bar_seconds * 10**9
            expiry = epoch[pi] + (7200, 1800, 5400)[strategy] * 10**9
            # A newer parent replaces the old one only when that publication occurs.
            next_parent = epoch[indices[j + 1]] if j + 1 < len(indices) else np.iinfo(np.int64).max
            lo = int(np.searchsorted(end_ns, start))
            hi = int(np.searchsorted(end_ns, min(expiry, next_parent), side="right"))
            for k in range(lo, hi):
                if not valid[k] or epoch[dest[k]] > expiry or epoch[dest[k]] >= next_parent:
                    continue
                row = m.iloc[k]
                reclaim = side * (row.close - level) > 0 and side * (row.close - row.open) > 0
                touch = (
                    row.low <= level + 0.1 * row.atr
                    if side == 1
                    else row.high >= level - 0.1 * row.atr
                )
                if reclaim and touch:
                    sig[dest[k], strategy] = (
                        side,
                        lower[k] if side == 1 else upper[k],
                        row.atr,
                        pi + 1,
                        level,
                    )
    return sig, update


@njit
def replay(
    b,
    a,
    times,
    days,
    months,
    sig,
    updates,
    capital,
    risk,
    rr,
    protect,
    hold_minutes,
    cost,
    spread_factor,
    leverage,
    minlot,
    step,
    contract,
    tick,
    mask,
    snap_target=False,
):
    balance = capital
    daybase = capital
    monthbase = capital
    dp = 0.0
    mp = 0.0
    prevday = -1
    prevmonth = -1
    # Position: strategy,side,entry,stop,target,lots,distance,index,fee,parent,peak,mae
    p = np.zeros(12)
    p[0] = -1
    used = np.zeros(3)
    day_trades = 0
    day_losses = 0
    next_entry = 0
    trades = np.zeros((np.count_nonzero(sig[:, :, 0]), 14))
    count = 0
    eq = np.zeros(len(b))
    bal = np.zeros(len(b))
    booked = np.zeros((len(b), 2))
    reject = np.zeros(6, dtype=np.int64)  # stop/spread,lot,margin,budget,session,used
    peak_account = capital
    max_dd = 0.0
    last_atr = np.nan
    for i in range(len(b)):
        mark = balance
        if p[0] >= 0:
            previous_extra = (a[i - 1, 0] - b[i - 1, 0]) * (spread_factor - 1) / 2
            px = b[i - 1, 3] - previous_extra if p[1] == 1 else a[i - 1, 3] + previous_extra
            mark += p[1] * (px - p[2]) * p[5] * contract
        if days[i] != prevday:
            prevday = days[i]
            daybase = mark
            dp = 0.0
            day_trades = 0
            day_losses = 0
        if months[i] != prevmonth:
            prevmonth = months[i]
            monthbase = mark
            mp = 0.0
        was_flat = p[0] < 0
        if np.isfinite(updates[i, 3]):
            last_atr = updates[i, 3]
        if not was_flat:
            side, entry, stop, tp, lots = p[1], p[2], p[3], p[4], p[5]
            # Protection uses earlier observed minute CLOSE peak, effective now.
            if protect and p[10] >= p[6]:
                lock = entry + side * 0.1 * p[6]
                stop = max(stop, lock) if side == 1 else min(stop, lock)
                if p[10] >= 1.5 * p[6] and np.isfinite(last_atr):
                    trail = entry + side * p[10] - side * 1.5 * last_atr
                    stop = max(stop, trail) if side == 1 else min(stop, trail)
                stop = (
                    np.floor(stop / tick + 1e-9) * tick
                    if side == 1
                    else np.ceil(stop / tick - 1e-9) * tick
                )
                p[3] = stop
            extra = (a[i, 0] - b[i, 0]) * (spread_factor - 1) / 2
            op = b[i, 0] - extra if side == 1 else a[i, 0] + extra
            hi = b[i, 1] - extra if side == 1 else a[i, 1] + extra
            lo = b[i, 2] - extra if side == 1 else a[i, 2] + extra
            close = b[i, 3] - extra if side == 1 else a[i, 3] + extra
            reason = 0
            exitpx = 0.0
            ambiguous = 0
            if side * (op - stop) <= 0:
                exitpx = op
                reason = 1
            elif side * (op - tp) >= 0:
                exitpx = tp
                reason = 2
            elif (
                times[i] - times[int(p[7])] >= hold_minutes * 60
                or days[i] > days[int(p[7])]
                or times[i] % 86400 >= (63000 if p[0] == 1 else 72000)
            ):
                exitpx = op
                reason = 3
            if reason == 0:
                stophit = lo <= stop if side == 1 else hi >= stop
                tphit = hi >= tp if side == 1 else lo <= tp
                ambiguous = int(stophit and tphit)
                if stophit:
                    exitpx = stop
                    reason = 1
                elif tphit:
                    exitpx = tp
                    reason = 2
            if reason:
                gross = side * (exitpx - entry) * lots * contract
                posting = gross - cost * lots / 2
                net = posting - p[8]
                balance += posting
                dp += posting
                mp += posting
                booked[i, 0] = min(0.0, dp / daybase)
                booked[i, 1] = min(0.0, mp / monthbase)
                trades[count] = np.array(
                    [
                        p[0] + 1,
                        p[7],
                        i,
                        side,
                        entry,
                        exitpx,
                        lots,
                        net,
                        reason,
                        p[6] * lots * contract + cost * lots,
                        max(p[10], side * (exitpx - entry)),
                        min(p[11], side * (exitpx - entry)),
                        ambiguous,
                        p[9],
                    ]
                )
                count += 1
                p[0] = -1
                next_entry = times[i] + 900
                if net < 0:
                    day_losses += 1
            else:
                move = side * (close - entry)
                p[10] = max(p[10], move)
                p[11] = min(p[11], move)
        if was_flat and times[i] >= next_entry and day_losses < 2 and day_trades < 3:
            for s in range(3):
                side, structural, atr, parent, level = sig[i, s]
                if not mask[s] or side == 0:
                    continue
                if parent == used[s]:
                    reject[5] += 1
                    continue
                end = 63000 if s == 1 else 72000
                if not 21600 <= times[i] % 86400 < end - 900:
                    reject[4] += 1
                    continue
                spread = (a[i, 0] - b[i, 0]) * spread_factor
                extra = (a[i, 0] - b[i, 0]) * (spread_factor - 1) / 2
                entry = a[i, 0] + extra if side == 1 else b[i, 0] - extra
                stop = (
                    np.floor(structural / tick) * tick
                    if side == 1
                    else np.ceil(structural / tick) * tick
                )
                dist = side * (entry - stop)
                if (
                    dist <= 0
                    or spread > 1.5
                    or dist < 4 * spread
                    or side * (b[i, 0] - level) < -0.25 * atr
                ):
                    reject[0] += 1
                    continue
                budget = min(balance * risk, 0.025 * daybase + dp, 0.06 * monthbase + mp)
                if budget <= 0:
                    reject[3] += 1
                    continue
                lots = np.floor((budget / (dist * contract + cost) + 1e-12) / step) * step
                lots = min(lots, 0.10)
                if lots < minlot - 1e-9:
                    reject[1] += 1
                    continue
                margin = lots * contract * entry / leverage
                if margin > balance * 0.30:
                    reject[2] += 1
                    continue
                fee = cost * lots / 2
                balance -= fee
                dp -= fee
                mp -= fee
                booked[i, 0] = min(booked[i, 0], dp / daybase)
                booked[i, 1] = min(booked[i, 1], mp / monthbase)
                used[s] = parent
                day_trades += 1
                tp = entry + side * rr * dist
                # Frozen V2 research keeps its original target. Deployment
                # verification opts into the broker grid, toward the entry.
                if snap_target:
                    tp = (
                        np.floor(tp / tick + 1e-9) * tick
                        if side == 1
                        else np.ceil(tp / tick - 1e-9) * tick
                    )
                p = np.array([s, side, entry, stop, tp, lots, dist, i, fee, parent, 0.0, 0.0])
                # Entry-minute stops are active. Ambiguous bars use stop first.
                hi = b[i, 1] - extra if side == 1 else a[i, 1] + extra
                lo = b[i, 2] - extra if side == 1 else a[i, 2] + extra
                close = b[i, 3] - extra if side == 1 else a[i, 3] + extra
                stophit = lo <= stop if side == 1 else hi >= stop
                tphit = hi >= tp if side == 1 else lo <= tp
                if stophit or tphit:
                    exitpx = stop if stophit else tp
                    gross = side * (exitpx - entry) * lots * contract
                    posting = gross - fee
                    net = posting - fee
                    balance += posting
                    dp += posting
                    mp += posting
                    booked[i, 0] = min(booked[i, 0], dp / daybase)
                    booked[i, 1] = min(booked[i, 1], mp / monthbase)
                    trades[count] = np.array(
                        [
                            s + 1,
                            i,
                            i,
                            side,
                            entry,
                            exitpx,
                            lots,
                            net,
                            1 if stophit else 2,
                            dist * lots * contract + cost * lots,
                            max(0.0, side * (exitpx - entry)),
                            min(0.0, side * (exitpx - entry)),
                            int(stophit and tphit),
                            parent,
                        ]
                    )
                    count += 1
                    p[0] = -1
                    next_entry = times[i] + 900
                    if net < 0:
                        day_losses += 1
                else:
                    move = side * (close - entry)
                    p[10] = max(0.0, move)
                    p[11] = min(0.0, move)
                break
        mark = balance
        if p[0] >= 0:
            extra = (a[i, 0] - b[i, 0]) * (spread_factor - 1) / 2
            px = b[i, 3] - extra if p[1] == 1 else a[i, 3] + extra
            mark += p[1] * (px - p[2]) * p[5] * contract
        eq[i] = mark
        bal[i] = balance
        peak_account = max(peak_account, mark)
        max_dd = max(max_dd, (peak_account - mark) / peak_account)
        booked[i, 0] = min(booked[i, 0], dp / daybase)
        booked[i, 1] = min(booked[i, 1], mp / monthbase)
    return trades[:count], eq, bal, booked, reject, p, max_dd


def evaluate(arrays, cfg, capital, mask, lo, hi, stress=False):
    b, a, t, days, months, signals, updates, meta = arrays
    results = replay(
        b[lo:hi],
        a[lo:hi],
        t[lo:hi],
        days[lo:hi],
        months[lo:hi],
        signals[(cfg["bar_seconds"], cfg["lookback"])][lo:hi],
        updates[cfg["bar_seconds"]][lo:hi],
        capital,
        cfg["risk"],
        cfg["rr"],
        cfg["protect"],
        cfg["hold"],
        44.0 if stress else 22.0,
        1.5 if stress else 1.0,
        meta["leverage"] / 2 if stress else meta["leverage"],
        meta["volume_min"],
        meta["volume_step"],
        meta["trade_contract_size"],
        meta["trade_tick_size"],
        np.array(mask),
        cfg.get("snap_target", False),
    )
    trades, eq, bal, booked, reject, pos, dd = results
    pnl = trades[:, 7]
    met = dict(
        trades=len(trades),
        realized_return_pct=(bal[-1] / capital - 1) * 100,
        equity_return_pct=(eq[-1] / capital - 1) * 100,
        max_drawdown_pct=dd * 100,
        worst_day_pct=booked[:, 0].min() * 100,
        worst_month_pct=booked[:, 1].min() * 100,
        daily_breach=bool((booked[:, 0] < -0.03 - 1e-9).any()),
        monthly_breach=bool((booked[:, 1] < -0.08 - 1e-9).any()),
        win_rate=float((pnl > 0).mean() * 100) if len(pnl) else None,
        profit_factor=float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum()) if (pnl < 0).any() else None,
        rejected=reject.tolist(),
        open_position=bool(pos[0] >= 0),
    )
    return met, results


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, a, quality = base.load()
    parents, _ = base.signals(b)
    sigs = {}
    updates = {}
    for bar_seconds, look in itertools.product((60, 300), (1, 3)):
        sigs[(bar_seconds, look)], updates[bar_seconds] = tactical(b, parents, look, bar_seconds)
    meta = json.loads((OUT / "broker-metadata.json").read_text())
    quality.update(
        engine_hash=base.digest(Path(__file__)),
        parent_engine_hash=base.digest(Path(base.__file__)),
        broker_metadata_hash=base.digest(OUT / "broker-metadata.json"),
        tactical_signals={
            str(k): [int((sigs[k][:, s, 0] != 0).sum()) for s in range(3)] for k in sigs
        },
        method="SOURCE-HYPOTHESIS-M1-M5-RETEST-INTRADAY-V2",
        source_hashes={p.name: base.digest(p) for p in base.SOURCE.glob("*.mq*")},
        parent_signals=[int((parents[:, s, 0] != 0).sum()) for s in range(3)],
    )
    (OUT / "quality.json").write_text(json.dumps(quality, indent=2))
    idx = b.index
    t = idx.astype("int64").to_numpy() // 10**9
    arrays = (
        b[["open", "high", "low", "close"]].to_numpy(),
        a[["open", "high", "low", "close"]].to_numpy(),
        t,
        t // 86400,
        (idx.year * 12 + idx.month).to_numpy(),
        sigs,
        updates,
        meta,
    )
    cuts = (
        [0]
        + [int(idx.searchsorted(pd.Timestamp(s, tz="UTC"))) for s in ("2025-09-01", "2026-03-01")]
        + [len(b)]
    )
    configs = [
        dict(bar_seconds=bar_seconds, lookback=look, risk=r, rr=rr, protect=pr, hold=h)
        for bar_seconds, look, r, rr, pr, h in itertools.product(
            (60, 300), (1, 3), (0.005, 0.0075, 0.01), (1.5, 2.0, 3.0), (False, True), (120, 240)
        )
    ]
    rows = []
    selections = []
    for capital in (500.0, 750.0, 1000.0):
        for name, mask in (
            ("S1", (1, 0, 0)),
            ("S2", (0, 1, 0)),
            ("S3", (0, 0, 1)),
            ("PORTFOLIO", (1, 1, 1)),
        ):
            training = []
            for ci, cfg in enumerate(configs):
                met, _ = evaluate(arrays, cfg, capital, mask, cuts[0], cuts[1])
                row = dict(
                    account=capital,
                    strategy=name,
                    config=ci,
                    split="TRAIN",
                    cost="BASE",
                    **cfg,
                    **met,
                )
                rows.append(row)
                if (
                    met["trades"] >= 10
                    and not met["daily_breach"]
                    and not met["monthly_breach"]
                    and met["realized_return_pct"] > 0
                ):
                    training.append(row)
            finalists = sorted(
                training,
                key=lambda r: r["equity_return_pct"] - 2 * r["max_drawdown_pct"],
                reverse=True,
            )[:5]
            eligible = []
            for row in finalists:
                ci = row["config"]
                cfg = configs[ci]
                for stress in (False, True):
                    met, _ = evaluate(arrays, cfg, capital, mask, cuts[1], cuts[2], stress)
                    rows.append(
                        dict(
                            account=capital,
                            strategy=name,
                            config=ci,
                            split="VALIDATION",
                            cost="STRESS" if stress else "BASE",
                            **cfg,
                            **met,
                        )
                    )
                    if (
                        stress
                        and met["trades"] >= 3
                        and not met["daily_breach"]
                        and not met["monthly_breach"]
                        and met["realized_return_pct"] > 0
                    ):
                        eligible.append(
                            dict(
                                config=ci,
                                score=met["equity_return_pct"] - 2 * met["max_drawdown_pct"],
                            )
                        )
            if not eligible:
                selections.append(
                    dict(account=capital, strategy=name, status="NO_VALIDATION_ELIGIBLE_CANDIDATE")
                )
                print("NONE", capital, name, flush=True)
                continue
            ci = max(eligible, key=lambda r: r["score"])["config"]
            cfg = configs[ci]
            selected = dict(account=capital, strategy=name, config=ci, **cfg, results=[])
            for split, lo, hi in (("TEST", cuts[2], cuts[3]), ("FULL", 0, len(idx))):
                for stress in (False, True):
                    met, result = evaluate(arrays, cfg, capital, mask, lo, hi, stress)
                    cost = "STRESS" if stress else "BASE"
                    rows.append(
                        dict(
                            account=capital,
                            strategy=name,
                            config=ci,
                            split=split,
                            cost=cost,
                            **cfg,
                            **met,
                        )
                    )
                    selected["results"].append(dict(split=split, cost=cost, **met))
                    tr, eq, bal, _, _, _, _ = result
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
                    prefix = f"{int(capital)}-{name}-{split}-{cost}"
                    ledger.to_csv(OUT / f"{prefix}-trades.csv", index=False)
                    pd.DataFrame(dict(equity=eq, balance=bal), index=idx[lo:hi]).resample(
                        "D"
                    ).last().dropna().to_csv(OUT / f"{prefix}-daily.csv")
            last = next(
                r for r in selected["results"] if r["split"] == "TEST" and r["cost"] == "STRESS"
            )
            selected["status"] = (
                "FORWARD_RESEARCH_CANDIDATE"
                if last["trades"] >= 5
                and last["realized_return_pct"] > 0
                and not last["daily_breach"]
                and not last["monthly_breach"]
                else "FAILED_LATER_PERIOD_ACCEPTANCE"
            )
            selections.append(selected)
            print("SELECTED", capital, name, selected["status"], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "search.csv", index=False)
    (OUT / "selected.json").write_text(json.dumps(selections, indent=2))
    print("COMPLETE", flush=True)


if __name__ == "__main__":
    main()
