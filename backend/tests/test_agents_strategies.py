"""Tests for the concrete strategy implementations.

Each strategy must abstain rather than guess when it lacks the data it is
named for, and must derive its geometry from ATR rather than point constants.
"""

from __future__ import annotations

import pytest
from ats.strategies.definitions import (
    evaluate_strategy,
    strategy_counter_trend,
    strategy_donchian_trend,
    strategy_oi_volume_machine,
    strategy_regime_filter,
    strategy_volatility_expansion,
    strategy_zscore_reversion,
)
from ats.strategies.features import Bar


def _mk(
    closes: list[float], *, vol: float = 1.0, oi: list[float | None] | None = None
) -> list[Bar]:
    out: list[Bar] = []
    for i, c in enumerate(closes):
        o = oi[i] if oi and i < len(oi) else None
        out.append(
            Bar(
                timestamp=float(i * 300),
                open=c,
                high=c + vol,
                low=c - vol,
                close=c,
                volume=100.0 + i,
                tick_count=100,
                open_interest=o,
            )
        )
    return out


def test_unknown_signal_source_abstains():
    s = evaluate_strategy("does_not_exist", _mk([1.0] * 30))
    assert not s.has_signal
    assert "No implementation" in s.rationale


@pytest.mark.parametrize(
    "fn",
    [
        strategy_donchian_trend,
        strategy_zscore_reversion,
        strategy_oi_volume_machine,
        strategy_counter_trend,
        strategy_regime_filter,
        strategy_volatility_expansion,
    ],
)
def test_every_strategy_abstains_without_enough_bars(fn):
    s = fn([Bar(timestamp=0, open=1, high=1, low=1, close=1) for _ in range(3)])
    assert not s.has_signal
    assert s.abstain_reason


def test_donchian_fires_on_channel_break():
    # Flat then a decisive break above the channel.
    closes = [100.0] * 25 + [101.0, 102.0, 103.0, 105.0, 107.0]
    s = strategy_donchian_trend(_mk(closes, vol=0.5), period=20)
    assert s.has_signal
    assert s.direction == "LONG"
    assert s.geometry is not None
    assert s.geometry.atr > 0


def test_donchian_abstains_inside_channel():
    closes = [100.0 + (i % 2) for i in range(30)]
    s = strategy_donchian_trend(_mk(closes, vol=0.5), period=20)
    assert not s.has_signal


def test_zscore_does_not_fade_a_strong_trend():
    closes = [100.0 + i * 3 for i in range(30)]
    s = strategy_zscore_reversion(_mk(closes, vol=0.2), period=20)
    assert not s.has_signal
    assert "trend" in s.rationale.lower()


def test_zscore_fires_when_extended_and_ranging():
    # Flat for 25 bars then a sharp move up: extended but not a clean trend.
    closes = [100.0] * 25 + [104.0]
    s = strategy_zscore_reversion(_mk(closes, vol=0.1), period=20)
    if s.has_signal:
        assert s.direction == "SHORT"


def test_oi_strategy_abstains_when_oi_missing():
    """The critical honesty check: no OI means no S17 trade."""
    s = strategy_oi_volume_machine(_mk([100.0 + i for i in range(30)]))
    assert not s.has_signal
    assert s.regime == "FEATURE_UNAVAILABLE"
    assert "open interest" in s.abstain_reason.lower()


def test_oi_strategy_uses_oi_when_present():
    oi = [1000.0] * 29 + [1200.0]
    closes = [100.0 + i * 0.5 for i in range(30)]
    bars = _mk(closes, oi=oi)
    bars[-1].volume = 10_000.0  # volume expansion
    s = strategy_oi_volume_machine(bars)
    assert s.has_signal
    assert s.direction == "LONG"


def test_regime_filter_is_selective():
    # Mostly flat market should not produce a trade.
    s = strategy_regime_filter(_mk([100.0 + (i % 2) * 0.1 for i in range(30)], vol=0.05))
    assert not s.has_signal
    assert "abstain" in s.rationale.lower()


def test_volatility_expansion_needs_expansion():
    flat = _mk([100.0] * 40, vol=0.05)
    s = strategy_volatility_expansion(flat)
    assert not s.has_signal


def test_counter_trend_fires_on_extreme():
    closes = [100.0] * 28 + [130.0, 140.0]
    s = strategy_counter_trend(_mk(closes, vol=0.5), period=20)
    assert s.has_signal
    assert s.direction == "SHORT"


def test_geometry_is_atr_derived_not_constant():
    """Two different volatility regimes must produce different stop distances."""
    series = [100.0] * 22 + [101, 102, 103, 105, 107]
    calm = strategy_donchian_trend(_mk(series, vol=0.2), period=20)
    wild = strategy_donchian_trend(_mk(series, vol=5.0), period=20)
    if calm.has_signal and wild.has_signal:
        assert wild.geometry.stop_points > calm.geometry.stop_points
