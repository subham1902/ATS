"""P1 position monitor — fast per-position state with trailing stop and HWM awareness."""

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


@dataclass(frozen=True)
class PositionMonitorConfig:
    hard_loss_fraction: Decimal = Decimal("0.015")
    trailing_distance_fraction: Decimal = Decimal("0.008")
    profit_protection_fraction: Decimal = Decimal("0.02")
    max_hold_minutes: int = 90
    min_profit_for_trailing: Decimal = Decimal("0.004")


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


@dataclass(frozen=True)
class PositionMonitorDecision:
    action: PositionAction
    reason_codes: tuple[str, ...]
    new_trailing_stop: Decimal | None
    should_exit_now: bool


def _unrealized_pnl_fraction(entry: Decimal, mark: Decimal, quantity: Decimal) -> Decimal:
    if entry == 0:
        return Decimal("0")
    return (mark - entry) / entry


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

    pnl_fraction = _unrealized_pnl_fraction(
        position.entry_price, position.current_mark, position.quantity
    )

    if not position.thesis_healthy:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("THESIS_INVALIDATED",),
            new_trailing_stop=None,
            should_exit_now=True,
        )

    if pnl_fraction <= -config.hard_loss_fraction:
        return PositionMonitorDecision(
            action=PositionAction.EXIT,
            reason_codes=("HARD_LOSS_BREACH",),
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
    "PositionAction",
    "PositionMonitorConfig",
    "PositionMonitorDecision",
    "evaluate_position",
]
