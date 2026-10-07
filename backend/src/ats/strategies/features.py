"""Market feature layer: bars, volatility, and structure indicators.

The pre-audit worker computed every "strategy" from a 30-tick deque spanning
roughly 60 seconds of price history, and read no volume, no open interest, and
no volatility measure at all. Strategies named ``S17_OI_VOLUME_MACHINE`` and
``S03_DONCHIAN_ATR`` were labels with no corresponding logic.

This module provides the real primitives those names imply:

* :class:`TickAggregator` - time-bucketed OHLCV bars from raw ticks
* :func:`atr` - Wilder's Average True Range
* :func:`vwap` - volume-weighted average price
* :func:`donchian` - rolling channel highs/lows
* :func:`zscore` - rolling standardisation
* :func:`realized_volatility` and :func:`trend_strength`

All functions are pure and tolerate short inputs by returning ``None`` rather
than raising, so the worker can degrade gracefully while bars are still forming.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Bar:
    """A single OHLCV bar."""

    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    tick_count: int = 0
    open_interest: float | None = None

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    @property
    def true_range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return self.close - self.open

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
            "open_interest": self.open_interest,
        }


class TickAggregator:
    """Aggregate raw ticks into fixed-duration OHLCV bars.

    The trading decision layer reads bars, not ticks. Ticks drive execution only.
    This is the change that stops the system from being noise-stopped by a
    22-point stop on 60 seconds of data.
    """

    def __init__(self, *, interval_seconds: float = 300.0, max_bars: int = 200) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._interval = float(interval_seconds)
        self._max_bars = int(max_bars)
        self._bars: deque[Bar] = deque(maxlen=self._max_bars)
        self._current: Bar | None = None
        self._current_bucket: int | None = None

    @property
    def interval_seconds(self) -> float:
        return self._interval

    @property
    def bars(self) -> list[Bar]:
        """Completed bars plus the in-progress bar, oldest first."""
        out = list(self._bars)
        if self._current is not None:
            out.append(self._current)
        return out

    @property
    def closed_bars(self) -> list[Bar]:
        return list(self._bars)

    @property
    def ready(self) -> bool:
        """True once enough closed bars exist to compute indicators."""
        return len(self._bars) >= 2

    def update(
        self,
        *,
        price: float,
        timestamp: float,
        volume: float = 0.0,
        open_interest: float | None = None,
    ) -> Bar | None:
        """Fold one tick into the aggregator.

        Returns the completed bar if this tick rolled the interval, else ``None``.
        """
        if price <= 0:
            return None

        bucket = int(timestamp // self._interval)
        completed: Bar | None = None

        if self._current is None or bucket != self._current_bucket:
            if self._current is not None:
                self._bars.append(self._current)
                completed = self._current
            self._current = Bar(
                timestamp=bucket * self._interval,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                tick_count=1,
                open_interest=open_interest,
            )
            self._current_bucket = bucket
        else:
            self._current.high = max(self._current.high, price)
            self._current.low = min(self._current.low, price)
            self._current.close = price
            self._current.volume += volume
            self._current.tick_count += 1
            if open_interest is not None:
                self._current.open_interest = open_interest

        return completed

    def update_ohlc(
        self,
        *,
        open_: float,
        high: float,
        low: float,
        close: float,
        timestamp: float,
        volume: float = 0.0,
        open_interest: float | None = None,
    ) -> Bar | None:
        """Fold a full OHLC observation into the aggregator.

        Used when re-aggregating historical bars: a tick only carries a price,
        so feeding ``close`` alone would discard the intra-bar high and low that
        ATR and the exit logic depend on.
        """
        if close <= 0:
            return None

        h = max(float(high), float(open_), close)
        low_ = min(float(low), float(open_), close)

        bucket = int(timestamp // self._interval)
        completed: Bar | None = None

        if self._current is None or bucket != self._current_bucket:
            if self._current is not None:
                self._bars.append(self._current)
                completed = self._current
            self._current = Bar(
                timestamp=bucket * self._interval,
                open=float(open_),
                high=h,
                low=low_,
                close=close,
                volume=volume,
                tick_count=1,
                open_interest=open_interest,
            )
            self._current_bucket = bucket
        else:
            self._current.high = max(self._current.high, h)
            self._current.low = min(self._current.low, low_)
            self._current.close = close
            self._current.volume += volume
            self._current.tick_count += 1
            if open_interest is not None:
                self._current.open_interest = open_interest

        return completed

    def flush(self) -> Bar | None:
        """Close and return the in-progress bar, if any."""
        if self._current is None:
            return None
        bar = self._current
        self._bars.append(bar)
        self._current = None
        self._current_bucket = None
        return bar

    def reset(self) -> None:
        self._bars.clear()
        self._current = None
        self._current_bucket = None


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def _closes(bars: Sequence[Bar]) -> list[float]:
    return [b.close for b in bars]


def true_ranges(bars: Sequence[Bar]) -> list[float]:
    """True range series, aligned 1:1 with ``bars`` (first bar falls back to H-L)."""
    out: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            out.append(bar.high - bar.low)
        else:
            prev_close = bars[i - 1].close
            out.append(
                max(
                    bar.high - bar.low,
                    abs(bar.high - prev_close),
                    abs(bar.low - prev_close),
                )
            )
    return out


def atr(bars: Sequence[Bar], period: int = 14) -> float | None:
    """Wilder's Average True Range over ``period`` bars.

    Returns ``None`` when there is insufficient data. This is the correct basis
    for stop placement: a fixed point stop cannot know how noisy the instrument
    currently is.
    """
    if period <= 0 or len(bars) < period:
        return None
    value = atr_series(bars, period)[-1]
    if value <= 0:
        return None
    return value


def atr_series(bars: Sequence[Bar], period: int = 14) -> list[float]:
    """Wilder ATR v1: first TR high-low, period SMA seed, recursive smoothing."""
    if period <= 0 or len(bars) < period:
        return []
    trs = true_ranges(bars)
    value = sum(trs[:period]) / period
    values = [value]
    for true_range in trs[period:]:
        value = (value * (period - 1) + true_range) / period
        values.append(value)
    return values


def vwap(bars: Sequence[Bar]) -> float | None:
    """Volume-weighted average price over ``bars``.

    Returns unknown when observed volume is unavailable; no mean-price substitute.
    """
    if not bars:
        return None
    total_volume = sum(b.volume for b in bars)
    if total_volume <= 0:
        return None
    return sum(b.typical_price * b.volume for b in bars) / total_volume


def donchian(bars: Sequence[Bar], period: int = 20) -> tuple[float, float] | None:
    """Rolling Donchian channel as ``(upper, lower)`` over the last ``period`` bars.

    Excludes the forming bar to avoid self-referential channels.
    """
    if period <= 1 or len(bars) < period + 1:
        return None
    window = bars[-(period + 1) : -1]
    return max(b.high for b in window), min(b.low for b in window)


def zscore(series: Sequence[float], period: int = 20) -> float | None:
    """Standardised position of the final element within its rolling window."""
    if period <= 1 or len(series) < period:
        return None
    window = list(series[-period:])
    mean = sum(window) / len(window)
    variance = sum((x - mean) ** 2 for x in window) / len(window)
    std = math.sqrt(variance)
    if std <= 1e-12:
        return 0.0
    return (window[-1] - mean) / std


def mean_reversion_distance(bars: Sequence[Bar], period: int = 20) -> float | None:
    """Z-score of the close versus its rolling mean."""
    if period <= 1 or len(bars) < period:
        return None
    return zscore(_closes(bars), period=period)


def realized_volatility(bars: Sequence[Bar], period: int = 20) -> float | None:
    """Standard deviation of log returns over ``period`` bars, annualisation-free.

    Reported as a fraction of price (e.g. ``0.004`` == 0.4% per bar) so it can be
    compared against target distances without unit confusion.
    """
    if period <= 1 or len(bars) < period + 1:
        return None
    window = bars[-(period + 1) :]
    rets: list[float] = []
    for i in range(1, len(window)):
        prev = window[i - 1].close
        if prev <= 0:
            continue
        rets.append(math.log(window[i].close / prev))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(variance)


def trend_strength(bars: Sequence[Bar], period: int = 20) -> float | None:
    """Directional consistency in ``[-1, 1]``.

    Computed as net displacement over the window divided by total path length.
    Near ``+/-1`` means a clean trend; near ``0`` means chop.
    """
    if period <= 1 or len(bars) < period:
        return None
    window = _closes(bars)[-period:]
    net = window[-1] - window[0]
    path = sum(abs(window[i] - window[i - 1]) for i in range(1, len(window)))
    if path <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, net / path))


def oi_change(bars: Sequence[Bar]) -> float | None:
    """Fractional open-interest change between the last two bars.

    Returns ``None`` when the feed does not carry OI, which is the honest
    answer - callers must treat an OI-dependent strategy as unavailable rather
    than silently trading without the feature it is named for.
    """
    if len(bars) < 2:
        return None
    last = bars[-1].open_interest
    prev = bars[-2].open_interest
    if last is None or prev is None or prev <= 0:
        return None
    return (last - prev) / prev


def volume_ratio(bars: Sequence[Bar], period: int = 20) -> float | None:
    """Latest volume versus its rolling average. ``>1`` means expansion."""
    if period <= 1 or len(bars) < period:
        return None
    vols = [b.volume for b in bars[-period:]]
    avg = sum(vols) / len(vols)
    if avg <= 0:
        return None
    return vols[-1] / avg


# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketRegime:
    """Classified volatility/trend state for the current bar window."""

    regime: str
    trend: float | None
    volatility: float | None
    atr: float | None
    vwap: float | None
    donchian_upper: float | None
    donchian_lower: float | None
    confidence: float
    description: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "trend": None if self.trend is None else round(self.trend, 3),
            "volatility": None if self.volatility is None else round(self.volatility, 5),
            "atr": None if self.atr is None else round(self.atr, 3),
            "vwap": self.vwap,
            "donchian_upper": self.donchian_upper,
            "donchian_lower": self.donchian_lower,
            "confidence": round(self.confidence, 3),
            "description": self.description,
        }


def classify_regime(bars: Sequence[Bar], *, lookback: int = 20) -> MarketRegime:
    """Classify the current market into a tradable regime.

    The pre-audit gate fired on a 1-sigma stretch of 60 seconds of ticks, which
    is inside the noise band essentially all the time. This classifier requires
    enough bars, uses realised volatility, and reports a heuristic confidence
    so the entry layer can abstain when the read is weak.
    """
    if len(bars) < max(5, lookback // 2):
        return MarketRegime(
            regime="INSUFFICIENT_DATA",
            trend=None,
            volatility=None,
            atr=None,
            vwap=None,
            donchian_upper=None,
            donchian_lower=None,
            confidence=0.0,
            description=f"Need {max(5, lookback // 2)} bars, have {len(bars)}",
        )

    trend = trend_strength(bars, period=lookback)
    vol = realized_volatility(bars, period=lookback)
    atr_val = atr(bars, period=min(14, len(bars)))
    vwap_val = vwap(bars[-lookback:])
    dc = donchian(bars, period=min(lookback, max(2, len(bars) - 1)))

    if trend is None or vol is None:
        return MarketRegime(
            regime="INSUFFICIENT_DATA",
            trend=trend,
            volatility=vol,
            atr=atr_val,
            vwap=vwap_val,
            donchian_upper=dc[0] if dc else None,
            donchian_lower=dc[1] if dc else None,
            confidence=0.0,
            description="Insufficient history for a regime read",
        )

    # Confidence rises with the absolute trend reading and falls with noise.
    confidence = min(1.0, abs(trend))

    if abs(trend) >= 0.55:
        regime = "STRONG_TREND"
        desc = f"Trend {trend:+.2f} (clean directional move)"
    elif abs(trend) >= 0.3:
        regime = "WEAK_TREND"
        desc = f"Trend {trend:+.2f} (developing directionality)"
    elif vol is not None and vol < 0.0015:
        regime = "COMPRESSION"
        desc = f"Low volatility ({vol:.4f}) - range or pre-expansion"
    else:
        regime = "CHOP"
        desc = f"Trend {trend:+.2f} with elevated noise - poor for directional entry"

    return MarketRegime(
        regime=regime,
        trend=trend,
        volatility=vol,
        atr=atr_val,
        vwap=vwap_val,
        donchian_upper=dc[0] if dc else None,
        donchian_lower=dc[1] if dc else None,
        confidence=confidence,
        description=desc,
    )


# ---------------------------------------------------------------------------
# ATR-derived trade geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TradeGeometry:
    """Volatility-scaled stop and target distances in price points."""

    stop_points: float
    target_points: float
    atr: float
    risk_reward: float
    basis: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "stop_points": round(self.stop_points, 2),
            "target_points": round(self.target_points, 2),
            "atr": round(self.atr, 3),
            "risk_reward": round(self.risk_reward, 2),
            "basis": self.basis,
        }


def atr_geometry(
    bars: Sequence[Bar],
    *,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    fallback_stop: float = 0.0,
    fallback_target: float = 0.0,
    tick_size: float = 0.01,
) -> TradeGeometry:
    """Derive stop and target distances from ATR.

    Guarantees the stop sits outside normal bar noise, which is exactly what the
    hardcoded 22-point stop failed to do. Falls back to caller-supplied values
    when ATR is unavailable, and reports that honestly in ``basis``.
    """
    atr_val = atr(bars, period=min(14, len(bars))) if bars else None

    if atr_val is None or atr_val <= 0:
        stop = abs(fallback_stop)
        target = abs(fallback_target)
        basis = "FALLBACK_CONSTANT (ATR unavailable)"
    else:
        stop = atr_val * atr_multiplier
        target = stop * risk_reward
        basis = f"ATR({atr_multiplier}) x R:R({risk_reward})"

    if tick_size > 0:
        stop = max(round(stop / tick_size) * tick_size, tick_size)
        target = max(round(target / tick_size) * tick_size, tick_size)

    rr = target / stop if stop > 0 else 0.0
    return TradeGeometry(
        stop_points=stop,
        target_points=target,
        atr=atr_val or 0.0,
        risk_reward=rr,
        basis=basis,
    )


def validate_geometry(
    geometry: TradeGeometry,
    *,
    noise_multiple: float = 0.5,
) -> tuple[bool, str]:
    """Sanity-check that a stop is wide enough to survive bar noise."""
    if geometry.atr <= 0:
        return False, "ATR unavailable - cannot size a stop from volatility"
    if geometry.stop_points < geometry.atr * noise_multiple:
        return (
            False,
            f"Stop {geometry.stop_points:.2f} is under {noise_multiple}x ATR "
            f"({geometry.atr:.2f}) and will be taken out by noise",
        )
    if geometry.risk_reward < 1.0:
        return False, f"Risk:reward {geometry.risk_reward:.2f} < 1.0"
    return True, "Geometry valid"


def summarize(bars: Iterable[Bar]) -> dict[str, Any]:
    """Compact feature snapshot for dashboards and logs."""
    bars = list(bars)
    if not bars:
        return {"bars": 0}
    regime = classify_regime(bars)
    out: dict[str, Any] = {
        "bars": len(bars),
        "last_close": bars[-1].close,
        "regime": regime.as_dict(),
    }
    z = mean_reversion_distance(bars)
    if z is not None:
        out["zscore"] = round(z, 3)
    vr = volume_ratio(bars)
    if vr is not None:
        out["volume_ratio"] = round(vr, 3)
    oi = oi_change(bars)
    if oi is not None:
        out["oi_change_pct"] = round(oi * 100.0, 3)
    else:
        out["oi_change_pct"] = None
    return out


__all__ = [
    "Bar",
    "MarketRegime",
    "TickAggregator",
    "TradeGeometry",
    "atr",
    "atr_geometry",
    "atr_series",
    "classify_regime",
    "donchian",
    "mean_reversion_distance",
    "oi_change",
    "realized_volatility",
    "summarize",
    "trend_strength",
    "true_ranges",
    "validate_geometry",
    "volume_ratio",
    "vwap",
    "zscore",
]
