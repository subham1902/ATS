"""Offline, source-audited M1 OHLC proxy research; never imports a broker SDK.

Run in the isolated reports/risk-research environment. Source datasets are read only.
This is a research variant, not terminal tick or order-engine parity certification.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "risk-research"
DATA = ROOT.parent / "ATS trade data"
SOURCE = Path(os.environ["ATS_GOLD_TRIPLE_SOURCE"])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rma(values, period):
    result = np.full(len(values), np.nan)
    if len(values) >= period:
        result[period - 1] = np.mean(values[:period])
        for i in range(period, len(values)):
            result[i] = (result[i - 1] * (period - 1) + values[i]) / period
    return result


def aggregate(frame, seconds, full=False):
    bars = frame.resample(f"{seconds}s").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        count=("close", "count"),
    )
    bars = bars[bars["count"] > 0]
    if full:
        bars = bars[bars["count"] == seconds // 60]
    tr = np.maximum(
        bars.high - bars.low,
        np.maximum(abs(bars.high - bars.close.shift()), abs(bars.low - bars.close.shift())),
    )
    tr.iloc[0] = bars.high.iloc[0] - bars.low.iloc[0]
    bars["tr"] = tr
    bars["atr"] = rma(tr.to_numpy(), 14)
    bars["end"] = bars.index + pd.Timedelta(seconds=seconds)
    return bars


def load():
    frames, hashes = [], {}
    for side in ("bid", "ask"):
        path = DATA / f"xauusd-m1-{side}-source-rechecked.csv"
        hashes[side] = digest(path)
        f = pd.read_csv(path)
        f.index = pd.DatetimeIndex(pd.to_datetime(f.pop("timestamp"), utc=True))
        if f.index.has_duplicates or not f.index.is_monotonic_increasing:
            raise ValueError("Duplicate or unordered data")
        prices = f[["open", "high", "low", "close"]]
        if not np.isfinite(prices).all().all() or (prices <= 0).any().any():
            raise ValueError("Invalid price")
        if (f.high < prices.max(axis=1)).any() or (f.low > prices.min(axis=1)).any():
            raise ValueError("Invalid OHLC")
        if (f.volume < 0).any() or not np.isfinite(f.volume).all():
            raise ValueError("Invalid source volume")
        frames.append(f)
    b, a = frames
    if not b.index.equals(a.index):
        raise ValueError("Unpaired quotes")
    crossed = {k: int((a[k] < b[k]).sum()) for k in ("open", "high", "low", "close")}
    if any(crossed.values()):
        raise ValueError(f"Crossed fields: {crossed}")
    quality = dict(
        hashes=hashes,
        rows=len(b),
        start=str(b.index[0]),
        end=str(b.index[-1]),
        crossed=crossed,
        gaps_over_one_minute=int((b.index.to_series().diff() > pd.Timedelta(minutes=1)).sum()),
        volume_provenance="UNKNOWN_SOURCE_VOLUME; S2 CONDITIONAL",
        timezone="EXPLICIT_UTC",
        source_files=[str(DATA / f"xauusd-m1-{s}-source-rechecked.csv") for s in ("bid", "ask")],
    )
    return b, a, quality


def signals(b):
    n = len(b)
    sig = np.zeros((n, 3, 5))  # side, atr, low, high, breakout level
    updates = np.full((n, 5), np.nan)  # h1close,h4high,atr,channel,close
    h1, f4 = aggregate(b, 3600), aggregate(b, 14400)
    h2, m = aggregate(b, 3600, True), aggregate(b, 900, True)
    h3 = aggregate(b, 14400, True)

    def at(time, max_delay=0):
        i = int(b.index.searchsorted(time))
        return i if i < n and 0 <= (b.index[i] - time).total_seconds() <= max_delay else -1

    for row in h1.itertuples():
        i = at(row.end)
        if i >= 0:
            updates[i, 0] = row.close
    atr64 = rma(h1.tr.to_numpy(), 64)
    fa = f4.close.to_numpy()
    ha = h1[["high", "low", "close", "atr", "tr", "count"]].to_numpy()
    for j in range(64, len(h1)):
        row = h1.iloc[j]
        time = row.end
        i = at(time)
        fi = int(f4.end.searchsorted(time, side="right")) - 1
        if (
            i < 0
            or fi < 12
            or row["count"] != 60
            or f4.iloc[fi]["count"] < 180
            or not 6 <= time.hour < 20
        ):
            continue
        prev, slow = ha[j - 1, 3], atr64[j - 1]
        path = np.abs(np.diff(fa[fi - 12 : fi + 1])).sum()
        mom = fa[fi] - fa[fi - 12]
        if (
            not np.isfinite(slow)
            or prev / slow > 1.15
            or row.tr < 1.1 * prev
            or path <= 0
            or abs(mom) / path < 0.25
            or row.high <= row.low
        ):
            continue
        upper, lower = ha[j - 24 : j, 0].max(), ha[j - 24 : j, 1].min()
        loc = (row.close - row.low) / (row.high - row.low)
        side = (
            1
            if mom > 0 and row.close >= upper and loc >= 0.7
            else (-1 if mom < 0 and row.close <= lower and loc <= 0.3 else 0)
        )
        if side:
            sig[i, 0] = (
                side,
                row.atr,
                ha[j - 5 : j + 1, 1].min(),
                ha[j - 5 : j + 1, 0].max(),
                upper if side == 1 else lower,
            )
    # S2 uses FIRST-TR seeded EMA ATR exactly as its source, unlike S1/S3.
    fast = h2.close.ewm(span=50, adjust=False).mean().to_numpy()
    slow = h2.close.ewm(span=200, adjust=False).mean().to_numpy()
    h_atr = h2.tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    m_atr = m.tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    med = m.volume.rolling(20).median().shift().to_numpy()
    for j in range(20, len(m)):
        row = m.iloc[j]
        time = row.end
        i = at(time)
        context = row.name.floor("h")
        hi = int(h2.end.searchsorted(context)) - 0
        if (
            i < 0
            or time.weekday() >= 5
            or not 750 <= time.hour * 60 + time.minute <= 960
            or hi >= len(h2)
            or h2.end.iloc[hi] != context
            or hi < 199
        ):
            continue
        if (
            (row.name - m.index[j - 4]).total_seconds() != 3600
            or row.high <= row.low
            or row.volume <= 1.2 * med[j]
        ):
            continue
        opening = m.loc[
            (m.index >= time.normalize() + pd.Timedelta(hours=7))
            & (m.index < time.normalize() + pd.Timedelta(hours=8))
        ]
        if len(opening) != 4:
            continue
        upper, lower = opening.high.max(), opening.low.min()
        loc = (row.close - row.low) / (row.high - row.low)
        slope = fast[hi] - fast[hi - 3]
        hc = h2.close.iloc[hi]
        side = (
            1
            if hc > fast[hi] > slow[hi]
            and slope > 0
            and row.close > upper >= m.close.iloc[j - 1]
            and loc >= 0.7
            else (
                -1
                if hc < fast[hi] < slow[hi]
                and slope < 0
                and row.close < lower <= m.close.iloc[j - 1]
                and loc <= 0.3
                else 0
            )
        )
        if side and side * (hc - fast[hi]) / h_atr[hi] > 1:
            sig[i, 1] = (
                side,
                m_atr[j],
                m.low.iloc[j - 4 : j].min(),
                m.high.iloc[j - 4 : j].max(),
                row.close,
            )
    ema = h3.close.ewm(span=30, adjust=False).mean().to_numpy()
    for j in range(len(h3)):
        row = h3.iloc[j]
        i = at(row.end, 5400)
        channel = h3.low.iloc[j - 5 : j].min() if j >= 5 else np.nan
        if i >= 0:
            updates[i, 1:] = row.high, row.atr, channel, row.close
        if (
            i >= 0
            and j >= 40
            and row.close > h3.high.iloc[j - 10 : j].max()
            and row.close > ema[j] > ema[j - 10]
            and row.atr > 0
        ):
            sig[i, 2] = 1, row.atr, 0, 0, row.close
    return sig, updates


@njit
def replay(
    b,
    a,
    seconds,
    days,
    months,
    weekday,
    sig,
    updates,
    capital,
    risk,
    maxrisk,
    target1,
    trigger1,
    rr2,
    trail3,
    cost,
    swap,
    spread_factor,
    mask,
):
    balance = capital
    daybase = capital
    monthbase = capital
    dprofit = 0.0
    mprofit = 0.0
    prevday = -1
    prevmonth = -1
    # side,entry,stop,tp,lots,openidx,initialrisk,highest,trigger,entrycost,level,mfe,mae
    pos = np.zeros((3, 13))
    cooldown = 0
    streak = 0
    trades = np.zeros((np.count_nonzero(sig[:, :, 0]), 12))
    count = 0
    rejected = 0
    ambiguous = 0
    equity = np.zeros(len(b))
    realized = np.zeros(len(b))
    booked_path = np.zeros((len(b), 2))
    for i in range(len(b)):
        mark = balance
        for s in range(3):
            if pos[s, 0]:
                px = b[i - 1, 3] if pos[s, 0] == 1 else a[i - 1, 3]
                mark += pos[s, 0] * (px - pos[s, 1]) * pos[s, 4] * 100
        if months[i] != prevmonth:
            prevmonth = months[i]
            monthbase = mark
            mprofit = 0.0
        if days[i] != prevday:
            prevday = days[i]
            daybase = mark
            dprofit = 0.0
            for s in range(3):
                if pos[s, 0] and swap > 0:
                    charge = swap * pos[s, 4] * (3 if weekday[i] == 3 else 1)
                    balance -= charge
                    dprofit -= charge
                    mprofit -= charge
                    booked_path[i, 0] = min(booked_path[i, 0], dprofit / daybase)
                    booked_path[i, 1] = min(booked_path[i, 1], mprofit / monthbase)
        # Freeze admission at the minute open: intrabar closures cannot fund entries.
        occupied = pos[:, 0].copy()
        admission_balance, admission_day, admission_month = balance, dprofit, mprofit
        reserve = 0.0
        margin = 0.0
        for p in range(3):
            if pos[p, 0]:
                reserve += (
                    max(0.0, pos[p, 0] * (pos[p, 1] - pos[p, 2]) * pos[p, 4] * 100)
                    + cost * pos[p, 4] / 2
                )
                margin += pos[p, 4] * 100 * pos[p, 1] / 9
        for s in range(3):
            side = pos[s, 0]
            if side == 0:
                continue
            entry, stop, tp, lots = pos[s, 1], pos[s, 2], pos[s, 3], pos[s, 4]
            # Exit-price spread stress is conservative for long too: deduct widening.
            extra = (a[i, 0] - b[i, 0]) * (spread_factor - 1) / 2
            op = b[i, 0] - extra if side == 1 else a[i, 0] + extra
            hi = b[i, 1] - extra if side == 1 else a[i, 1] + extra
            lo = b[i, 2] - extra if side == 1 else a[i, 2] + extra
            exitpx = 0.0
            reason = 0
            if s == 0 and pos[s, 8] and i > pos[s, 8]:
                stop = max(stop, entry + 10) if side == 1 else min(stop, entry - 10)
            if s == 2 and np.isfinite(updates[i, 1]) and seconds[i] > seconds[int(pos[s, 5])]:
                pos[s, 7] = max(pos[s, 7], updates[i, 1])
                stop = max(stop, pos[s, 7] - trail3 * updates[i, 2])
                if np.isfinite(updates[i, 3]) and updates[i, 4] < updates[i, 3]:
                    exitpx = op
                    reason = 4
            pos[s, 2] = stop
            if (
                s == 0
                and seconds[i] - seconds[int(pos[s, 5])] >= 21600
                and np.isfinite(updates[i, 0])
                and side * (updates[i, 0] - pos[s, 10]) < 0
            ):
                exitpx = op
                reason = 5
            if s == 1 and (days[i] > days[int(pos[s, 5])] or seconds[i] % 86400 >= 63000):
                exitpx = op
                reason = 6
            if side * (op - stop) <= 0:
                exitpx = op
                reason = 1
            elif tp > 0 and side * (op - tp) >= 0:
                exitpx = tp
                reason = 2
            if exitpx == 0:
                stophit = lo <= stop if side == 1 else hi >= stop
                tphit = tp > 0 and (hi >= tp if side == 1 else lo <= tp)
                if stophit and tphit:
                    ambiguous += 1
                if stophit:
                    exitpx = stop
                    reason = 1
                elif tphit:
                    exitpx = tp
                    reason = 2
            # MFE/MAE use prior observed closes only; no unknown intrabar sequence.
            closepx = b[i, 3] if side == 1 else a[i, 3]
            if exitpx == 0:
                move = side * (closepx - entry) * lots * 100
                pos[s, 11] = max(pos[s, 11], move)
                pos[s, 12] = min(pos[s, 12], move)
                if (
                    s == 0
                    and not pos[s, 8]
                    and (hi - entry if side == 1 else entry - lo) >= trigger1
                ):
                    pos[s, 8] = i
            if exitpx != 0:
                gross = side * (exitpx - entry) * lots * 100
                pnl = gross - cost * lots / 2
                balance += pnl
                dprofit += pnl
                mprofit += pnl
                booked_path[i, 0] = min(booked_path[i, 0], dprofit / daybase)
                booked_path[i, 1] = min(booked_path[i, 1], mprofit / monthbase)
                net = pnl - pos[s, 9]
                trades[count] = np.array(
                    [
                        s + 1,
                        pos[s, 5],
                        i,
                        side,
                        entry,
                        exitpx,
                        lots,
                        net,
                        reason,
                        pos[s, 6],
                        max(pos[s, 11], gross),
                        min(pos[s, 12], gross),
                    ]
                )
                count += 1
                if s == 0:
                    streak = streak + 1 if net < 0 else 0
                    if streak >= 2:
                        cooldown = seconds[i] + 604800
                        streak = 0
                pos[s] = 0
        for s in range(3):
            side, atr, low, high, level = sig[i, s]
            if not mask[s] or side == 0 or occupied[s] or (s == 0 and seconds[i] < cooldown):
                continue
            spread = (a[i, 0] - b[i, 0]) * spread_factor
            entry = (
                a[i, 0] + (spread_factor - 1) * (a[i, 0] - b[i, 0]) / 2
                if side == 1
                else b[i, 0] - (spread_factor - 1) * (a[i, 0] - b[i, 0]) / 2
            )
            if s == 1 and (spread > 1.5 or abs(b[i, 0] - level) > 0.25 * atr):
                rejected += 1
                continue
            if s == 0:
                dist = min(
                    max(2 * atr, (entry - low if side == 1 else high - entry) + 0.25 * atr), 39.78
                )
                if dist <= 0 or dist < 10 * spread or target1 / dist < 1:
                    rejected += 1
                    continue
                tp = entry + side * target1
            elif s == 1:
                dist = max(1.2 * atr, entry - low if side == 1 else high - entry)
                if dist < 3:
                    rejected += 1
                    continue
                tp = entry + side * rr2 * dist
            else:
                dist = 2 * atr
                tp = 0.0
            stop = (
                np.floor((entry - dist) * 100) / 100
                if side == 1
                else np.ceil((entry + dist) * 100) / 100
            )
            dist = side * (entry - stop)
            # Inner caps preserve 0.3% daily / 1% monthly gap/cost buffer.
            budget = min(
                admission_balance * risk,
                admission_balance * maxrisk - reserve,
                0.027 * daybase + admission_day - reserve,
                0.07 * monthbase + admission_month - reserve,
            )
            lots = np.floor(max(0.0, budget) / (dist * 100 + cost) * 100) / 100
            lots = min(
                lots,
                100.0,
                np.floor(max(0.0, admission_balance * 0.8 - margin) / (entry * 100 / 9) * 100)
                / 100,
            )
            if lots < 0.01:
                rejected += 1
                continue
            entrycost = cost * lots / 2
            admission_balance -= entrycost
            admission_day -= entrycost
            admission_month -= entrycost
            reserve += dist * lots * 100 + cost * lots / 2
            margin += lots * 100 * entry / 9
            balance -= entrycost
            dprofit -= entrycost
            mprofit -= entrycost
            booked_path[i, 0] = min(booked_path[i, 0], dprofit / daybase)
            booked_path[i, 1] = min(booked_path[i, 1], mprofit / monthbase)
            pos[s] = np.array(
                [
                    side,
                    entry,
                    stop,
                    tp,
                    lots,
                    i,
                    dist * lots * 100 + cost * lots,
                    entry,
                    0,
                    entrycost,
                    level,
                    0,
                    0,
                ]
            )
            # Protection is active immediately on a new entry, including its first bar.
            extra = (a[i, 0] - b[i, 0]) * (spread_factor - 1) / 2
            hi = b[i, 1] - extra if side == 1 else a[i, 1] + extra
            lo = b[i, 2] - extra if side == 1 else a[i, 2] + extra
            stophit = lo <= stop if side == 1 else hi >= stop
            tphit = tp > 0 and (hi >= tp if side == 1 else lo <= tp)
            if stophit and tphit:
                ambiguous += 1
            if stophit or tphit:
                exitpx = stop if stophit else tp
                gross = side * (exitpx - entry) * lots * 100
                pnl = gross - cost * lots / 2
                balance += pnl
                dprofit += pnl
                mprofit += pnl
                booked_path[i, 0] = min(booked_path[i, 0], dprofit / daybase)
                booked_path[i, 1] = min(booked_path[i, 1], mprofit / monthbase)
                net = pnl - entrycost
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
                        pos[s, 6],
                        max(0.0, gross),
                        min(0.0, gross),
                    ]
                )
                count += 1
                if s == 0:
                    streak = streak + 1 if net < 0 else 0
                    if streak >= 2:
                        cooldown = seconds[i] + 604800
                        streak = 0
                pos[s] = 0
            else:
                closepx = b[i, 3] if side == 1 else a[i, 3]
                move = side * (closepx - entry) * lots * 100
                pos[s, 11] = max(0.0, move)
                pos[s, 12] = min(0.0, move)
                if s == 0 and (hi - entry if side == 1 else entry - lo) >= trigger1:
                    pos[s, 8] = i
        eq = balance
        for s in range(3):
            if pos[s, 0]:
                eq += (
                    pos[s, 0]
                    * ((b[i, 3] if pos[s, 0] == 1 else a[i, 3]) - pos[s, 1])
                    * pos[s, 4]
                    * 100
                )
        equity[i] = eq
        realized[i] = balance
        booked_path[i, 0] = min(booked_path[i, 0], dprofit / daybase)
        booked_path[i, 1] = min(booked_path[i, 1], mprofit / monthbase)
    return trades[:count], equity, realized, rejected, ambiguous, pos, booked_path


def metrics(trades, equity, balance, index, capital, booked_path):
    pnl = trades[:, 7] if len(trades) else np.array([])
    daily = pd.Series(balance, index=index).resample("D").last().dropna()
    monthly = pd.Series(balance, index=index).resample("MS").last().dropna()
    # Account-level booked P&L includes entry fees and modeled financing.
    daypnl = daily.diff()
    daypnl.iloc[0] = daily.iloc[0] - capital
    monpnl = monthly.diff()
    monpnl.iloc[0] = monthly.iloc[0] - capital
    dr = pd.Series(booked_path[:, 0], index=index).resample("D").min().dropna()
    mr = pd.Series(booked_path[:, 1], index=index).resample("MS").min().dropna()
    peak = np.maximum.accumulate(np.maximum(equity, capital))
    return dict(
        trades=len(pnl),
        realized_return_pct=(balance[-1] / capital - 1) * 100,
        equity_return_pct=(equity[-1] / capital - 1) * 100,
        max_drawdown_pct=float(np.max((peak - equity) / peak) * 100),
        win_rate_pct=float((pnl > 0).mean() * 100) if len(pnl) else None,
        profit_factor_ex_financing=float(pnl[pnl > 0].sum() / -pnl[pnl < 0].sum())
        if (pnl < 0).any()
        else None,
        worst_day_pct=float(dr.min() * 100),
        worst_month_pct=float(mr.min() * 100),
        daily_breaches=int((dr < -0.03 - 1e-9).sum()),
        monthly_breaches=int((mr < -0.08 - 1e-9).sum()),
        profitable_months=int((monpnl > 0).sum()),
        months=len(monthly),
        average_winner_capture_close_proxy=float(
            np.mean(
                pnl[(trades[:, 10] > 0) & (pnl > 0)] / trades[(trades[:, 10] > 0) & (pnl > 0), 10]
            )
        )
        if ((trades[:, 10] > 0) & (pnl > 0)).any()
        else None,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b, a, quality = load()
    sig, updates = signals(b)
    quality["source_hashes"] = {p.name: digest(p) for p in SOURCE.glob("*.mq*")}
    quality["engine_hash"] = digest(Path(__file__))
    quality["signals"] = {f"S{s + 1}": int((sig[:, s, 0] != 0).sum()) for s in range(3)}
    (OUT / "quality.json").write_text(json.dumps(quality, indent=2))
    print("QUALITY", json.dumps(quality), flush=True)
    idx = b.index
    seconds = idx.astype("int64").to_numpy() // 10**9
    days = seconds // 86400
    months = (idx.year * 12 + idx.month).to_numpy()
    weekday = idx.dayofweek.to_numpy()
    ba = b[["open", "high", "low", "close"]].to_numpy()
    aa = a[["open", "high", "low", "close"]].to_numpy()
    cuts = [
        idx.searchsorted(pd.Timestamp(t, tz="UTC"))
        for t in ("2024-09-01", "2025-09-01", "2026-03-01", "2026-09-01")
    ]
    cuts[-1] = len(idx)
    configs = []
    for risk, maxrisk, exitstyle in itertools.product(
        (0.0025, 0.005, 0.0075, 0.01), (0.0075, 0.015, 0.02), (0, 1, 2)
    ):
        if maxrisk < risk:
            continue
        params = [(50.0, 30.0, 2.0, 3.0), (40.0, 25.0, 1.5, 2.0), (60.0, 35.0, 2.5, 4.0)][exitstyle]
        configs.append(dict(risk=risk, maxrisk=maxrisk, exitstyle=exitstyle, params=params))
    allrows = []
    selected = []
    for capital in (1000.0, 10000.0, 100000.0):
        for name, mask in (
            ("S1", (1, 0, 0)),
            ("S2", (0, 1, 0)),
            ("S3", (0, 0, 1)),
            ("PORTFOLIO", (1, 1, 1)),
        ):
            train = []
            for ci, cfg in enumerate(configs):
                lo, hi = cuts[0], cuts[1]
                t, e, r, reject, amb, p, booked = replay(
                    ba[lo:hi],
                    aa[lo:hi],
                    seconds[lo:hi],
                    days[lo:hi],
                    months[lo:hi],
                    weekday[lo:hi],
                    sig[lo:hi],
                    updates[lo:hi],
                    capital,
                    cfg["risk"],
                    cfg["maxrisk"],
                    *cfg["params"],
                    22.0,
                    15.0,
                    1.0,
                    np.array(mask),
                )
                met = metrics(t, e, r, idx[lo:hi], capital, booked)
                row = dict(
                    account=capital,
                    strategy=name,
                    config=ci,
                    split="TRAIN",
                    cost="BASE",
                    **cfg,
                    **met,
                )
                allrows.append(row)
                train.append(row)
            feasible = [
                r
                for r in train
                if not r["daily_breaches"] and not r["monthly_breaches"] and r["trades"] >= 10
            ]
            finalists = sorted(
                feasible,
                key=lambda r: r["equity_return_pct"] - 1.5 * r["max_drawdown_pct"],
                reverse=True,
            )[:5]
            validation = []
            for row in finalists:
                cfg = configs[row["config"]]
                lo, hi = cuts[1], cuts[2]
                t, e, r, rej, amb, p, booked = replay(
                    ba[lo:hi],
                    aa[lo:hi],
                    seconds[lo:hi],
                    days[lo:hi],
                    months[lo:hi],
                    weekday[lo:hi],
                    sig[lo:hi],
                    updates[lo:hi],
                    capital,
                    cfg["risk"],
                    cfg["maxrisk"],
                    *cfg["params"],
                    22.0,
                    15.0,
                    1.0,
                    np.array(mask),
                )
                met = metrics(t, e, r, idx[lo:hi], capital, booked)
                vr = dict(
                    account=capital,
                    strategy=name,
                    config=row["config"],
                    split="VALIDATION",
                    cost="BASE",
                    **cfg,
                    **met,
                )
                allrows.append(vr)
                if not met["daily_breaches"] and not met["monthly_breaches"] and met["trades"] >= 3:
                    validation.append(vr)
            if not validation:
                selected.append(
                    dict(account=capital, strategy=name, status="NO_ELIGIBLE_CONFIGURATION")
                )
                continue
            best = max(
                validation, key=lambda r: r["equity_return_pct"] - 1.5 * r["max_drawdown_pct"]
            )
            cfg = configs[best["config"]]
            for split, lo, hi in (("TEST", cuts[2], cuts[3]), ("FULL", 0, len(idx))):
                for stress, cost, swap, spread in (
                    ("BASE", 22.0, 15.0, 1.0),
                    ("STRESS", 44.0, 30.0, 1.5),
                ):
                    t, e, r, rej, amb, p, booked = replay(
                        ba[lo:hi],
                        aa[lo:hi],
                        seconds[lo:hi],
                        days[lo:hi],
                        months[lo:hi],
                        weekday[lo:hi],
                        sig[lo:hi],
                        updates[lo:hi],
                        capital,
                        cfg["risk"],
                        cfg["maxrisk"],
                        *cfg["params"],
                        cost,
                        swap,
                        spread,
                        np.array(mask),
                    )
                    met = metrics(t, e, r, idx[lo:hi], capital, booked)
                    sr = dict(
                        account=capital,
                        strategy=name,
                        config=best["config"],
                        split=split,
                        cost=stress,
                        **cfg,
                        **met,
                        rejected=rej,
                        ambiguous_stop_target=amb,
                        open_positions=int((p[:, 0] != 0).sum()),
                    )
                    allrows.append(sr)
                    selected.append(sr)
                    ledger = pd.DataFrame(
                        t,
                        columns=[
                            "strategy",
                            "entry_idx",
                            "exit_idx",
                            "side",
                            "entry",
                            "exit",
                            "lots",
                            "net_ex_financing",
                            "reason",
                            "initial_risk",
                            "observed_close_mfe",
                            "observed_close_mae",
                        ],
                    )
                    if len(ledger):
                        ledger["entry_time"] = [str(idx[lo + int(j)]) for j in ledger.entry_idx]
                        ledger["exit_time"] = [str(idx[lo + int(j)]) for j in ledger.exit_idx]
                    prefix = f"{int(capital)}-{name}-{split}-{stress}"
                    ledger.to_csv(OUT / f"{prefix}-trades.csv", index=False)
                    pd.DataFrame({"equity": e, "balance": r}, index=idx[lo:hi]).resample(
                        "D"
                    ).last().dropna().to_csv(OUT / f"{prefix}-daily.csv")
            print("DONE", capital, name, flush=True)
    pd.DataFrame(allrows).to_csv(OUT / "search.csv", index=False)
    (OUT / "selected.json").write_text(json.dumps(selected, indent=2))
    print("COMPLETE", flush=True)


if __name__ == "__main__":
    main()
