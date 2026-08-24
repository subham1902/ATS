"""Deterministic indicator implementations using stdlib only.

Exact formulas (documented):

- SMA(series, window): sum(window)/window
- EMA(series, window): alpha=2/(window+1), seed SMA of first window, then
  Wilder-style recursive: EMA_t = alpha*price_t + (1-alpha)*EMA_{t-1}
  computed over the available history up to evaluation_index. Returns EMA_t.
- ATR(high, low, close, window): TR_t = max(high-low, abs(high-close_{t-1}), abs(low-close_{t-1}))
  first TR = high-low. ATR = Wilder smoothing: seed SMA of first window TRs,
  then ATR_t = (ATR_{t-1}*(window-1)+TR_t)/window.
- ROC(series, window): (value_t / value_{t-window} -1)*100.
  window >=1. Denominator 0 -> DivisionByZero.
- RSI(series, window): Wilder RSI. Gains/losses over window, seed SMA, then
  iterative smoothing. RS = avg_gain/avg_loss. RSI = 100 - 100/(1+RS).
  avg_loss==0 => 100, avg_gain==0 => 0.
- VWAP(price, volume, window): sum(price_i*volume_i)/sum(volume_i)
- ZSCORE(series, window): (value_t - SMA)/std_population. std==0 => DivisionByZero.
- SLOPE(series, window): OLS slope of y=series window vs x=0..window-1.
  slope = cov(x,y)/var(x). var==0 => error.
- PERCENTILE(series, window, p): p-th percentile (0..100) of window values
  linear interpolation between closest ranks. p outside [0,100] => InvalidPercentile.
- ROLLING_STD(series, window): population std dev (ddof=0) over window.
- ROLLING_CORR(a, b, window): Pearson correlation over window, population.
  If std zero => DivisionByZero / InsufficientWarmup.

All handle temporal safety via context; windows bounded and finite.
"""

from __future__ import annotations

import math
from decimal import Decimal

from .context import FormulaEvaluationContext
from .errors import (
    DivisionByZeroError,
    InsufficientWarmupError,
    InvalidPercentileError,
    InvalidWindowError,
)


def _finite(v: float) -> float:
    if not math.isfinite(v):
        from .errors import NumericSafetyError

        raise NumericSafetyError("non-finite intermediate")
    return v


def sma(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    vals = ctx.get_window(feature, window)
    return _finite(sum(vals) / window)


def ema(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("window must be >0")
    seq = ctx.series.get(feature)
    if seq is None:
        from .errors import UnknownFeatureError

        raise UnknownFeatureError(feature)
    if ctx.evaluation_index + 1 < window:
        raise InsufficientWarmupError("EMA insufficient warmup")
    # Convert to floats deterministically
    floats: list[float] = []
    for v in seq[: ctx.evaluation_index + 1]:
        if isinstance(v, Decimal):
            floats.append(float(v))
        elif isinstance(v, int) and not isinstance(v, bool):
            floats.append(float(v))
        elif isinstance(v, float):
            if not math.isfinite(v):
                from .errors import NumericSafetyError

                raise NumericSafetyError("non-finite in EMA series")
            floats.append(v)
        else:
            from .errors import TypeError_

            raise TypeError_(f"non-numeric in EMA: {v!r}")
    alpha = 2.0 / (window + 1)
    # seed
    seed = sum(floats[0:window]) / window
    _finite(seed)
    ema_val = seed
    for i in range(window, len(floats)):
        ema_val = alpha * floats[i] + (1 - alpha) * ema_val
        _finite(ema_val)
    return ema_val


def atr(ctx: FormulaEvaluationContext, high: str, low: str, close: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("window must be >0")
    if ctx.evaluation_index + 1 < window:
        raise InsufficientWarmupError("ATR warmup")
    # Need windows for high/low/close up to evaluation_index
    # Compute TR series up to evaluation_index inclusive
    high_seq = ctx.series.get(high)
    low_seq = ctx.series.get(low)
    close_seq = ctx.series.get(close)
    if high_seq is None or low_seq is None or close_seq is None:
        from .errors import UnknownFeatureError

        raise UnknownFeatureError("ATR missing series")

    # Convert to floats with bounds
    def to_floats(seq: object) -> list[float]:
        lst: list[float] = []
        assert isinstance(seq, list | tuple)
        sliced = list(seq)[: ctx.evaluation_index + 1]
        for v in sliced:
            if isinstance(v, Decimal):
                lst.append(float(v))
            elif isinstance(v, int) and not isinstance(v, bool):
                lst.append(float(v))
            elif isinstance(v, float):
                if not math.isfinite(v):
                    from .errors import NumericSafetyError

                    raise NumericSafetyError("non-finite")
                lst.append(v)
            else:
                from .errors import TypeError_

                raise TypeError_(f"non-numeric ATR: {v!r}")
        return lst

    h = to_floats(high_seq)
    lo = to_floats(low_seq)
    c = to_floats(close_seq)
    n = len(h)
    trs: list[float] = []
    for i in range(n):
        if i == 0:
            tr = h[i] - lo[i]
        else:
            tr = max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1]))
        _finite(tr)
        if tr < 0:
            # high < low is invalid data; treat as error
            from .errors import NumericSafetyError

            raise NumericSafetyError("negative TR")
        trs.append(tr)
    seed = sum(trs[0:window]) / window
    _finite(seed)
    atr_val = seed
    for i in range(window, len(trs)):
        atr_val = (atr_val * (window - 1) + trs[i]) / window
        _finite(atr_val)
    return atr_val


def roc(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("ROC window must be >0")
    if ctx.evaluation_index - window < 0:
        raise InsufficientWarmupError("ROC warmup")
    cur = ctx.get_window(feature, 1)[0]
    # get value window bars ago
    seq = ctx.series[feature]
    past_raw = seq[ctx.evaluation_index - window]
    if isinstance(past_raw, Decimal):
        past_f: float = float(past_raw)
    elif isinstance(past_raw, int) and not isinstance(past_raw, bool):
        past_f = float(past_raw)
    elif isinstance(past_raw, float):
        past_f = past_raw
    else:
        from .errors import TypeError_

        raise TypeError_(f"non-numeric ROC: {past_raw!r}")
    if not math.isfinite(past_f):
        from .errors import NumericSafetyError

        raise NumericSafetyError("non-finite")
    if past_f == 0.0:
        raise DivisionByZeroError("ROC denominator zero")
    val = (cur / past_f - 1.0) * 100.0
    return _finite(val)


def rsi(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("RSI window must be >0")
    if ctx.evaluation_index + 1 < window + 1:
        raise InsufficientWarmupError("RSI warmup")
    ctx.get_window(
        feature, window + 1
    )  # need window deltas, but we want full history up to index for smoothing
    # Actually need full series up to evaluation_index for Wilder smoothing
    seq = ctx.series[feature]
    floats: list[float] = []
    seq_list = list(seq)[: ctx.evaluation_index + 1]
    for v in seq_list:
        if isinstance(v, Decimal):
            floats.append(float(v))
        elif isinstance(v, int) and not isinstance(v, bool):
            floats.append(float(v))
        elif isinstance(v, float):
            if not math.isfinite(v):
                from .errors import NumericSafetyError

                raise NumericSafetyError("non-finite")
            floats.append(v)
        else:
            from .errors import TypeError_

            raise TypeError_(f"non-numeric RSI: {v!r}")
    # compute gains/losses
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(floats)):
        delta = floats[i] - floats[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    # seed
    avg_gain = sum(gains[0:window]) / window
    avg_loss = sum(losses[0:window]) / window
    _finite(avg_gain)
    _finite(avg_loss)
    # Wilder smoothing for remaining
    for i in range(window, len(gains)):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window
        _finite(avg_gain)
        _finite(avg_loss)
    if avg_loss == 0.0:
        return 100.0 if avg_gain != 0 else 50.0  # flat => 50; purely gains => 100
    if avg_gain == 0.0:
        return 0.0
    rs = avg_gain / avg_loss
    rsi_val = 100.0 - (100.0 / (1.0 + rs))
    return _finite(rsi_val)


def vwap(ctx: FormulaEvaluationContext, price: str, volume: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("VWAP window must be >0")
    p_vals = ctx.get_window(price, window)
    v_vals = ctx.get_window(volume, window)
    # volume must be non-negative; check
    for vv in v_vals:
        if vv < 0:
            from .errors import NumericSafetyError

            raise NumericSafetyError("negative volume")
    denom = sum(v_vals)
    if denom == 0.0:
        raise DivisionByZeroError("VWAP zero volume sum")
    num = sum(p * v for p, v in zip(p_vals, v_vals, strict=False))
    return _finite(num / denom)


def zscore(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    vals = ctx.get_window(feature, window)
    mean = sum(vals) / window
    var = sum((x - mean) ** 2 for x in vals) / window
    _finite(var)
    if var < 0:
        var = 0.0
    std = math.sqrt(var)
    _finite(std)
    if std == 0.0:
        raise DivisionByZeroError("ZSCORE std zero")
    return _finite((vals[-1] - mean) / std)


def slope(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    vals = ctx.get_window(feature, window)
    n = window
    # x = 0..n-1
    mean_x = (n - 1) / 2.0
    mean_y = sum(vals) / n
    cov = sum((i - mean_x) * (vals[i] - mean_y) for i in range(n))
    var_x = sum((i - mean_x) ** 2 for i in range(n))
    _finite(cov)
    _finite(var_x)
    if var_x == 0.0:
        raise DivisionByZeroError("SLOPE var zero")
    return _finite(cov / var_x)


def percentile(ctx: FormulaEvaluationContext, feature: str, window: int, p: float) -> float:
    if not math.isfinite(p):
        raise InvalidPercentileError("percentile not finite")
    if p < 0.0 or p > 100.0:
        raise InvalidPercentileError(f"percentile {p} out of [0,100]")
    vals = ctx.get_window(feature, window)
    if not vals:
        from .errors import EmptyWindowError

        raise EmptyWindowError("empty window")
    sorted_vals = sorted(vals)
    # linear interpolation
    # rank = p/100 * (n-1)
    n = len(sorted_vals)
    if n == 1:
        return _finite(sorted_vals[0])
    rank = p / 100.0 * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return _finite(sorted_vals[lo])
    frac = rank - lo
    val = sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac
    return _finite(val)


def rolling_std(ctx: FormulaEvaluationContext, feature: str, window: int) -> float:
    vals = ctx.get_window(feature, window)
    mean = sum(vals) / window
    var = sum((x - mean) ** 2 for x in vals) / window
    _finite(var)
    if var < 0:
        var = 0.0
    return _finite(math.sqrt(var))


def rolling_corr(ctx: FormulaEvaluationContext, a: str, b: str, window: int) -> float:
    if window <= 0:
        raise InvalidWindowError("window must be >0")
    av = ctx.get_window(a, window)
    bv = ctx.get_window(b, window)
    mean_a = sum(av) / window
    mean_b = sum(bv) / window
    var_a = sum((x - mean_a) ** 2 for x in av) / window
    var_b = sum((x - mean_b) ** 2 for x in bv) / window
    _finite(var_a)
    _finite(var_b)
    std_a = math.sqrt(var_a) if var_a >= 0 else 0.0
    std_b = math.sqrt(var_b) if var_b >= 0 else 0.0
    _finite(std_a)
    _finite(std_b)
    if std_a == 0.0 or std_b == 0.0:
        raise DivisionByZeroError("corr std zero")
    cov = sum((av[i] - mean_a) * (bv[i] - mean_b) for i in range(window)) / window
    _finite(cov)
    corr = cov / (std_a * std_b)
    # clamp due to floating error
    corr = max(-1.0, min(1.0, corr))
    return _finite(corr)


__all__ = [
    "atr",
    "ema",
    "percentile",
    "roc",
    "rolling_corr",
    "rolling_std",
    "rsi",
    "slope",
    "sma",
    "vwap",
    "zscore",
]
