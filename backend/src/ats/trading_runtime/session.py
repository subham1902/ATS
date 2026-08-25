"""Runtime session controller — time-driven transitions over frozen SessionState."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta, timezone
from enum import StrEnum

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import SessionState
from ats.market.calendar.models import SessionCalendar

_INDIA_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


class RuntimeSessionPhase(StrEnum):
    PREOPEN = "PREOPEN"
    WARMUP = "WARMUP"
    ENTRY_ALLOWED = "ENTRY_ALLOWED"
    EXIT_ONLY = "EXIT_ONLY"
    FLATTENING = "FLATTENING"
    CLOSED = "CLOSED"
    HALTED = "HALTED"


_RUNTIME_TO_FROZEN: dict[RuntimeSessionPhase, SessionState] = {
    RuntimeSessionPhase.PREOPEN: SessionState.PREOPEN,
    RuntimeSessionPhase.WARMUP: SessionState.PREOPEN,
    RuntimeSessionPhase.ENTRY_ALLOWED: SessionState.OPEN,
    RuntimeSessionPhase.EXIT_ONLY: SessionState.OPEN,
    RuntimeSessionPhase.FLATTENING: SessionState.OPEN,
    RuntimeSessionPhase.CLOSED: SessionState.CLOSED,
    RuntimeSessionPhase.HALTED: SessionState.HALTED,
}


@dataclass(frozen=True)
class SessionRuntimeConfig:
    warmup_bars: int = 2
    exit_only_before_close_minutes: int = 15
    flattening_before_close_minutes: int = 5
    kill_switch_halted: bool = False


@dataclass(frozen=True)
class SessionStatus:
    phase: RuntimeSessionPhase
    frozen_state: SessionState
    can_enter: bool
    can_reduce: bool
    must_flatten: bool
    is_halted: bool


def resolve_session_status(
    *,
    calendar: SessionCalendar,
    config: SessionRuntimeConfig,
    now: UTCDateTime,
    kill_switch_active: bool = False,
) -> SessionStatus:
    if kill_switch_active or config.kill_switch_halted:
        return SessionStatus(
            phase=RuntimeSessionPhase.HALTED,
            frozen_state=SessionState.HALTED,
            can_enter=False,
            can_reduce=True,
            must_flatten=True,
            is_halted=True,
        )
    frozen = calendar.state_at(now)
    if frozen is SessionState.HALTED:
        return SessionStatus(
            phase=RuntimeSessionPhase.HALTED,
            frozen_state=SessionState.HALTED,
            can_enter=False,
            can_reduce=True,
            must_flatten=True,
            is_halted=True,
        )
    if frozen is SessionState.CLOSED:
        return SessionStatus(
            phase=RuntimeSessionPhase.CLOSED,
            frozen_state=SessionState.CLOSED,
            can_enter=False,
            can_reduce=False,
            must_flatten=False,
            is_halted=False,
        )
    local = now.astimezone(_INDIA_TZ)
    local_time = local.timetz().replace(tzinfo=None)
    assert isinstance(local_time, time)
    if frozen is SessionState.PREOPEN:
        if config.warmup_bars > 0:
            warmup_cutoff_minutes = config.warmup_bars * 5
            preopen_elapsed = (
                local_time.hour * 60
                + local_time.minute
                - calendar.preopen_start.hour * 60
                - calendar.preopen_start.minute
            )
            if preopen_elapsed < warmup_cutoff_minutes:
                return SessionStatus(
                    phase=RuntimeSessionPhase.WARMUP,
                    frozen_state=SessionState.PREOPEN,
                    can_enter=False,
                    can_reduce=False,
                    must_flatten=False,
                    is_halted=False,
                )
        return SessionStatus(
            phase=RuntimeSessionPhase.PREOPEN,
            frozen_state=SessionState.PREOPEN,
            can_enter=False,
            can_reduce=False,
            must_flatten=False,
            is_halted=False,
        )
    close_minutes = calendar.market_close.hour * 60 + calendar.market_close.minute
    now_minutes = local_time.hour * 60 + local_time.minute
    minutes_to_close = close_minutes - now_minutes
    if minutes_to_close <= config.flattening_before_close_minutes:
        return SessionStatus(
            phase=RuntimeSessionPhase.FLATTENING,
            frozen_state=SessionState.OPEN,
            can_enter=False,
            can_reduce=True,
            must_flatten=True,
            is_halted=False,
        )
    if minutes_to_close <= config.exit_only_before_close_minutes:
        return SessionStatus(
            phase=RuntimeSessionPhase.EXIT_ONLY,
            frozen_state=SessionState.OPEN,
            can_enter=False,
            can_reduce=True,
            must_flatten=False,
            is_halted=False,
        )
    return SessionStatus(
        phase=RuntimeSessionPhase.ENTRY_ALLOWED,
        frozen_state=SessionState.OPEN,
        can_enter=True,
        can_reduce=True,
        must_flatten=False,
        is_halted=False,
    )


__all__ = ["RuntimeSessionPhase", "SessionRuntimeConfig", "SessionStatus", "resolve_session_status"]
