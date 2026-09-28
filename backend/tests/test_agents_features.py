"""Tests for the feature layer: bars, volatility, and structure indicators."""

from __future__ import annotations

import pytest
from ats.agents.features import (
    Bar,
    TickAggregator,
    atr,
    atr_geometry,
    classify_regime,
    donchian,
    oi_change,
    realized_volatility,
    summarize,
    trend_strength,
    validate_geometry,
    volume_ratio,
    vwap,
    zscore,
)


def _bar(
    o: float,
    h: float,
    low: float,
    c: float,
    v: float = 0.0,
    oi: float | None = None,
) -> Bar:
    return Bar(
        timestamp=0.0,
        open=o,
        high=h,
        low=low,
        close=c,
        volume=v,
        tick_count=10,
        open_interest=oi,
    )


def test_aggregator_builds_bars_on_time_buckets():
    agg = TickAggregator(interval_seconds=60.0)
    # 10 ticks inside the first minute.
    for i in range(10):
        agg.update(price=100.0 + i, timestamp=10.0 + i)
    completed = agg.update(price=200.0, timestamp=70.0)
    assert completed is not None
    assert completed.high == 109.0
    assert completed.low == 100.0
    assert completed.close == 109.0
    assert len(agg.closed_bars) == 1


def test_aggregator_ignores_invalid_prices():
    agg = TickAggregator(interval_seconds=60.0)
    assert agg.update(price=0.0, timestamp=1.0) is None
    assert agg.update(price=-5.0, timestamp=1.0) is None


def test_aggregator_rejects_bad_interval():
    with pytest.raises(ValueError):
        TickAggregator(interval_seconds=0.0)


def test_atr_needs_enough_bars():
    bars = [_bar(10, 11, 9, 10) for _ in range(3)]
    assert atr(bars, period=14) is None


def test_atr_measures_bar_range():
    bars = [_bar(100, 105, 95, 100) for _ in range(20)]
    a = atr(bars, period=14)
    assert a is not None
    assert a == pytest.approx(10.0, rel=0.5)


def test_vwap_volume_weighted():
    bars = [_bar(10, 12, 8, 10, v=10.0), _bar(20, 22, 18, 20, v=30.0)]
    # typical prices 10 and 20, weighted 10:30 -> 17.5
    assert vwap(bars) == pytest.approx(17.5)


def test_vwap_falls_back_without_volume():
    bars = [_bar(10, 12, 8, 10), _bar(20, 22, 18, 20)]
    assert vwap(bars) == pytest.approx(15.0)


def test_donchian_excludes_forming_bar():
    bars = [_bar(100, 100 + i, 100 - i, 100) for i in range(5)]
    upper, lower = donchian(bars, period=3)
    assert upper is not None and lower is not None
    assert upper >= lower


def test_donchian_needs_extra_bar():
    assert donchian([_bar(1, 1, 1, 1)], period=20) is None


def test_zscore_of_flat_series_is_zero():
    assert zscore([5.0] * 20, period=20) == 0.0


def test_trend_strength_signs():
    up = [_bar(100 + i, 101 + i, 99 + i, 100 + i) for i in range(20)]
    down = [_bar(100 - i, 101 - i, 99 - i, 100 - i) for i in range(20)]
    assert trend_strength(up, period=20) > 0.9
    assert trend_strength(down, period=20) < -0.9


def test_oi_change_detects_build():
    bars = [_bar(10, 10, 10, 10, oi=100.0), _bar(10, 10, 10, 10, oi=110.0)]
    assert oi_change(bars) == pytest.approx(0.1)


def test_oi_change_none_when_feature_missing():
    bars = [_bar(10, 10, 10, 10), _bar(10, 10, 10, 10)]
    assert oi_change(bars) is None


def test_realized_volatility_zero_for_flat():
    bars = [_bar(10, 10, 10, 10) for _ in range(25)]
    assert realized_volatility(bars, period=20) == pytest.approx(0.0)


def test_volume_ratio_expansion():
    bars = [_bar(10, 10, 10, 10, v=10.0) for _ in range(19)]
    bars.append(_bar(10, 10, 10, 10, v=50.0))
    assert volume_ratio(bars, period=20) == pytest.approx(50.0 / (19 * 10.0 + 50.0) * 20, rel=0.3)


def test_classify_regime_detects_strong_trend():
    bars = [_bar(100 + i * 2, 101 + i * 2, 99 + i * 2, 100 + i * 2) for i in range(30)]
    r = classify_regime(bars, lookback=20)
    assert r.regime == "STRONG_TREND"
    assert r.confidence > 0.5


def test_classify_regime_insufficient_data():
    r = classify_regime([_bar(1, 1, 1, 1)], lookback=20)
    assert r.regime == "INSUFFICIENT_DATA"
    assert r.confidence == 0.0


def test_atr_geometry_derives_from_atr():
    bars = [_bar(100, 105, 95, 100) for _ in range(20)]
    g = atr_geometry(bars, atr_multiplier=1.5, risk_reward=2.0)
    assert g.atr > 0
    assert g.risk_reward == pytest.approx(2.0)
    assert g.target_points == pytest.approx(g.stop_points * 2.0, rel=0.05)


def test_atr_geometry_falls_back_honestly():
    g = atr_geometry([_bar(100, 100, 100, 100)], fallback_stop=20.0, fallback_target=40.0)
    assert "FALLBACK" in g.basis
    assert g.stop_points == pytest.approx(20.0)


def test_validate_geometry_rejects_noise_stop():
    class G:
        atr = 10.0
        stop_points = 2.0
        target_points = 20.0
        risk_reward = 10.0

    ok, why = validate_geometry(G(), noise_multiple=0.5)  # type: ignore[arg-type]
    assert not ok
    assert "noise" in why


def test_summarize_reports_features():
    bars = [_bar(100 + i, 101 + i, 99 + i, 100 + i, v=10.0) for i in range(30)]
    s = summarize(bars)
    assert s["bars"] == 30
    assert "regime" in s
    assert s["oi_change_pct"] is None
