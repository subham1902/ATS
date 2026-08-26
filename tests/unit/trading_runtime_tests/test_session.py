from __future__ import annotations

from datetime import UTC, date, datetime, time

from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.session import (
    RuntimeSessionPhase,
    SessionRuntimeConfig,
    resolve_session_status,
)


def _calendar() -> SessionCalendar:
    return SessionCalendar(
        calendar_id="TEST",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def test_entry_allowed_during_open() -> None:
    cal = _calendar()
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=4, minute=0, second=0, microsecond=0
    )
    status = resolve_session_status(calendar=cal, config=SessionRuntimeConfig(), now=ts)
    assert status.phase == RuntimeSessionPhase.ENTRY_ALLOWED
    assert status.can_enter
    assert not status.must_flatten


def test_exit_only_before_close() -> None:
    cal = _calendar()
    # IST 15:20 -> 15 min before close -> EXIT_ONLY
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=9, minute=50, second=0, microsecond=0
    )
    status = resolve_session_status(calendar=cal, config=SessionRuntimeConfig(), now=ts)
    assert status.phase == RuntimeSessionPhase.EXIT_ONLY
    assert not status.can_enter
    assert status.can_reduce
    assert not status.must_flatten


def test_flattening_before_close() -> None:
    cal = _calendar()
    # IST 15:28 -> 2 min before close -> FLATTENING
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=9, minute=58, second=0, microsecond=0
    )
    status = resolve_session_status(calendar=cal, config=SessionRuntimeConfig(), now=ts)
    assert status.phase == RuntimeSessionPhase.FLATTENING
    assert status.must_flatten


def test_closed_outside_trading_date() -> None:
    cal = _calendar()
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=4, hour=5, minute=0, second=0, microsecond=0
    )
    status = resolve_session_status(calendar=cal, config=SessionRuntimeConfig(), now=ts)
    assert status.phase == RuntimeSessionPhase.CLOSED
    assert not status.can_enter
    assert not status.can_reduce


def test_halted_on_kill_switch() -> None:
    cal = _calendar()
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    status = resolve_session_status(
        calendar=cal, config=SessionRuntimeConfig(), now=ts, kill_switch_active=True
    )
    assert status.phase == RuntimeSessionPhase.HALTED
    assert status.is_halted


def test_preopen_warmup() -> None:
    cal = _calendar()
    # IST 09:02 -> preopen warmup (2 bars = 10 min)
    ts = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=3, minute=32, second=0, microsecond=0
    )
    status = resolve_session_status(
        calendar=cal, config=SessionRuntimeConfig(warmup_bars=2), now=ts
    )
    assert status.phase == RuntimeSessionPhase.WARMUP
