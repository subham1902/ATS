"""Materially different signal families.

The 2026-09-28 historical validation showed that ten trend/mean-reversion
variants all had negative out-of-sample expectancy on the same single price
series. That is not ten bad strategies - it is one idea worn ten times. Trend
and mean reversion are complements, so optimising one tends to damage the other,
and no amount of parameter tuning escapes that.

These families are deliberately orthogonal to both. Each uses a *different
statistical structure*, not a different threshold on the same one:

============================  ==================================================
Family                        Structure it exploits
============================  ==================================================
``hurst_regime``              Serial correlation (persistent vs anti-persistent)
``moment_skew``               Distribution asymmetry and fat tails
``volume_divergence``         Price movement unsupported by participation
``squeeze``                   Volatility compression and release
``close_location``            Where price settles inside its own range
``session_seasonality``       Intraday time-of-day structure
============================  ==================================================

All of them operate on the bar layer from :mod:`ats.strategies.features` and return
the same :class:`~ats.strategies.definitions.StrategySignal` as the original
families, so they plug into the existing gate chain unchanged.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from ats.strategies.definitions import StrategySignal, _no_signal
from ats.strategies.features import (
    Bar,
    atr_geometry,
    classify_regime,
    trend_strength,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _closes(bars: Sequence[Bar]) -> list[float]:
    return [b.close for b in bars]


def _log_returns(closes: Sequence[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            out.append(math.log(closes[i] / closes[i - 1]))
    return out


def _variance_ratio(closes: Sequence[float], *, q: int = 5) -> float | None:
    """Variance ratio of aggregated ``q``-period returns over 1-period variance.

    VR > 1 indicates persistence (trending); VR < 1 indicates mean reversion.
    This is a *structural* classification of the series, not a direction call,
    which is what makes it orthogonal to trend-following.
    """
    rets = _log_returns(closes)
    if len(rets) < q * 4:
        return None

    mean = sum(rets) / len(rets)
    var1 = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    if var1 <= 0:
        return None

    agg: list[float] = []
    for i in range(0, len(rets) - q + 1, q):
        chunk = rets[i : i + q]
        if len(chunk) < q:
            break
        agg.append(sum(chunk))
    if len(agg) < 4:
        return None

    amean = sum(agg) / len(agg)
    var_q: float = sum((a - amean) ** 2 for a in agg) / (len(agg) - 1)
    if var_q <= 0:
        return None
    return var_q / (q * var1)


def _skewness(values: Sequence[float]) -> float | None:
    n = len(values)
    if n < 8:
        return None
    mean = sum(values) / n
    m2 = sum((v - mean) ** 2 for v in values) / n
    if m2 <= 1e-18:
        return None
    m3 = sum((v - mean) ** 3 for v in values) / n
    skew: float = m3 / (m2**1.5)
    return skew


def _close_location_value(bar: Bar) -> float:
    """Where the close sits inside the bar's range. +1 = on the high, -1 = low."""
    rng = bar.high - bar.low
    if rng <= 0:
        return 0.0
    return ((bar.close - bar.low) / rng) * 2.0 - 1.0


def _bandwidth(bars: Sequence[Bar], period: int) -> float | None:
    """Normalised Bollinger-style bandwidth: band width over mid price."""
    if len(bars) < period:
        return None
    window = bars[-period:]
    hi = max(b.high for b in window)
    lo = min(b.low for b in window)
    mid = sum(b.close for b in window) / len(window)
    if mid <= 0 or hi <= lo:
        return None
    return (hi - lo) / mid


def _percentile_of_current(values: Sequence[float]) -> float | None:
    """Fraction of ``values`` at or below the last element."""
    if len(values) < 8:
        return None
    last = values[-1]
    return sum(1 for v in values if v <= last) / len(values)


# ---------------------------------------------------------------------------
# Family 1: Hurst / serial-correlation regime
# ---------------------------------------------------------------------------


def strategy_hurst_regime(
    bars: list[Bar],
    *,
    lookback: int = 120,
    q: int = 5,
    vr_trend_threshold: float = 1.10,
    vr_reversion_threshold: float = 0.90,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Classify the series as persistent or mean-reverting, then act accordingly.

    Where trend-following and mean-reversion disagree, this sidesteps the
    argument: it measures which regime is actually present and trades only that.

    * VR above threshold -> persistent: trade with the recent drift.
    * VR below threshold -> anti-persistent: fade the extension.
    * Between the thresholds -> no structural edge, abstain.
    """
    sid = "H01_HURST_REGIME"
    if len(bars) < lookback:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback} bars, have {len(bars)}")

    closes = _closes(bars)
    vr = _variance_ratio(closes, q=q)
    regime = classify_regime(bars, lookback=min(lookback, len(bars)))
    features: dict[str, Any] = {"variance_ratio": None if vr is None else round(vr, 4)}

    if vr is None:
        return _no_signal(sid, regime.regime, "Variance ratio unavailable", features)

    if vr_trend_threshold <= vr:
        # Persistent structure: lean with the drift, not against it.
        drift = closes[-1] - closes[-(q + 1)] if len(closes) > q + 1 else 0.0
        if drift == 0:
            return _no_signal(sid, regime.regime, "No drift to follow", features)
        direction = "LONG" if drift > 0 else "SHORT"
        strength = min(1.0, (vr - vr_trend_threshold) / 0.5 + 0.5)
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction=direction,
            confidence=max(0.0, min(1.0, strength)),
            regime=f"PERSISTENT(VR={vr:.2f})",
            rationale=(
                f"Variance ratio {vr:.2f} > {vr_trend_threshold} indicates persistent "
                f"structure; following drift {direction}"
            ),
            geometry=geom,
            features=features,
        )

    if vr <= vr_reversion_threshold:
        # Anti-persistent structure: fade the latest move.
        last_move = closes[-1] - closes[-2] if len(closes) > 2 else 0.0
        if last_move == 0:
            return _no_signal(sid, regime.regime, "No move to fade", features)
        direction = "SHORT" if last_move > 0 else "LONG"
        strength = min(1.0, (vr_reversion_threshold - vr) / 0.5 + 0.5)
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction=direction,
            confidence=max(0.0, min(1.0, strength)),
            regime=f"ANTI_PERSISTENT(VR={vr:.2f})",
            rationale=(
                f"Variance ratio {vr:.2f} < {vr_reversion_threshold} indicates "
                f"mean-reverting structure; fading move {direction}"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(
        sid,
        regime.regime,
        f"Variance ratio {vr:.2f} between thresholds - no structural edge",
        features,
    )


# ---------------------------------------------------------------------------
# Family 2: Distribution skew / fat tails
# ---------------------------------------------------------------------------


def strategy_moment_skew(
    bars: list[Bar],
    *,
    lookback: int = 60,
    skew_threshold: float = 0.6,
    atr_multiplier: float = 1.5,
    risk_reward: float = 1.8,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Fade statistically skewed returns.

    Uses third-moment asymmetry rather than price level. A series with a fat
    right tail offers poor long expectancy regardless of direction, because the
    left tail is thin and frequent; the skew itself is the signal.
    """
    sid = "H02_MOMENT_SKEW"
    if len(bars) < lookback:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback} bars, have {len(bars)}")

    rets = _log_returns(_closes(bars))
    skew = _skewness(rets)
    regime = classify_regime(bars, lookback=min(lookback, len(bars)))
    features = {"skew": None if skew is None else round(skew, 3)}

    if skew is None:
        return _no_signal(sid, regime.regime, "Skew unavailable", features)

    if skew >= skew_threshold:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, abs(skew) / (skew_threshold * 3.0)),
            regime=regime.regime,
            rationale=(
                f"Right-skewed returns ({skew:+.2f}) imply thin left tail - "
                f"shorting offers the better distribution"
            ),
            geometry=geom,
            features=features,
        )

    if skew <= -skew_threshold:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, abs(skew) / (skew_threshold * 3.0)),
            regime=regime.regime,
            rationale=(
                f"Left-skewed returns ({skew:+.2f}) imply thin right tail - "
                f"buying offers the better distribution"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(
        sid, regime.regime, f"Skew {skew:+.2f} symmetric - no distributional edge", features
    )


# ---------------------------------------------------------------------------
# Family 3: Volume divergence
# ---------------------------------------------------------------------------


def strategy_volume_divergence(
    bars: list[Bar],
    *,
    lookback: int = 20,
    min_ratio: float = 0.70,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Fade price moves that participation does not support.

    A new high on shrinking volume is a different phenomenon from a new high on
    expanding volume. This family reads only the *relationship* between the two,
    so it is largely uncorrelated with any price-only trend system.
    """
    sid = "H03_VOLUME_DIVERGENCE"
    if len(bars) < lookback + 2:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 2} bars, have {len(bars)}")

    window = bars[-(lookback + 1) : -1]
    if any(b.volume <= 0 for b in window) or window[-1].volume <= 0:
        return _no_signal(
            sid, "FEATURE_UNAVAILABLE", "Volume absent on this feed - cannot assess divergence"
        )

    avg_vol = sum(b.volume for b in window) / len(window)
    if avg_vol <= 0:
        return _no_signal(sid, "FEATURE_UNAVAILABLE", "No volume history")

    last = bars[-1]
    vol_ratio = last.volume / avg_vol
    prev = bars[-2]
    price_up = last.close > prev.close
    high = max(b.high for b in window)
    low = min(b.low for b in window)
    regime = classify_regime(bars, lookback=lookback)

    features = {
        "volume_ratio": round(vol_ratio, 3),
        "avg_volume": round(avg_vol, 4),
        "price_direction": "up" if price_up else "down",
    }

    # New extreme on weak participation: exhaustion.
    if last.close > high and price_up and vol_ratio < min_ratio:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, (1.0 - vol_ratio) + 0.35),
            regime=regime.regime,
            rationale=(
                f"New high {last.close:.2f} on {vol_ratio:.2f}x average volume - "
                f"move is not supported by participation"
            ),
            geometry=geom,
            features=features,
        )

    if last.close < low and not price_up and vol_ratio < min_ratio:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, (1.0 - vol_ratio) + 0.35),
            regime=regime.regime,
            rationale=(
                f"New low {last.close:.2f} on {vol_ratio:.2f}x average volume - "
                f"move is not supported by participation"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, f"Volume ratio {vol_ratio:.2f} - no divergence", features)


# ---------------------------------------------------------------------------
# Family 4: Squeeze / volatility compression and release
# ---------------------------------------------------------------------------


def strategy_squeeze(
    bars: list[Bar],
    *,
    lookback: int = 40,
    compress_percentile: float = 0.20,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.5,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Trade the direction of a volatility release out of compression.

    Uses the *rank* of current bandwidth within its own history, so it adapts
    to any instrument's volatility regime rather than assuming absolute levels.
    """
    sid = "H04_SQUEEZE_RELEASE"
    if len(bars) < lookback + 5:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 5} bars, have {len(bars)}")

    series: list[float] = []
    for i in range(lookback, len(bars) + 1):
        bw = _bandwidth(bars[:i], lookback)
        if bw is not None:
            series.append(bw)
    if len(series) < 12:
        return _no_signal(sid, "INSUFFICIENT_DATA", "Insufficient bandwidth history")

    pct = _percentile_of_current(series)
    regime = classify_regime(bars, lookback=lookback)
    features = {
        "bandwidth": round(series[-1], 6),
        "bandwidth_percentile": None if pct is None else round(pct, 3),
    }

    if pct is None:
        return _no_signal(sid, regime.regime, "Bandwidth percentile unavailable", features)

    if pct > 0.55:
        return _no_signal(
            sid, regime.regime, f"Bandwidth at {pct:.0%} - already released", features
        )

    if pct > compress_percentile:
        return _no_signal(
            sid,
            regime.regime,
            f"Bandwidth at {pct:.0%}, above the {compress_percentile:.0%} squeeze threshold",
            features,
        )

    trend = trend_strength(bars[-lookback:], period=min(lookback, len(bars) - 1))
    if trend is None or abs(trend) < 0.12:
        return _no_signal(
            sid, regime.regime, "Compressed but no directional pressure - abstaining", features
        )

    direction = "LONG" if trend > 0 else "SHORT"
    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction=direction,
        confidence=min(1.0, 0.4 + (compress_percentile - pct) * 2.0),
        regime=f"COMPRESSED({pct:.0%})",
        rationale=(
            f"Bandwidth at {pct:.0%} of history with trend {trend:+.2f} - "
            f"trading the release {direction}"
        ),
        geometry=geom,
        features=features,
    )


# ---------------------------------------------------------------------------
# Family 5: Close location value persistence
# ---------------------------------------------------------------------------


def strategy_close_location(
    bars: list[Bar],
    *,
    run_length: int = 3,
    clv_threshold: float = 0.45,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Read where price settles inside its own range, as an order-flow proxy.

    Consecutive bars closing near the same extreme indicates persistent
    one-sided pressure. When that run *breaks*, pressure has exhausted and the
    next move tends to revert. Uses bar-internal structure that pure
    close-to-close systems ignore entirely.
    """
    sid = "H05_CLOSE_LOCATION"
    if len(bars) < run_length + 3:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {run_length + 3} bars, have {len(bars)}")

    clv = [_close_location_value(b) for b in bars]
    recent = clv[-run_length:]
    regime = classify_regime(bars, lookback=min(30, len(bars)))
    features = {
        "clv_recent": [round(v, 2) for v in recent],
        "clv_current": round(clv[-1], 3),
    }

    run_high = all(v >= clv_threshold for v in recent)
    run_low = all(v <= -clv_threshold for v in recent)

    if run_high and clv[-1] < clv_threshold:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, 0.45 + run_length * 0.08),
            regime=regime.regime,
            rationale=(
                f"{run_length}-bar run of closes near the high has broken - "
                f"one-sided pressure exhausted"
            ),
            geometry=geom,
            features=features,
        )

    if run_low and clv[-1] > -clv_threshold:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, 0.45 + run_length * 0.08),
            regime=regime.regime,
            rationale=(
                f"{run_length}-bar run of closes near the low has broken - "
                f"one-sided pressure exhausted"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, "No exhausted one-sided run to fade", features)


# ---------------------------------------------------------------------------
# Family 6: Intraday session seasonality
# ---------------------------------------------------------------------------


def strategy_session_seasonality(
    bars: list[Bar],
    *,
    bucket_hours: float = 1.0,
    min_samples: int = 6,
    min_mean_move: float = 0.0008,
    atr_multiplier: float = 1.5,
    risk_reward: float = 1.8,
    tick_size: float = 0.01,
    timezone_offset_hours: float = 5.5,
) -> StrategySignal:
    """Trade the empirical time-of-day profile of the instrument.

    Builds a conditional distribution of returns by hour bucket from the recent
    history and trades only when the current bucket's historical mean is
    meaningfully non-zero. This is a statistical property of *when* rather than
    *what* the price did, and is the least correlated family in the set.
    """
    sid = "H06_SESSION_SEASONALITY"
    if len(bars) < 40:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need 40 bars, have {len(bars)}")

    buckets: dict[int, list[float]] = defaultdict(list)
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1].close, bars[i].close
        if prev <= 0:
            continue
        ts = bars[i].timestamp + timezone_offset_hours * 3600.0
        hour = int(ts // 3600) % int(bucket_hours) if bucket_hours else int(ts // 3600)
        buckets[hour].append(math.log(cur / prev))

    regime = classify_regime(bars, lookback=min(30, len(bars)))
    ts_now = bars[-1].timestamp + timezone_offset_hours * 3600.0
    hour_now = int(ts_now // 3600) % int(bucket_hours) if bucket_hours else int(ts_now // 3600)

    samples = buckets.get(hour_now, [])
    features: dict[str, Any] = {
        "hour_bucket": hour_now,
        "samples": len(samples),
        "mean_move": None,
    }

    if len(samples) < min_samples:
        return _no_signal(
            sid, regime.regime, f"Hour bucket {hour_now} has only {len(samples)} samples", features
        )

    mean_move = sum(samples) / len(samples)
    features["mean_move"] = round(mean_move, 6)

    if abs(mean_move) < min_mean_move:
        return _no_signal(
            sid,
            regime.regime,
            f"Hour {hour_now} mean move {mean_move:+.5f} is not material",
            features,
        )

    confidence = min(1.0, 0.4 + abs(mean_move) / (min_mean_move * 3.0))

    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    direction = "LONG" if mean_move > 0 else "SHORT"
    return StrategySignal(
        strategy_id=sid,
        direction=direction,
        confidence=confidence,
        regime=regime.regime,
        rationale=(
            f"Hour bucket {hour_now} historically moves {mean_move:+.5f} over "
            f"{len(samples)} samples; trading {direction}"
        ),
        geometry=geom,
        features=features,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Families that are structurally distinct from trend and mean reversion.
DIVERSE_FAMILIES: dict[str, Any] = {
    "hurst_regime": strategy_hurst_regime,
    "moment_skew": strategy_moment_skew,
    "volume_divergence": strategy_volume_divergence,
    "squeeze": strategy_squeeze,
    "close_location": strategy_close_location,
    "session_seasonality": strategy_session_seasonality,
}

#: Human-readable description of what each family exploits, for the UI.
FAMILY_DESCRIPTIONS: dict[str, str] = {
    "hurst_regime": "Serial-correlation regime classification (persistent vs anti-persistent)",
    "moment_skew": "Distribution asymmetry and tail behaviour",
    "volume_divergence": "Price moves unsupported by participation",
    "squeeze": "Volatility compression and release",
    "close_location": "Where price settles inside its own range",
    "session_seasonality": "Intraday time-of-day return profile",
}


def register_diverse_families() -> int:
    """Register every diverse family into the global strategy registry.

    Idempotent: safe to call repeatedly.
    """
    from ats.strategies.definitions import STRATEGY_REGISTRY

    for name, fn in DIVERSE_FAMILIES.items():
        STRATEGY_REGISTRY[name] = fn
    return len(DIVERSE_FAMILIES)


__all__ = [
    "DIVERSE_FAMILIES",
    "FAMILY_DESCRIPTIONS",
    "register_diverse_families",
    "strategy_close_location",
    "strategy_hurst_regime",
    "strategy_moment_skew",
    "strategy_session_seasonality",
    "strategy_squeeze",
    "strategy_volume_divergence",
]
