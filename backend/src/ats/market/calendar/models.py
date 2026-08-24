"""Minimal explicit calendar semantics for deterministic Alpha replay."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, SessionState, ensure_unique

_INDIA_STANDARD_TIME = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


class SessionOverride(ATSBaseModel):
    timestamp: UTCDateTime
    state: Literal[SessionState.CLOSED, SessionState.HALTED]


class SessionCalendar(ATSBaseModel):
    """Explicit calendar with session-anchored five-minute close semantics."""

    calendar_id: NonEmptyStr
    calendar_version: NonEmptyStr
    timezone: Literal["Asia/Kolkata"]
    trading_dates: tuple[date, ...]
    preopen_start: time
    market_open: time
    market_close: time
    overrides: tuple[SessionOverride, ...]

    @model_validator(mode="after")
    def validate_calendar(self) -> SessionCalendar:
        if not self.trading_dates:
            raise ValueError("trading_dates must be non-empty")
        ensure_unique(self.trading_dates, "trading_dates")
        if tuple(sorted(self.trading_dates)) != self.trading_dates:
            raise ValueError("trading_dates must be strictly ordered")
        if not self.preopen_start < self.market_open < self.market_close:
            raise ValueError("session boundaries must be strictly ordered")
        timestamps = tuple(item.timestamp for item in self.overrides)
        ensure_unique(timestamps, "override timestamps")
        if tuple(sorted(timestamps)) != timestamps:
            raise ValueError("overrides must be strictly ordered")
        return self

    def state_at(self, timestamp: UTCDateTime) -> SessionState:
        for item in self.overrides:
            if item.timestamp == timestamp:
                return SessionState(item.state)
        local = timestamp.astimezone(_INDIA_STANDARD_TIME)
        if local.date() not in self.trading_dates:
            return SessionState.CLOSED
        local_time = local.timetz().replace(tzinfo=None)
        if self.preopen_start < local_time <= self.market_open:
            return SessionState.PREOPEN
        if self.market_open < local_time <= self.market_close:
            return SessionState.OPEN
        return SessionState.CLOSED

    def validate_bar_close(
        self,
        timestamp: UTCDateTime,
        declared_state: SessionState,
    ) -> None:
        actual = self.state_at(timestamp)
        if actual is not declared_state:
            raise ValueError(f"calendar state is {actual.value}, not {declared_state.value}")
        if any(item.timestamp == timestamp for item in self.overrides):
            return
        if actual not in (SessionState.PREOPEN, SessionState.OPEN):
            raise ValueError("CLOSED/HALTED bars require an explicit calendar override")
        local = timestamp.astimezone(_INDIA_STANDARD_TIME)
        if local.second or local.microsecond:
            raise ValueError("bar close must have zero seconds and microseconds")
        anchor_time = self.preopen_start if actual is SessionState.PREOPEN else self.market_open
        anchor = datetime.combine(local.date(), anchor_time, tzinfo=local.tzinfo)
        elapsed_seconds = int((local - anchor).total_seconds())
        if elapsed_seconds <= 0 or elapsed_seconds % 300:
            raise ValueError("bar close is not aligned to the configured five-minute session")


def nse_cash_alpha_v1_calendar() -> SessionCalendar:
    """Return the explicit calendar used by the committed Alpha replay fixture."""
    return SessionCalendar(
        calendar_id="NSE_CASH_ALPHA",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


__all__ = ["SessionCalendar", "SessionOverride", "nse_cash_alpha_v1_calendar"]
