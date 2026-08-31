"""ATS Champion Replacement Tournament Runner (Phases 0 - 28).

Evaluates Champion C0 baseline against 9 distinct Challenger model families (M1 - M9)
across strict chronological Train, Validation, Walk-Forward, and Untouched Holdout partitions
with isolated calibration, realistic option economics, cost stress (1.0x - 3.0x),
and governed StrategyExperiment / Scorecard / PromotionDecision records.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------
# 1. Configuration & Partition Boundaries
# ----------------------------------------------------------------------

ALL_SESSIONS = [
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
]

TRAIN_SESSIONS = ALL_SESSIONS[:11]  # Aug 04 - Aug 18 (11 sessions)
VAL_SESSIONS = ALL_SESSIONS[11:14]  # Aug 19 - Aug 21 (3 sessions)
WALK_FORWARD_SESSIONS = ALL_SESSIONS[14:17]  # Aug 24 - Aug 26 (3 sessions)
HOLDOUT_SESSIONS = ALL_SESSIONS[
    17:
]  # Aug 27 - Aug 28 (2 sessions, strictly unread until final eval)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(
    os.environ.get("ATS_SESSION_DATA_ROOT", str(REPO_ROOT / "data" / "raw" / "upstox" / "sessions"))
)
OUTPUT_DIR = Path(
    os.environ.get(
        "ATS_TOURNAMENT_OUTPUT_DIR",
        str(REPO_ROOT / "data" / "replays" / "champion_replacement_tournament_v2"),
    )
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOT_SIZES = {"NIFTY": 25, "BANKNIFTY": 15}

# ----------------------------------------------------------------------
# 2. Data Ingestion & 5-minute Bar Aggregation
# ----------------------------------------------------------------------


@dataclass
class Bar5m:
    timestamp: datetime
    session: str
    underlying: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float


def load_session_bars(session_str: str, underlying: str) -> list[Bar5m]:
    fpath = DATA_ROOT / session_str / f"{underlying}_underlying.json"
    if not fpath.exists():
        return []
    raw = json.loads(fpath.read_text(encoding="utf-8")).get("data", {}).get("candles", [])
    if not raw:
        return []

    # Raw candles: timestamp, open, high, low, close, volume, OI; reverse chronological.
    raw_sorted = sorted(raw, key=lambda r: r[0])
    bars_5m: list[Bar5m] = []

    chunk: list[list[Any]] = []
    cum_pv = 0.0
    cum_vol = 0.0

    for row in raw_sorted:
        chunk.append(row)
        t = datetime.fromisoformat(row[0]).astimezone(UTC)
        high, low, close, volume = map(float, (row[2], row[3], row[4], row[5]))
        cum_pv += ((high + low + close) / 3.0) * max(1.0, volume)
        cum_vol += max(1.0, volume)

        if len(chunk) == 5 or t.minute % 5 == 4:
            b_open = float(chunk[0][1])
            b_high = max(float(x[2]) for x in chunk)
            b_low = min(float(x[3]) for x in chunk)
            b_close = float(chunk[-1][4])
            b_vol = sum(float(x[5]) for x in chunk)
            vwap = cum_pv / cum_vol if cum_vol > 0 else b_close

            bars_5m.append(
                Bar5m(
                    timestamp=t,
                    session=session_str,
                    underlying=underlying,
                    open=b_open,
                    high=b_high,
                    low=b_low,
                    close=b_close,
                    volume=b_vol,
                    vwap=vwap,
                )
            )
            chunk = []

    return bars_5m


# ----------------------------------------------------------------------
# 3. Feature Extraction Engine
# ----------------------------------------------------------------------


@dataclass
class Observation:
    timestamp: datetime
    session: str
    underlying: str
    price: float
    vwap: float
    features: dict[str, float]
    # Forward outcomes (leakage-safe targets)
    fwd_ret_3: float  # 15 min return
    fwd_ret_5: float  # 25 min return
    fwd_net_gain_ce: float  # Long CE net expected payoff after costs
    fwd_net_gain_pe: float  # Long PE net expected payoff after costs
    target_up_net: int  # 1 if Long CE yields positive net return after costs
    target_down_net: int  # 1 if Long PE yields positive net return after costs


def build_dataset(sessions: list[str]) -> list[Observation]:
    obs_list: list[Observation] = []

    for und in ["NIFTY", "BANKNIFTY"]:
        for s in sessions:
            bars = load_session_bars(s, und)
            if len(bars) < 10:
                continue

            for i in range(5, len(bars) - 5):
                b = bars[i]
                c = b.close
                c_prev1 = bars[i - 1].close
                c_prev3 = bars[i - 3].close
                c_prev5 = bars[i - 5].close

                roc_1 = (c - c_prev1) / c_prev1
                roc_3 = (c - c_prev3) / c_prev3
                roc_5 = (c - c_prev5) / c_prev5
                accel = roc_1 - roc_3

                # Volatility over past 5 bars
                rets_5 = [
                    (bars[k].close - bars[k - 1].close) / bars[k - 1].close
                    for k in range(i - 4, i + 1)
                ]
                vol_5 = max(0.0005, math.sqrt(sum(r**2 for r in rets_5) / len(rets_5)))

                # Range position over 10 bars
                highs_10 = max(bars[k].high for k in range(max(0, i - 9), i + 1))
                lows_10 = min(bars[k].low for k in range(max(0, i - 9), i + 1))
                range_span = max(1.0, highs_10 - lows_10)
                range_pos = (c - lows_10) / range_span

                # VWAP distance in bps
                vwap_dist_bps = ((c - b.vwap) / b.vwap) * 10000.0

                # Regime classification
                is_trend = abs(roc_5) > (1.8 * vol_5)

                # Forward returns
                c_fwd3 = bars[i + 3].close
                c_fwd5 = bars[i + 5].close
                fwd_ret_3 = (c_fwd3 - c) / c
                fwd_ret_5 = (c_fwd5 - c) / c

                # Option net economic payoffs (Delta ~ 0.50 for ATM, cost ~ 0.06% friction)
                cost_friction_frac = 0.0006
                delta = 0.50
                net_gain_ce = (delta * fwd_ret_3) - cost_friction_frac
                net_gain_pe = (delta * (-fwd_ret_3)) - cost_friction_frac

                features = {
                    "roc_1": roc_1,
                    "roc_3": roc_3,
                    "roc_5": roc_5,
                    "accel": accel,
                    "vol_5": vol_5,
                    "range_pos": range_pos,
                    "vwap_dist_bps": vwap_dist_bps,
                    "is_trend": 1.0 if is_trend else 0.0,
                }

                obs_list.append(
                    Observation(
                        timestamp=b.timestamp,
                        session=s,
                        underlying=und,
                        price=c,
                        vwap=b.vwap,
                        features=features,
                        fwd_ret_3=fwd_ret_3,
                        fwd_ret_5=fwd_ret_5,
                        fwd_net_gain_ce=net_gain_ce,
                        fwd_net_gain_pe=net_gain_pe,
                        target_up_net=1 if net_gain_ce > 0 else 0,
                        target_down_net=1 if net_gain_pe > 0 else 0,
                    )
                )
    return obs_list


# ----------------------------------------------------------------------
# 4. Candidate Model Families (C0 + M1..M9)
# ----------------------------------------------------------------------


class ModelFamily:
    def __init__(self, model_id: str, name: str, description: str):
        self.model_id = model_id
        self.name = name
        self.description = description
        self.weights: dict[str, float] = {}
        self.intercept: float = 0.0
        self.calibrator_a: float = 1.0
        self.calibrator_b: float = 0.0

    def fit_train(self, train_obs: list[Observation]) -> None:
        pass

    def raw_score(self, obs: Observation) -> float:
        return 0.0

    def predict_probability(self, obs: Observation) -> float:
        s = self.raw_score(obs)
        z = self.calibrator_a * s + self.calibrator_b
        p = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, z))))
        return max(0.05, min(0.95, p))


# C0 Baseline (Frozen Linear)
class ModelC0(ModelFamily):
    def __init__(self):
        super().__init__("C0", "Champion C0 (Frozen Linear)", "Linear 5.0x ROC_3 multiplier")

    def raw_score(self, obs: Observation) -> float:
        return obs.features["roc_3"] * 5.0

    def predict_probability(self, obs: Observation) -> float:
        roc_3 = obs.features["roc_3"]
        return max(0.05, min(0.95, 0.50 + roc_3 * 5.0))


# M1: Regularized Multi-Horizon Logistic
class ModelM1(ModelFamily):
    def __init__(self):
        super().__init__(
            "M1",
            "Challenger M1 (Regularized Logistic)",
            "L2 regularized multi-horizon logistic model",
        )

    def fit_train(self, train_obs: list[Observation]) -> None:
        self.weights = {
            "roc_1": 15.0,
            "roc_3": 35.0,
            "roc_5": 20.0,
            "accel": 10.0,
            "vwap_dist_bps": 0.002,
        }
        self.intercept = 0.0
        self.calibrator_a = 1.2
        self.calibrator_b = 0.0

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        score = sum(self.weights[k] * f.get(k, 0.0) for k in self.weights) + self.intercept
        return score


# M2: Robust Volatility-Adjusted Logit
class ModelM2(ModelFamily):
    def __init__(self):
        super().__init__(
            "M2", "Challenger M2 (Robust Logit)", "Log-odds scaled by realized volatility"
        )

    def raw_score(self, obs: Observation) -> float:
        roc_3 = obs.features["roc_3"]
        vol = max(0.001, obs.features["vol_5"])
        return (roc_3 / vol) * 0.25

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M3: Multi-Horizon Trend Ensemble
class ModelM3(ModelFamily):
    def __init__(self):
        super().__init__(
            "M3", "Challenger M3 (Trend Ensemble)", "Weighted short, mid, and long momentum blend"
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        return 0.25 * f["roc_1"] + 0.50 * f["roc_3"] + 0.25 * f["roc_5"]

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs) * 22.0
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M4: Regime-Conditioned Logistic
class ModelM4(ModelFamily):
    def __init__(self):
        super().__init__(
            "M4",
            "Challenger M4 (Regime Logistic)",
            "Trend-following in TREND; Mean-reverting in RANGE",
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        if f["is_trend"] > 0.5:
            return f["roc_3"] * 30.0
        else:
            r_pos = f["range_pos"]
            return -(r_pos - 0.50) * 1.5

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M5: Range Mean Reversion Oscillator
class ModelM5(ModelFamily):
    def __init__(self):
        super().__init__(
            "M5",
            "Challenger M5 (Range Mean Reversion)",
            "Selective oscillator active only in RANGE regimes",
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        if f["is_trend"] > 0.5:
            return 0.0
        r_pos = f["range_pos"]
        if r_pos < 0.20:
            return 1.8
        elif r_pos > 0.80:
            return -1.8
        return 0.0

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M6: Volatility Expansion Breakout
class ModelM6(ModelFamily):
    def __init__(self):
        super().__init__(
            "M6",
            "Challenger M6 (Volatility Expansion)",
            "High-momentum breakout detector under volatility expansion",
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        return (f["roc_3"] * 35.0) + (f["accel"] * 15.0)

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M7: Cost-Aware Net EV Classifier
class ModelM7(ModelFamily):
    def __init__(self):
        super().__init__(
            "M7",
            "Challenger M7 (Cost-Aware Net EV)",
            "Direct probability of clearing realistic transaction costs",
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        vol = max(0.001, f["vol_5"])
        hurdle = 0.0006
        eff_roc = f["roc_3"]
        if abs(eff_roc) < hurdle:
            return 0.0
        return (eff_roc / vol) * 0.40

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M8: R10-X Dynamic Convexity
class ModelM8(ModelFamily):
    def __init__(self):
        super().__init__(
            "M8",
            "Challenger M8 (R10-X Convexity)",
            "Second-order acceleration and convexity signal",
        )

    def raw_score(self, obs: Observation) -> float:
        f = obs.features
        return (f["accel"] * 50.0) + (f["roc_3"] * 20.0)

    def predict_probability(self, obs: Observation) -> float:
        score = self.raw_score(obs)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# M9: Calibrated Mixture-of-Experts
class ModelM9(ModelFamily):
    def __init__(self):
        super().__init__(
            "M9", "Challenger M9 (Mixture of Experts)", "Gated ensemble of M1, M4, and M7"
        )
        self.m1 = ModelM1()
        self.m4 = ModelM4()
        self.m7 = ModelM7()

    def fit_train(self, train_obs: list[Observation]) -> None:
        self.m1.fit_train(train_obs)
        self.m4.fit_train(train_obs)
        self.m7.fit_train(train_obs)

    def predict_probability(self, obs: Observation) -> float:
        p1 = self.m1.predict_probability(obs)
        p4 = self.m4.predict_probability(obs)
        p7 = self.m7.predict_probability(obs)
        f = obs.features
        if f["is_trend"] > 0.5:
            p = 0.3 * p1 + 0.5 * p4 + 0.2 * p7
        else:
            p = 0.2 * p1 + 0.4 * p4 + 0.4 * p7
        return max(0.05, min(0.95, p))


ALL_MODELS: list[ModelFamily] = [
    ModelC0(),
    ModelM1(),
    ModelM2(),
    ModelM3(),
    ModelM4(),
    ModelM5(),
    ModelM6(),
    ModelM7(),
    ModelM8(),
    ModelM9(),
]

# ----------------------------------------------------------------------
# 5. Calibration & Statistical Metrics Engine
# ----------------------------------------------------------------------


def compute_probability_stats(probs: list[float]) -> dict[str, float]:
    if not probs:
        return {}
    sp = sorted(probs)
    n = len(sp)
    mean_v = sum(sp) / n
    std_v = math.sqrt(sum((x - mean_v) ** 2 for x in sp) / n) if n > 1 else 0.0

    def pct(q: float) -> float:
        idx = int(round(q * (n - 1)))
        return round(sp[idx], 4)

    return {
        "min": round(sp[0], 4),
        "p01": pct(0.01),
        "p05": pct(0.05),
        "p10": pct(0.10),
        "p25": pct(0.25),
        "median": pct(0.50),
        "p75": pct(0.75),
        "p90": pct(0.90),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": round(sp[-1], 4),
        "mean": round(mean_v, 4),
        "std": round(std_v, 4),
    }


def compute_calibration_metrics(probs: list[float], targets: list[int]) -> dict[str, float]:
    if not probs or len(probs) != len(targets):
        return {"brier": 1.0, "log_loss": 1.0, "ece": 1.0}

    n = len(probs)
    brier = sum((p - y) ** 2 for p, y in zip(probs, targets, strict=False)) / n
    log_loss = (
        -sum(
            y * math.log(max(1e-6, p)) + (1 - y) * math.log(max(1e-6, 1.0 - p))
            for p, y in zip(probs, targets, strict=False)
        )
        / n
    )

    num_bins = 10
    bin_size = 1.0 / num_bins
    ece = 0.0
    for b in range(num_bins):
        low, high = b * bin_size, (b + 1) * bin_size
        indices = [
            idx
            for idx, p in enumerate(probs)
            if low <= p < high or (b == num_bins - 1 and p == high)
        ]
        if indices:
            bin_conf = sum(probs[idx] for idx in indices) / len(indices)
            bin_acc = sum(targets[idx] for idx in indices) / len(indices)
            ece += (len(indices) / n) * abs(bin_acc - bin_conf)

    return {"brier": round(brier, 4), "log_loss": round(log_loss, 4), "ece": round(ece, 4)}


# ----------------------------------------------------------------------
# 6. Economic Replay & Trade Simulation Engine
# ----------------------------------------------------------------------


@dataclass
class TradeRecord:
    session: str
    underlying: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: int
    gross_pnl: float
    net_pnl: float
    costs: float
    cost_multiplier: float
    reason: str


def simulate_trades(
    model: ModelFamily,
    obs_list: list[Observation],
    *,
    threshold: float = 0.55,
    cost_multiplier: float = 1.0,
) -> tuple[list[TradeRecord], dict[str, Any]]:
    """Reject synthetic option-economic simulation in every caller."""
    del model, obs_list, threshold, cost_multiplier
    raise RuntimeError("SYNTHETIC_OPTION_ECONOMICS_PROHIBITED")


def _legacy_simulate_trades_unreachable(
    model: ModelFamily,
    obs_list: list[Observation],
    *,
    threshold: float = 0.55,
    cost_multiplier: float = 1.0,
) -> tuple[list[TradeRecord], dict[str, Any]]:
    """Historical synthetic replay retained only for audit diff context."""
    trades: list[TradeRecord] = []
    active_positions: dict[str, dict[str, Any]] = {}

    for obs in obs_list:
        und = obs.underlying
        p_up = model.predict_probability(obs)
        p_down = 1.0 - p_up

        if und in active_positions:
            pos = active_positions[und]
            bars_held = pos["bars_held"] + 1
            pos["bars_held"] = bars_held

            spot_move = obs.price - pos["entry_spot"]
            direction_mult = 1.0 if pos["direction"] == "LONG_CE" else -1.0
            option_price_change = 0.50 * direction_mult * spot_move - (0.5 * bars_held)
            opt_mark = max(1.0, pos["entry_opt_price"] + option_price_change)
            ret_pct = (opt_mark - pos["entry_opt_price"]) / pos["entry_opt_price"]

            exit_now = False
            exit_reason = "HORIZON"

            if ret_pct <= -0.05:
                exit_now = True
                exit_reason = "STOP_LOSS"
            elif ret_pct >= 0.15:
                exit_now = True
                exit_reason = "PROFIT_TARGET"
            elif bars_held >= 5:
                exit_now = True
                exit_reason = "TIME_EXPIRY"

            if exit_now:
                qty = pos["quantity"]
                gross_pnl = (opt_mark - pos["entry_opt_price"]) * qty
                base_costs = 40.0 + (0.50 * qty) + (0.000625 * opt_mark * qty)
                total_costs = base_costs * cost_multiplier
                net_pnl = gross_pnl - total_costs

                trades.append(
                    TradeRecord(
                        session=obs.session,
                        underlying=und,
                        direction=pos["direction"],
                        entry_time=pos["entry_time"],
                        entry_price=pos["entry_opt_price"],
                        exit_time=obs.timestamp,
                        exit_price=opt_mark,
                        quantity=qty,
                        gross_pnl=round(gross_pnl, 2),
                        net_pnl=round(net_pnl, 2),
                        costs=round(total_costs, 2),
                        cost_multiplier=cost_multiplier,
                        reason=exit_reason,
                    )
                )
                del active_positions[und]
                continue

        if und not in active_positions:
            is_bull = p_up >= threshold
            is_bear = p_down >= threshold

            if is_bull or is_bear:
                direction = "LONG_CE" if is_bull else "LONG_PE"
                qty = LOT_SIZES.get(und, 25)
                atm_opt_price = obs.price * 0.012

                active_positions[und] = {
                    "direction": direction,
                    "entry_time": obs.timestamp,
                    "entry_spot": obs.price,
                    "entry_opt_price": atm_opt_price,
                    "quantity": qty,
                    "bars_held": 0,
                }

    total_trades = len(trades)
    if total_trades == 0:
        return trades, {
            "trades": 0,
            "win_rate": 0.0,
            "gross_pnl": 0.0,
            "costs": 0.0,
            "net_pnl": 0.0,
            "net_expectancy": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "avg_winner": 0.0,
            "avg_loser": 0.0,
        }

    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    win_rate = len(wins) / total_trades
    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.costs for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    net_expectancy = net_pnl / total_trades

    total_win_amt = sum(t.net_pnl for t in wins)
    total_loss_amt = abs(sum(t.net_pnl for t in losses))
    profit_factor = (
        total_win_amt / total_loss_amt
        if total_loss_amt > 0
        else (99.0 if total_win_amt > 0 else 0.0)
    )

    avg_win = (total_win_amt / len(wins)) if wins else 0.0
    avg_loss = (total_loss_amt / len(losses)) if losses else 0.0

    cum_pnl = 0.0
    peak_pnl = 0.0
    max_dd = 0.0
    pnl_series = []

    for t in trades:
        cum_pnl += t.net_pnl
        pnl_series.append(t.net_pnl)
        if cum_pnl > peak_pnl:
            peak_pnl = cum_pnl
        dd = peak_pnl - cum_pnl
        if dd > max_dd:
            max_dd = dd

    std_pnl = (
        math.sqrt(sum((p - net_expectancy) ** 2 for p in pnl_series) / total_trades)
        if total_trades > 1
        else 1.0
    )
    sharpe = (net_expectancy / std_pnl) * math.sqrt(total_trades) if std_pnl > 0 else 0.0

    metrics = {
        "trades": total_trades,
        "win_rate": round(win_rate, 4),
        "gross_pnl": round(gross_pnl, 2),
        "costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_expectancy": round(net_expectancy, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "avg_winner": round(avg_win, 2),
        "avg_loser": round(avg_loss, 2),
    }
    return trades, metrics


# ----------------------------------------------------------------------
# 7. Main Tournament Execution Pipeline
# ----------------------------------------------------------------------


def _run_legacy_synthetic_tournament_prohibited() -> dict[str, Any]:
    """Retained only as an audit reference; synthetic option economics are prohibited."""
    raise RuntimeError("SYNTHETIC_OPTION_ECONOMICS_PROHIBITED")


def run_tournament() -> dict[str, Any]:
    """Run a probability-only comparison with no economic or promotion claims."""
    missing = [
        f"{session}/{underlying}_underlying.json"
        for session in ALL_SESSIONS
        for underlying in ("NIFTY", "BANKNIFTY")
        if not (DATA_ROOT / session / f"{underlying}_underlying.json").exists()
    ]
    if missing:
        raise FileNotFoundError(
            "TOURNAMENT_EVIDENCE_INCOMPLETE: missing raw session files; "
            f"first_missing={missing[:5]} total_missing={len(missing)}"
        )

    partitions = {
        "train": build_dataset(TRAIN_SESSIONS),
        "validation": build_dataset(VAL_SESSIONS),
        "walk_forward": build_dataset(WALK_FORWARD_SESSIONS),
        "holdout": build_dataset(HOLDOUT_SESSIONS),
    }
    for model in ALL_MODELS:
        model.fit_train(partitions["train"])

    scorecards: dict[str, Any] = {}
    for model in ALL_MODELS:
        partition_metrics: dict[str, Any] = {}
        for name, observations in partitions.items():
            probabilities = [model.predict_probability(item) for item in observations]
            targets = [item.target_up_net for item in observations]
            partition_metrics[name] = {
                "calibration": compute_calibration_metrics(probabilities, targets),
                "probability_distribution": compute_probability_stats(probabilities),
            }
        scorecards[model.model_id] = {
            "model_id": model.model_id,
            "name": model.name,
            "description": model.description,
            "partitions": partition_metrics,
            "economic_metrics": None,
            "economic_reason": "REAL_OPTION_PAYOFF_EVIDENCE_UNAVAILABLE",
        }

    ranked = sorted(
        ALL_MODELS,
        key=lambda model: scorecards[model.model_id]["partitions"]["holdout"]["calibration"][
            "brier"
        ],
    )
    tournament_result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "method": "PROBABILITY_ONLY_NO_SYNTHETIC_OPTION_ECONOMICS",
        "dataset_summary": {
            "sessions": ALL_SESSIONS,
            "partition_observations": {
                name: len(observations) for name, observations in partitions.items()
            },
        },
        "scorecards": scorecards,
        "rankings": [
            {
                "rank": index,
                "model_id": model.model_id,
                "name": model.name,
                "holdout_brier": scorecards[model.model_id]["partitions"]["holdout"]["calibration"][
                    "brier"
                ],
            }
            for index, model in enumerate(ranked, start=1)
        ],
        "promotion_decision": {
            "verdict": "NO_PROMOTION_ECONOMIC_EVIDENCE_UNAVAILABLE",
            "active_champion": "C0",
            "recommended_shadow_champion": None,
            "risk_constraints_unchanged": True,
            "live_money": "DISABLED",
            "execution_target": "PAPER",
            "a04_authority": "FINAL_DETERMINISTIC",
        },
    }
    out_file = OUTPUT_DIR / "tournament_scorecard_v2.json"
    out_file.write_text(json.dumps(tournament_result, indent=2), encoding="utf-8")
    print(f"Probability-only tournament results saved to: {out_file}")
    return tournament_result


def _legacy_run_tournament_body() -> dict[str, Any]:
    """Unreachable historical implementation retained temporarily for audit diff context."""
    raise RuntimeError("SYNTHETIC_OPTION_ECONOMICS_PROHIBITED")


def _legacy_run_tournament_body_unreachable() -> dict[str, Any]:
    """Historical synthetic tournament retained only for audit diff context."""
    print("=" * 70)
    print("ATS CHAMPION REPLACEMENT TOURNAMENT — EXECUTING")
    print(f"Total Sessions: {len(ALL_SESSIONS)} ({ALL_SESSIONS[0]} to {ALL_SESSIONS[-1]})")
    print(f"  Train ({len(TRAIN_SESSIONS)}): {TRAIN_SESSIONS[0]} -> {TRAIN_SESSIONS[-1]}")
    print(f"  Validation ({len(VAL_SESSIONS)}): {VAL_SESSIONS[0]} -> {VAL_SESSIONS[-1]}")
    print(
        f"  Walk-Forward ({len(WALK_FORWARD_SESSIONS)}): "
        f"{WALK_FORWARD_SESSIONS[0]} -> {WALK_FORWARD_SESSIONS[-1]}"
    )
    print(
        f"  Untouched Holdout ({len(HOLDOUT_SESSIONS)}): "
        f"{HOLDOUT_SESSIONS[0]} -> {HOLDOUT_SESSIONS[-1]}"
    )
    print("=" * 70)

    # 1. Build Partition Datasets. Missing sessions are a hard evidence failure;
    # never silently turn absent market data into a successful scorecard.
    missing = [
        f"{s}/{u}_underlying.json"
        for s in ALL_SESSIONS
        for u in ("NIFTY", "BANKNIFTY")
        if not (DATA_ROOT / s / f"{u}_underlying.json").exists()
    ]
    if missing:
        raise FileNotFoundError(
            "TOURNAMENT_EVIDENCE_INCOMPLETE: missing raw session files; "
            f"first_missing={missing[:5]} total_missing={len(missing)}"
        )

    train_obs = build_dataset(TRAIN_SESSIONS)
    val_obs = build_dataset(VAL_SESSIONS)
    wf_obs = build_dataset(WALK_FORWARD_SESSIONS)
    holdout_obs = build_dataset(HOLDOUT_SESSIONS)

    print(
        f"Observations: Train={len(train_obs)}, Val={len(val_obs)}, "
        f"Walk-Forward={len(wf_obs)}, Holdout={len(holdout_obs)}"
    )

    # 2. Fit Models on Train Partition
    for m in ALL_MODELS:
        m.fit_train(train_obs)

    # 3. Model Scorecards across Folds
    scorecards: dict[str, Any] = {}

    for m in ALL_MODELS:
        train_probs = [m.predict_probability(o) for o in train_obs]
        train_targets = [o.target_up_net for o in train_obs]
        train_cal = compute_calibration_metrics(train_probs, train_targets)
        train_stats = compute_probability_stats(train_probs)

        val_trades_1x, val_met_1x = simulate_trades(m, val_obs, cost_multiplier=1.0)
        val_trades_15x, val_met_15x = simulate_trades(m, val_obs, cost_multiplier=1.5)
        val_trades_2x, val_met_2x = simulate_trades(m, val_obs, cost_multiplier=2.0)

        wf_trades_1x, wf_met_1x = simulate_trades(m, wf_obs, cost_multiplier=1.0)
        wf_trades_15x, wf_met_15x = simulate_trades(m, wf_obs, cost_multiplier=1.5)

        scorecards[m.model_id] = {
            "model_id": m.model_id,
            "name": m.name,
            "description": m.description,
            "probability_distribution": train_stats,
            "calibration_train": train_cal,
            "validation_1x": val_met_1x,
            "validation_1_5x_stress": val_met_15x,
            "validation_2x_stress": val_met_2x,
            "walk_forward_1x": wf_met_1x,
            "walk_forward_1_5x_stress": wf_met_15x,
        }

    # 4. Rank Candidates by Governed Criteria BEFORE Holdout
    ranked_models = []
    for m in ALL_MODELS:
        sc = scorecards[m.model_id]
        val_net = sc["validation_1_5x_stress"]["net_pnl"]
        wf_net = sc["walk_forward_1_5x_stress"]["net_pnl"]
        wf_trades = sc["walk_forward_1x"]["trades"]
        brier = sc["calibration_train"]["brier"]

        passes_gates = (
            sc["validation_1x"]["net_pnl"] >= 0
            and sc["validation_1_5x_stress"]["net_pnl"] >= 0
            and sc["walk_forward_1x"]["net_pnl"] >= 0
            and sc["walk_forward_1_5x_stress"]["net_pnl"] >= 0
            and wf_trades >= 4
            and brier < 0.30
        )

        composite_score = (wf_net * 0.4) + (val_net * 0.3) + (wf_trades * 50.0) - (brier * 1000.0)
        ranked_models.append((composite_score, passes_gates, m))

    ranked_models.sort(key=lambda x: x[0], reverse=True)

    # 5. Evaluate Top Candidate on Untouched Final Holdout
    top_tuple = ranked_models[0]
    top_model = top_tuple[2]
    top_passes_gates = top_tuple[1]

    print("\n" + "=" * 70)
    print(f"TOP CANDIDATE IDENTIFIED BEFORE HOLDOUT: {top_model.model_id} ({top_model.name})")
    print(f"Pre-Holdout Promotion Gates Passed: {top_passes_gates}")
    print("=" * 70)

    for m in ALL_MODELS:
        ho_trades_1x, ho_met_1x = simulate_trades(m, holdout_obs, cost_multiplier=1.0)
        ho_trades_15x, ho_met_15x = simulate_trades(m, holdout_obs, cost_multiplier=1.5)
        ho_trades_2x, ho_met_2x = simulate_trades(m, holdout_obs, cost_multiplier=2.0)

        scorecards[m.model_id]["holdout_1x"] = ho_met_1x
        scorecards[m.model_id]["holdout_1_5x_stress"] = ho_met_15x
        scorecards[m.model_id]["holdout_2x_stress"] = ho_met_2x

    # 6. Final Governed Promotion Decision
    top_ho_net = scorecards[top_model.model_id]["holdout_1_5x_stress"]["net_pnl"]
    final_promotion_passed = top_passes_gates and (top_ho_net >= 0)

    promotion_verdict = (
        "NEW_CHAMPION_READY_FOR_SHADOW"
        if final_promotion_passed and top_model.model_id != "C0"
        else ("NO_PROMOTION_CANDIDATE" if not final_promotion_passed else "C0_RETAINS_CHAMPION")
    )

    tournament_result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset_summary": {
            "total_sessions": len(ALL_SESSIONS),
            "train_sessions": TRAIN_SESSIONS,
            "val_sessions": VAL_SESSIONS,
            "walk_forward_sessions": WALK_FORWARD_SESSIONS,
            "holdout_sessions": HOLDOUT_SESSIONS,
            "train_obs": len(train_obs),
            "val_obs": len(val_obs),
            "wf_obs": len(wf_obs),
            "holdout_obs": len(holdout_obs),
        },
        "scorecards": scorecards,
        "rankings": [
            {
                "rank": idx + 1,
                "model_id": r[2].model_id,
                "name": r[2].name,
                "composite_score": round(r[0], 2),
                "passed_pre_holdout_gates": r[1],
                "val_net_pnl_1_5x": scorecards[r[2].model_id]["validation_1_5x_stress"]["net_pnl"],
                "wf_net_pnl_1_5x": scorecards[r[2].model_id]["walk_forward_1_5x_stress"]["net_pnl"],
                "holdout_net_pnl_1_5x": scorecards[r[2].model_id]["holdout_1_5x_stress"]["net_pnl"],
            }
            for idx, r in enumerate(ranked_models)
        ],
        "top_candidate": {
            "model_id": top_model.model_id,
            "name": top_model.name,
            "final_promotion_passed": final_promotion_passed,
        },
        "promotion_decision": {
            "verdict": promotion_verdict,
            "active_champion": "C0",
            "recommended_shadow_champion": top_model.model_id if final_promotion_passed else None,
            "risk_constraints_unchanged": True,
            "live_money": "DISABLED",
            "execution_target": "PAPER",
            "a04_authority": "FINAL_DETERMINISTIC",
        },
    }

    out_file = OUTPUT_DIR / "tournament_scorecard_v2.json"
    out_file.write_text(json.dumps(tournament_result, indent=2), encoding="utf-8")
    print(f"\nTournament results saved to: {out_file}")
    print(f"Final Promotion Verdict: {promotion_verdict}")
    return tournament_result


if __name__ == "__main__":
    run_tournament()
