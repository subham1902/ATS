"""P1 position monitor — fast per-position state with trailing stop, HWM,
capital-weighted stops, and options-aware (Greeks/IV/theta) exit checks."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ats.contracts.common import UTCDateTime

from .hwm import HWMState


class PositionAction(StrEnum):
    HOLD = "HOLD"
    TRAIL = "TRAIL"
    EXIT = "EXIT"
    REDUCE = "REDUCE"
    NO_DATA = "NO_DATA"


class PositionOrigin(StrEnum):
    ATS_AUTONOMOUS = "ATS_AUTONOMOUS"
    OPERATOR_MANUAL = "OPERATOR_MANUAL"
    EXTERNAL_RECONCILED = "EXTERNAL_RECONCILED"


class ManagedExitMode(StrEnum):
    MONITOR_ONLY = "MONITOR_ONLY"
    ATS_MANAGED_EXIT = "ATS_MANAGED_EXIT"


@dataclass(frozen=True)
class PositionMonitorConfig:
    hard_loss_fraction: Decimal = Decimal("0.015")
    trailing_distance_fraction: Decimal = Decimal("0.008")
    profit_protection_fraction: Decimal = Decimal("0.02")
    max_hold_minutes: int = 90
    min_profit_for_trailing: Decimal = Decimal("0.004")
    iv_collapse_exit_fraction: float = 0.30
    theta_bleed_exit_fraction: float = 0.50


@dataclass(frozen=True)
class MonitoredPosition:
    position_id: str
    instrument_id: str
    entry_price: Decimal
    current_mark: Decimal | None
    quantity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    peak_pnl: Decimal
    current_stop: Decimal | None
    trailing_stop: Decimal | None
    time_held_minutes: int
    entry_thesis_ref: str | None
    thesis_healthy: bool
    data_fresh: bool
    last_event: str | None
    # --- Capital & Greeks extensions ---
    capital_at_risk: Decimal = Decimal("0")
    capital_committed: Decimal = Decimal("0")
    risk_budget: Decimal = Decimal("0")
    maximum_loss_per_unit: Decimal = Decimal("0")
    entry_iv: float | None = None
    greeks_delta: float | None = None
    greeks_theta: float | None = None
    greeks_iv: float | None = None
    entry_at: UTCDateTime | None = None
    lot_size: int = 1
    expected_edge_r: float = 0.0
    direction: str = "BULLISH"
    origin: PositionOrigin = PositionOrigin.ATS_AUTONOMOUS
    managed_exit_mode: ManagedExitMode = ManagedExitMode.ATS_MANAGED_EXIT
    operator_action_id: str | None = None


def update_mark(
    position: MonitoredPosition,
    *,
    mark: Decimal,
    at: UTCDateTime,
    greeks_delta: float | None = None,
    greeks_theta: float | None = None,
    greeks_iv: float | None = None,
    data_fresh: bool = True,
) -> MonitoredPosition:
    """Return a new MonitoredPosition with updated mark, PnL, time, and greeks.

    This is the core fix: positions must be re-marked on every tick/bar so that
    stop-loss, trailing-stop, and PnL monitoring operate on live data.
    """
    unrealized = (mark - position.entry_price) * position.quantity
    new_peak = max(position.peak_pnl, unrealized)
    held_minutes = position.time_held_minutes
    if position.entry_at is not None:
        held_minutes = max(0, int((at - position.entry_at).total_seconds() / 60))
    return MonitoredPosition(
        position_id=position.position_id,
        instrument_id=position.instrument_id,
        entry_price=position.entry_price,
        current_mark=mark,
        quantity=position.quantity,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=unrealized,
        peak_pnl=new_peak,
        current_stop=position.current_stop,
        trailing_stop=position.trailing_stop,
        time_held_minutes=held_minutes,
        entry_thesis_ref=position.entry_thesis_ref,
        thesis_healthy=position.thesis_healthy,
        data_fresh=data_fresh,
        last_event="MARK_UPDATE",
        capital_at_risk=position.capital_at_risk,
        capital_committed=position.capital_committed,
        risk_budget=position.risk_budget,
        maximum_loss_per_unit=position.maximum_loss_per_unit,
        entry_iv=position.entry_iv,
        greeks_delta=greeks_delta if greeks_delta is not None else position.greeks_delta,
        greeks_theta=greeks_theta if greeks_theta is not None else position.greeks_theta,
        greeks_iv=greeks_iv if greeks_iv is not None else position.greeks_iv,
        entry_at=position.entry_at,
        lot_size=position.lot_size,
        expected_edge_r=position.expected_edge_r,
        direction=position.direction,
        origin=position.origin,
        managed_exit_mode=position.managed_exit_mode,
        operator_action_id=position.operator_action_id,
    )


@dataclass(frozen=True)
class PositionMonitorDecision:
    action: PositionAction
    reason_codes: tuple[str, ...]
    new_trailing_stop: Decimal | None
    should_exit_now: bool


def _capital_pnl_fraction(position: MonitoredPosition) -> Decimal:
    """Compute unrealized PnL as a fraction of capital at risk.

    When capital_at_risk is set (> 0), the stop is based on the total capital
    allocated to the position, not the per-unit entry price.  This gives
    meaningful stop distances for options:
      1.5% of ₹50,000 capital = ₹750 stop (not 1.5% of ₹200 premium = ₹3).
    Falls back to price-based fraction if capital_at_risk is zero.
    """
    if position.current_mark is None:
        return Decimal("0")
    if position.capital_at_risk > 0:
        return position.unrealized_pnl / position.capital_at_risk
    if position.entry_price == 0:
        return Decimal("0")
    return (position.current_mark - position.entry_price) / position.entry_price


def evaluate_position(
    *,
    config: PositionMonitorConfig,
    position: MonitoredPosition,
    hwm: HWMState | None,
    evaluation_time: UTCDateTime,
) -> PositionMonitorDecision:
    _ = evaluation_time
    if position.current_mark is None or not position.data_fresh:
        return PositionMonitorDecision(
            action=PositionAction.NO_DATA,
            reason_codes=("MARK_STALE_OR_MISSING",),
            new_trailing_stop=position.trailing_stop,
            should_exit_now=False,
        )

    pnl_fraction = _capital_pnl_fraction(position)

    if not position.thesis_healthy:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("THESIS_INVALIDATED",),
            new_trailing_stop=None,
            should_exit_now=True,
        )

    hard_loss_breached = (
        position.risk_budget > 0 and position.unrealized_pnl <= -position.risk_budget
    ) or (position.risk_budget <= 0 and pnl_fraction <= -config.hard_loss_fraction)
    if hard_loss_breached:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("HARD_LOSS_BREACH",),
            new_trailing_stop=None,
            should_exit_now=True,
        )

    # --- Options-aware exits ---
    if position.entry_iv is not None and position.greeks_iv is not None and position.entry_iv > 0:
        iv_change = (position.greeks_iv - position.entry_iv) / position.entry_iv
        if iv_change <= -config.iv_collapse_exit_fraction:
            return PositionMonitorDecision(
                action=PositionAction.EXIT,
                reason_codes=("IV_COLLAPSE",),
                new_trailing_stop=None,
                should_exit_now=True,
            )

    if (
        position.greeks_theta is not None
        and position.expected_edge_r > 0
        and position.capital_at_risk > 0
        and position.time_held_minutes > 0
    ):
        # Theta is negative for long options (cost per day).  Estimate
        # cumulative theta bleed in capital terms over the holding period.
        minutes_held = max(1, position.time_held_minutes)
        daily_theta_cost = abs(position.greeks_theta) * float(position.quantity)
        theta_bleed = daily_theta_cost * (minutes_held / 390)  # 390 min trading day
        expected_edge_capital = position.expected_edge_r * float(position.capital_at_risk)
        if (
            expected_edge_capital > 0
            and theta_bleed / expected_edge_capital >= config.theta_bleed_exit_fraction
        ):
            return PositionMonitorDecision(
                action=PositionAction.EXIT,
                reason_codes=("THETA_DECAY_EXCESSIVE",),
                new_trailing_stop=None,
                should_exit_now=True,
            )

    if position.time_held_minutes >= config.max_hold_minutes:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("TIME_EXIT",),
            new_trailing_stop=None,
            should_exit_now=True,
        )

    if hwm is not None and hwm.profit_protection.value == "TRIGGERED" and pnl_fraction > 0:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("HWM_PROFIT_PROTECTION",),
            new_trailing_stop=None,
            should_exit_now=True,
        )

    if position.trailing_stop is not None and position.current_mark <= position.trailing_stop:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("TRAILING_STOP_HIT",),
            new_trailing_stop=position.trailing_stop,
            should_exit_now=True,
        )

    if pnl_fraction >= config.min_profit_for_trailing:
        candidate_stop = position.current_mark * (Decimal("1") - config.trailing_distance_fraction)
        best_stop = candidate_stop
        if position.trailing_stop is not None:
            best_stop = max(position.trailing_stop, candidate_stop)
        no_trail = position.trailing_stop is None
        cur_stop = position.current_stop
        if cur_stop is not None and best_stop <= cur_stop and no_trail:
            return PositionMonitorDecision(
                action=PositionAction.HOLD,
                reason_codes=("HOLD_NO_TIGHTEN",),
                new_trailing_stop=position.trailing_stop,
                should_exit_now=False,
            )
        if best_stop != position.trailing_stop:
            return PositionMonitorDecision(
                action=PositionAction.TRAIL,
                reason_codes=("TRAIL_UPDATE",),
                new_trailing_stop=best_stop,
                should_exit_now=False,
            )

    return PositionMonitorDecision(
        action=PositionAction.HOLD,
        reason_codes=("POSITION_HEALTHY",),
        new_trailing_stop=position.trailing_stop,
        should_exit_now=False,
    )


__all__ = [
    "MonitoredPosition",
    "ManagedExitMode",
    "PositionAction",
    "PositionOrigin",
    "PositionMonitorConfig",
    "PositionMonitorDecision",
    "evaluate_position",
    "update_mark",
]
