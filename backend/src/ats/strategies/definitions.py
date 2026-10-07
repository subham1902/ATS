"""Concrete strategy implementations on the bar/feature layer.

Every strategy here is a real function of the market features in
:mod:`ats.strategies.features`. Each returns a :class:`StrategySignal` that the
worker evaluates for cost-gate viability before entering.

Design rules enforced across all strategies:

* No entry on insufficient data - return ``NO_SIGNAL`` rather than guessing.
* A strategy that depends on a feature the feed does not carry (e.g. open
  interest) must say so explicitly and abstain, not silently degrade.
* Targets and stops come from ATR via :func:`atr_geometry`, never from
  hardcoded point constants.
* Confidence is a heuristic score, not an empirical success probability.
  No XAUUSD calibration or performance authority is established.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ats.strategies.features import (
    Bar,
    MarketRegime,
    TradeGeometry,
    atr_geometry,
    classify_regime,
    donchian,
    mean_reversion_distance,
    oi_change,
    trend_strength,
    volume_ratio,
    vwap,
    zscore,
)


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """A strategy's output for one bar."""

    strategy_id: str
    direction: str | None
    confidence: float
    regime: str
    rationale: str
    geometry: TradeGeometry | None = None
    features: dict[str, Any] | None = None
    abstain_reason: str = ""

    @property
    def has_signal(self) -> bool:
        return self.direction is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "regime": self.regime,
            "rationale": self.rationale,
            "geometry": self.geometry.as_dict() if self.geometry else None,
            "features": self.features or {},
            "abstain_reason": self.abstain_reason,
        }


def _no_signal(
    strategy_id: str,
    regime: str,
    reason: str,
    features: dict[str, Any] | None = None,
) -> StrategySignal:
    return StrategySignal(
        strategy_id=strategy_id,
        direction=None,
        confidence=0.0,
        regime=regime,
        rationale=reason,
        geometry=None,
        features=features,
        abstain_reason=reason,
    )


# ---------------------------------------------------------------------------
# Individual strategies
# ---------------------------------------------------------------------------


def strategy_donchian_trend(
    bars: list[Bar],
    *,
    period: int = 20,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Donchian channel breakout with trend-strength confirmation.

    Replaces the pre-audit "recent high/low breakout over 60 seconds of ticks",
    which fired on noise. A 20-bar channel on 5-minute bars is a genuine
    structural breakout, and the ATR-derived stop guarantees the stop sits
    outside bar noise.
    """
    sid = "S03_DONCHIAN_ATR"
    if len(bars) < period + 2:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {period + 2} bars, have {len(bars)}")

    dc = donchian(bars, period=period)
    if dc is None:
        return _no_signal(sid, "INSUFFICIENT_DATA", "Donchian channel unavailable")

    upper, lower = dc
    last = bars[-1]
    trend = trend_strength(bars, period=period)
    regime = classify_regime(bars, lookback=period)

    features = {
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "close": last.close,
        "trend_strength": None if trend is None else round(trend, 3),
    }

    if last.close > upper and trend is not None and trend > 0.2:
        geom = atr_geometry(
            bars,
            atr_multiplier=atr_multiplier,
            risk_reward=risk_reward,
            fallback_stop=atr_multiplier * 5.0,
            fallback_target=risk_reward * atr_multiplier * 5.0,
            tick_size=tick_size,
        )
        conf = min(1.0, 0.5 + abs(trend or 0.0) * 0.5)
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=conf,
            regime=regime.regime,
            rationale=(
                f"Close {last.close:.2f} broke {period}-bar high "
                f"{upper:.2f} with trend {trend:+.2f}"
            ),
            geometry=geom,
            features=features,
        )

    if last.close < lower and trend is not None and trend < -0.2:
        geom = atr_geometry(
            bars,
            atr_multiplier=atr_multiplier,
            risk_reward=risk_reward,
            fallback_stop=atr_multiplier * 5.0,
            fallback_target=risk_reward * atr_multiplier * 5.0,
            tick_size=tick_size,
        )
        conf = min(1.0, 0.5 + abs(trend or 0.0) * 0.5)
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=conf,
            regime=regime.regime,
            rationale=(
                f"Close {last.close:.2f} broke {period}-bar low {lower:.2f} with trend {trend:+.2f}"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, "Price inside channel - no breakout", features)


def strategy_zscore_reversion(
    bars: list[Bar],
    *,
    period: int = 20,
    entry_sigma: float = 1.5,
    atr_multiplier: float = 1.5,
    risk_reward: float = 1.5,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Mean reversion from a statistically extended close.

    Uses a 1.5-sigma entry on *bars* rather than the pre-audit 1.0-sigma on
    60 seconds of ticks, and requires the regime to be non-trending so it does
    not stand in front of a trend.
    """
    sid = "S05_MEAN_REV"
    if len(bars) < period + 1:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {period + 1} bars, have {len(bars)}")

    z = mean_reversion_distance(bars, period=period)
    if z is None:
        return _no_signal(sid, "INSUFFICIENT_DATA", "Z-score unavailable")

    regime = classify_regime(bars, lookback=period)
    features = {"zscore": round(z, 3), "regime": regime.regime}

    if regime.regime in ("STRONG_TREND", "WEAK_TREND"):
        return _no_signal(
            sid,
            regime.regime,
            f"Z={z:+.2f} but regime is {regime.regime} - fading a trend is unsafe",
            features,
        )

    if z <= -entry_sigma:
        geom = atr_geometry(
            bars,
            atr_multiplier=atr_multiplier,
            risk_reward=risk_reward,
            tick_size=tick_size,
        )
        conf = min(1.0, abs(z) / (entry_sigma * 2.0))
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=conf,
            regime=regime.regime,
            rationale=f"Close {z:+.2f}σ oversold in {regime.regime} - reverting to mean",
            geometry=geom,
            features=features,
        )

    if z >= entry_sigma:
        geom = atr_geometry(
            bars,
            atr_multiplier=atr_multiplier,
            risk_reward=risk_reward,
            tick_size=tick_size,
        )
        conf = min(1.0, abs(z) / (entry_sigma * 2.0))
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=conf,
            regime=regime.regime,
            rationale=f"Close {z:+.2f}σ overbought in {regime.regime} - reverting to mean",
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, f"Z={z:+.2f} inside ±{entry_sigma}σ band", features)


def strategy_oi_volume_machine(
    bars: list[Bar],
    *,
    lookback: int = 20,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Open-interest and volume confirmation state machine.

    This is the strategy the pre-audit system *named* but never implemented - it
    read no OI and no volume. Critically, when the feed carries no OI it
    abstains explicitly instead of trading without the feature that defines it.
    """
    sid = "S17_OI_VOLUME_MACHINE"
    if len(bars) < lookback + 2:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 2} bars, have {len(bars)}")

    oi = oi_change(bars)
    if oi is None:
        return _no_signal(
            sid,
            "FEATURE_UNAVAILABLE",
            "Open interest not present on this feed - S17 requires OI and will not "
            "trade without it (abstaining rather than substituting a different signal)",
        )

    vr = volume_ratio(bars, period=lookback)
    trend = trend_strength(bars, period=lookback)
    regime = classify_regime(bars, lookback=lookback)

    features = {
        "oi_change_pct": round(oi * 100.0, 3),
        "volume_ratio": None if vr is None else round(vr, 3),
        "trend_strength": None if trend is None else round(trend, 3),
    }

    if vr is None or vr < 1.2:
        return _no_signal(
            sid, regime.regime, f"Volume ratio {vr} below 1.2 - no participation", features
        )
    if trend is None:
        return _no_signal(sid, regime.regime, "Trend strength unavailable", features)

    # Price up + OI up + volume expanding = new longs driving the move.
    if trend > 0.15 and oi > 0.0:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, 0.5 + min(vr, 3.0) * 0.15),
            regime=regime.regime,
            rationale=(
                f"Price trend {trend:+.2f} with OI {oi * 100:+.2f}% and volume "
                f"{vr:.2f}x - fresh long participation"
            ),
            geometry=geom,
            features=features,
        )

    # Price down + OI up + volume expanding = fresh short participation.
    if trend < -0.15 and oi > 0.0:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, 0.5 + min(vr, 3.0) * 0.15),
            regime=regime.regime,
            rationale=(
                f"Price trend {trend:+.2f} with OI {oi * 100:+.2f}% and volume "
                f"{vr:.2f}x - fresh short participation"
            ),
            geometry=geom,
            features=features,
        )

    return _no_signal(
        sid,
        regime.regime,
        f"No OI-confirmed state (trend {trend:+.2f}, OI {oi * 100:+.2f}%)",
        features,
    )


def strategy_vwap_trend(
    bars: list[Bar],
    *,
    lookback: int = 20,
    atr_multiplier: float = 2.0,
    risk_reward: float = 2.5,
    tick_size: float = 0.01,
) -> StrategySignal:
    """VWAP-anchored swing trend capture.

    A wider stop and better R:R than the intraday strategies, because a swing
    target must clear materially more cost for the trade to be worth holding.
    """
    sid = "S02_TSMOM"
    if len(bars) < lookback + 1:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 1} bars, have {len(bars)}")

    v = vwap(bars[-lookback:])
    if v is None:
        return _no_signal(sid, "INSUFFICIENT_DATA", "VWAP unavailable")

    last = bars[-1]
    trend = trend_strength(bars, period=lookback)
    regime = classify_regime(bars, lookback=lookback)
    features = {
        "vwap": round(v, 2),
        "close": last.close,
        "distance_pct": round((last.close - v) / v * 100.0, 3) if v else None,
    }

    if trend is None or abs(trend) < 0.35:
        return _no_signal(
            sid,
            regime.regime,
            f"Trend {0.0 if trend is None else trend:+.2f} lacks conviction",
            features,
        )

    above = last.close > v
    if trend > 0.35 and above:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, abs(trend)),
            regime=regime.regime,
            rationale=f"Close {last.close:.2f} above VWAP {v:.2f}, trend {trend:+.2f}",
            geometry=geom,
            features=features,
        )

    if trend < -0.35 and not above:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, abs(trend)),
            regime=regime.regime,
            rationale=f"Close {last.close:.2f} below VWAP {v:.2f}, trend {trend:+.2f}",
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, "No VWAP-aligned momentum", features)


def strategy_volatility_expansion(
    bars: list[Bar],
    *,
    lookback: int = 20,
    expansion_ratio: float = 1.3,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Trade the direction of a volatility expansion in a compressing tape."""
    sid = "S04_VOL_TARGET"
    if len(bars) < lookback + 2:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 2} bars, have {len(bars)}")

    from ats.strategies.features import realized_volatility

    current = realized_volatility(bars[-lookback:], period=lookback)
    baseline = realized_volatility(bars[-(lookback * 2) : -lookback], period=lookback)
    if current is None or baseline is None or baseline <= 0:
        return _no_signal(sid, "INSUFFICIENT_DATA", "Volatility history unavailable")

    ratio = current / baseline
    trend = trend_strength(bars[-lookback:], period=lookback)
    regime = classify_regime(bars, lookback=lookback)
    features = {
        "vol_ratio": round(ratio, 3),
        "current_vol": round(current, 5),
        "baseline_vol": round(baseline, 5),
    }

    if ratio < expansion_ratio:
        return _no_signal(
            sid,
            regime.regime,
            f"Volatility ratio {ratio:.2f} below {expansion_ratio:.1f}",
            features,
        )
    if trend is None or abs(trend) < 0.2:
        return _no_signal(sid, regime.regime, "Expansion without directional conviction", features)

    direction = "LONG" if trend > 0 else "SHORT"
    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction=direction,
        confidence=min(1.0, 0.45 + min(ratio, 3.0) * 0.2),
        regime=regime.regime,
        rationale=f"Volatility expanded {ratio:.2f}x with trend {trend:+.2f}",
        geometry=geom,
        features=features,
    )


def strategy_counter_trend(
    bars: list[Bar],
    *,
    period: int = 20,
    entry_sigma: float = 2.2,
    atr_multiplier: float = 2.0,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Fade a statistically extreme displacement on the swing horizon."""
    sid = "S07_NY_OVERLAP_TREND"
    if len(bars) < period + 1:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {period + 1} bars, have {len(bars)}")

    z = zscore([b.close for b in bars], period=period)
    if z is None:
        return _no_signal(sid, "INSUFFICIENT_DATA", "Z-score unavailable")

    regime = classify_regime(bars, lookback=period)
    features = {"zscore": round(z, 3), "regime": regime.regime}

    if z >= entry_sigma:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="SHORT",
            confidence=min(1.0, abs(z) / (entry_sigma * 2.0)),
            regime=regime.regime,
            rationale=f"Extreme +{z:.2f}σ extension - fading",
            geometry=geom,
            features=features,
        )
    if z <= -entry_sigma:
        geom = atr_geometry(
            bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
        )
        return StrategySignal(
            strategy_id=sid,
            direction="LONG",
            confidence=min(1.0, abs(z) / (entry_sigma * 2.0)),
            regime=regime.regime,
            rationale=f"Extreme {z:.2f}σ extension - fading",
            geometry=geom,
            features=features,
        )

    return _no_signal(sid, regime.regime, f"Z={z:+.2f} not extreme enough to fade", features)


def strategy_regime_filter(
    bars: list[Bar],
    *,
    lookback: int = 20,
    atr_multiplier: float = 2.0,
    risk_reward: float = 2.5,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Trade only when the regime classifier is emphatic.

    A deliberately selective filter strategy: most of the time it abstains,
    which is the correct behaviour. It exists to prove the abstention machinery
    works in a live path.
    """
    sid = "S06_REGIME_FILTER"
    if len(bars) < lookback:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback} bars, have {len(bars)}")

    regime: MarketRegime = classify_regime(bars, lookback=lookback)
    features = regime.as_dict()

    if regime.regime != "STRONG_TREND" or regime.trend is None:
        return _no_signal(
            sid,
            regime.regime,
            f"Regime '{regime.regime}' is not a strong trend - abstaining by design",
            features,
        )

    direction = "LONG" if regime.trend > 0 else "SHORT"
    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction=direction,
        confidence=min(1.0, abs(regime.trend)),
        regime=regime.regime,
        rationale=f"Strong trend {regime.trend:+.2f} confirmed by regime classifier",
        geometry=geom,
        features=features,
    )


def strategy_tick_velocity(
    bars: list[Bar],
    *,
    lookback: int = 20,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Bar-internal participation: many ticks with a directional close."""
    sid = "S02_MICRO_TICK"
    if len(bars) < lookback + 1:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {lookback + 1} bars, have {len(bars)}")

    counts = [b.tick_count for b in bars]
    avg = sum(counts[-lookback:]) / lookback
    if avg <= 0:
        return _no_signal(sid, "INSUFFICIENT_DATA", "No tick counts available")

    last = bars[-1]
    expansion = (last.tick_count / avg) if avg > 0 else 0.0
    body_ratio = abs(last.body) / last.true_range if last.true_range > 0 else 0.0
    regime = classify_regime(bars, lookback=lookback)
    features = {
        "tick_expansion": round(expansion, 3),
        "body_ratio": round(body_ratio, 3),
        "direction": "bullish" if last.is_bullish else "bearish",
    }

    if expansion < 1.5:
        return _no_signal(sid, regime.regime, f"Tick expansion {expansion:.2f} below 1.5", features)
    if body_ratio < 0.55:
        return _no_signal(
            sid, regime.regime, f"Body ratio {body_ratio:.2f} - bar is indecisive", features
        )

    direction = "LONG" if last.is_bullish else "SHORT"
    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction=direction,
        confidence=min(1.0, 0.4 + min(expansion, 4.0) * 0.15),
        regime=regime.regime,
        rationale=f"Tick expansion {expansion:.2f}x with {body_ratio:.0%} body",
        geometry=geom,
        features=features,
    )


def strategy_gap_fill(
    bars: list[Bar],
    *,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Fade a bar that closes far from its open (an unfilled auction gap)."""
    sid = "S03_GAP_FILL"
    if len(bars) < 21:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need 21 bars, have {len(bars)}")

    from ats.strategies.features import atr as atr_fn

    a = atr_fn(bars, period=14)
    last = bars[-1]
    if a is None or a <= 0:
        return _no_signal(sid, "INSUFFICIENT_DATA", "ATR unavailable")

    body = last.body
    ratio = abs(body) / a
    regime = classify_regime(bars, lookback=20)
    features = {"body": round(body, 2), "body_atr_ratio": round(ratio, 3), "atr": round(a, 2)}

    if ratio < 0.9:
        return _no_signal(
            sid, regime.regime, f"Bar body {ratio:.2f}x ATR - no displacement to fill", features
        )

    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction="SHORT" if body > 0 else "LONG",
        confidence=min(1.0, 0.4 + ratio * 0.2),
        regime=regime.regime,
        rationale=f"Bar closed {ratio:.2f}x ATR from open - fading the displacement",
        geometry=geom,
        features=features,
    )


def strategy_tsmom(
    bars: list[Bar],
    *,
    fast: int = 10,
    slow: int = 30,
    atr_multiplier: float = 1.5,
    risk_reward: float = 2.0,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Time-series momentum across stacked horizons."""
    sid = "S08_MTF_CONSOL"
    if len(bars) < slow + 2:
        return _no_signal(sid, "INSUFFICIENT_DATA", f"Need {slow + 2} bars, have {len(bars)}")

    closes = [b.close for b in bars]
    fast_ret = (closes[-1] - closes[-fast - 1]) / closes[-fast - 1] if closes[-fast - 1] else 0.0
    slow_ret = (closes[-1] - closes[-slow - 1]) / closes[-slow - 1] if closes[-slow - 1] else 0.0
    regime = classify_regime(bars, lookback=slow)
    features = {
        "fast_ret_pct": round(fast_ret * 100.0, 3),
        "slow_ret_pct": round(slow_ret * 100.0, 3),
    }

    if fast_ret <= 0 or slow_ret <= 0:
        return _no_signal(sid, regime.regime, "Momentum not positive across horizons", features)
    if fast_ret < slow_ret * 1.2:
        return _no_signal(
            sid,
            regime.regime,
            "Fast horizon not extending beyond slow - momentum stalled",
            features,
        )

    geom = atr_geometry(
        bars, atr_multiplier=atr_multiplier, risk_reward=risk_reward, tick_size=tick_size
    )
    return StrategySignal(
        strategy_id=sid,
        direction="LONG",
        confidence=min(1.0, 0.5 + (fast_ret - slow_ret) * 10.0),
        regime=regime.regime,
        rationale=f"Momentum aligned: fast {fast_ret * 100:+.2f}% > slow {slow_ret * 100:+.2f}%",
        geometry=geom,
        features=features,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

StrategyFn = Callable[..., StrategySignal]

#: Maps a mandate's ``signal_source`` to its concrete implementation.
STRATEGY_REGISTRY: dict[str, StrategyFn] = {
    "donchian": strategy_donchian_trend,
    "atr_expansion": strategy_volatility_expansion,
    "zscore": strategy_zscore_reversion,
    "oi_volume": strategy_oi_volume_machine,
    "vwap_trend": strategy_vwap_trend,
    "tick_velocity": strategy_tick_velocity,
    "gap_fill": strategy_gap_fill,
    "regime_gate": strategy_regime_filter,
    "tsmom": strategy_tsmom,
    "fade_extreme": strategy_counter_trend,
}


def ensure_diverse_families_loaded() -> None:
    """Idempotently register the built-in diverse families."""
    global _FAMILIES_LOADED
    if _FAMILIES_LOADED:
        return
    _autoload_diverse_families()
    _FAMILIES_LOADED = True


def register_family(name: str, fn: StrategyFn) -> None:
    """Register one strategy implementation under ``name``.

    Used both by the built-in diverse families and by operator-supplied
    custom strategies.
    """
    if not name or not name.strip():
        raise ValueError("strategy name must be non-empty")
    if not callable(fn):
        raise TypeError("strategy implementation must be callable")
    STRATEGY_REGISTRY[name.strip()] = fn


def unregister_family(name: str) -> bool:
    """Remove a strategy implementation. Returns True if it existed."""
    return STRATEGY_REGISTRY.pop(name, None) is not None


def _autoload_diverse_families() -> None:
    """Register the structurally-different families shipped with the platform.

    Deferred to first *use* rather than module import: ``families`` imports this
    module for ``StrategySignal``/``_no_signal``, so importing it eagerly here
    would be circular when ``families`` is the entry point.
    """
    from ats.strategies.families import register_diverse_families

    register_diverse_families()


#: Ensures the diverse families are present the first time a strategy is looked
#: up, without an import-time cycle.
_FAMILIES_LOADED = False


def evaluate_strategy(
    signal_source: str,
    bars: list[Bar],
    *,
    tick_size: float = 0.01,
) -> StrategySignal:
    """Dispatch to a strategy by mandate signal source."""
    ensure_diverse_families_loaded()
    fn = STRATEGY_REGISTRY.get(signal_source)
    if fn is None:
        return _no_signal(
            "UNKNOWN", "UNKNOWN", f"No implementation registered for '{signal_source}'"
        )
    return fn(bars, tick_size=tick_size)


__all__ = [
    "STRATEGY_REGISTRY",
    "StrategyFn",
    "StrategySignal",
    "evaluate_strategy",
    "register_family",
    "unregister_family",
    "strategy_counter_trend",
    "strategy_donchian_trend",
    "strategy_gap_fill",
    "strategy_oi_volume_machine",
    "strategy_regime_filter",
    "strategy_tick_velocity",
    "strategy_tsmom",
    "strategy_volatility_expansion",
    "strategy_vwap_trend",
    "strategy_zscore_reversion",
]
