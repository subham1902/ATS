"""High-water-mark governor — peak equity, drawdown, profit protection, de-escalation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ats.trading_runtime.modes import TradingMode


class ProfitProtectionState(StrEnum):
    NONE = "NONE"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"


@dataclass(frozen=True)
class HWMConfig:
    hwm_update_min_profit: Decimal = Decimal("0.01")
    drawdown_deescalate_threshold: Decimal = Decimal("0.03")
    drawdown_halt_threshold: Decimal = Decimal("0.08")
    profit_giveback_threshold: Decimal = Decimal("0.02")
    noise_floor: Decimal = Decimal("0.005")


@dataclass(frozen=True)
class HWMState:
    session_start_equity: Decimal
    peak_equity: Decimal
    current_equity: Decimal
    drawdown_fraction: Decimal
    peak_profit: Decimal
    giveback_from_peak: Decimal
    profit_protection: ProfitProtectionState
    mode_hint: TradingMode | None


def evaluate_hwm(
    *,
    config: HWMConfig,
    previous: HWMState | None,
    session_start_equity: Decimal,
    current_equity: Decimal,
) -> HWMState:
    if previous is None:
        peak = max(session_start_equity, current_equity)
        profit = max(Decimal("0"), current_equity - session_start_equity)
        protection = ProfitProtectionState.NONE if profit == 0 else ProfitProtectionState.ARMED
        return HWMState(
            session_start_equity=session_start_equity,
            peak_equity=peak,
            current_equity=current_equity,
            drawdown_fraction=Decimal("0") if peak == 0 else (peak - current_equity) / peak,
            peak_profit=profit,
            giveback_from_peak=Decimal("0"),
            profit_protection=protection,
            mode_hint=None,
        )
    peak_equity = previous.peak_equity
    if current_equity - peak_equity >= config.hwm_update_min_profit:
        peak_equity = current_equity
    peak_profit = max(
        previous.peak_profit, current_equity - session_start_equity, Decimal("0")
    )
    drawdown = Decimal("0")
    if peak_equity != 0:
        drawdown = max(Decimal("0"), (peak_equity - current_equity) / peak_equity)
    giveback = max(Decimal("0"), peak_equity - current_equity)
    if giveback < config.noise_floor:
        giveback = Decimal("0")

    protection = previous.profit_protection
    if peak_profit > config.noise_floor and protection is ProfitProtectionState.NONE:
        protection = ProfitProtectionState.ARMED
    if protection is ProfitProtectionState.ARMED:
        if giveback >= config.profit_giveback_threshold:
            protection = ProfitProtectionState.TRIGGERED
    if protection is ProfitProtectionState.TRIGGERED:
        if current_equity > peak_equity - config.noise_floor:
            protection = ProfitProtectionState.ARMED

    mode_hint: TradingMode | None = None
    if drawdown >= config.drawdown_halt_threshold:
        mode_hint = TradingMode.HALTED
    elif drawdown >= config.drawdown_deescalate_threshold:
        mode_hint = TradingMode.SAFE
    elif protection is ProfitProtectionState.TRIGGERED:
        mode_hint = TradingMode.SAFE

    return HWMState(
        session_start_equity=session_start_equity,
        peak_equity=peak_equity,
        current_equity=current_equity,
        drawdown_fraction=drawdown,
        peak_profit=peak_profit,
        giveback_from_peak=giveback,
        profit_protection=protection,
        mode_hint=mode_hint,
    )


__all__ = ["HWMConfig", "HWMState", "ProfitProtectionState", "evaluate_hwm"]
