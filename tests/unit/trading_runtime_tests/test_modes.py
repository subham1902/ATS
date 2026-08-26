from __future__ import annotations

from ats.trading_runtime.modes import TradingMode, resolve_effective_mode


def test_normal_stays_normal() -> None:
    state = resolve_effective_mode(user_selected=TradingMode.NORMAL)
    assert state.effective == TradingMode.NORMAL
    assert state.deescalation_reason is None


def test_hwm_deescalation() -> None:
    state = resolve_effective_mode(
        user_selected=TradingMode.AGGRESSIVE, hwm_deescalated=TradingMode.SAFE
    )
    assert state.effective == TradingMode.SAFE
    assert state.deescalation_reason == "HWM_DRAWDOWN_DEESCALATION"


def test_auto_escalation_forbidden() -> None:
    state = resolve_effective_mode(
        user_selected=TradingMode.AGGRESSIVE, previous_effective=TradingMode.NORMAL
    )
    assert state.effective == TradingMode.NORMAL
    assert state.deescalation_reason == "AUTO_ESCALATION_FORBIDDEN"


def test_auto_deescalation_allowed() -> None:
    state = resolve_effective_mode(
        user_selected=TradingMode.SAFE, previous_effective=TradingMode.NORMAL
    )
    assert state.effective == TradingMode.SAFE
    assert state.deescalation_reason is None


def test_safety_halted_overrides() -> None:
    state = resolve_effective_mode(user_selected=TradingMode.AGGRESSIVE, safety_halted=True)
    assert state.effective == TradingMode.HALTED
