from __future__ import annotations

from decimal import Decimal

from ats.trading_runtime.hwm import HWMConfig, ProfitProtectionState, evaluate_hwm


def test_initial_hwm_no_profit() -> None:
    state = evaluate_hwm(
        config=HWMConfig(),
        previous=None,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("100000"),
    )
    assert state.peak_equity == Decimal("100000")
    assert state.drawdown_fraction == Decimal("0")
    assert state.profit_protection == ProfitProtectionState.NONE


def test_peak_tracks_profit() -> None:
    s0 = evaluate_hwm(
        config=HWMConfig(),
        previous=None,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("100000"),
    )
    s1 = evaluate_hwm(
        config=HWMConfig(),
        previous=s0,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("102000"),
    )
    assert s1.peak_equity == Decimal("102000")
    assert s1.peak_profit == Decimal("2000")


def test_drawdown_deescalation_hint() -> None:
    cfg = HWMConfig(drawdown_deescalate_threshold=Decimal("0.02"))
    s0 = evaluate_hwm(
        config=cfg,
        previous=None,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("110000"),
    )
    s1 = evaluate_hwm(
        config=cfg,
        previous=s0,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("107000"),
    )
    assert s1.mode_hint is not None


def test_noise_floor_suppresses_tiny_giveback() -> None:
    cfg = HWMConfig(noise_floor=Decimal("100"))
    s0 = evaluate_hwm(
        config=cfg,
        previous=None,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("101000"),
    )
    s1 = evaluate_hwm(
        config=cfg,
        previous=s0,
        session_start_equity=Decimal("100000"),
        current_equity=Decimal("100950"),
    )
    assert s1.giveback_from_peak == Decimal("0")
