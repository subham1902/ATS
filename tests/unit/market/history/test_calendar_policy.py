"""Calendar-aware missing-interval detection versus naive gap arithmetic."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone

import pytest
from ats.contracts.domain.types import SessionState
from ats.market.calendar.models import SessionCalendar, SessionOverride
from ats.market.history import (
    HistoricalTruthErrorCode,
    HistoryValidationPolicy,
    validate_market_history,
)

from tests.unit.market.history.fixtures import make_bar_observation

IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
DAY_ONE = date(2024, 6, 3)
DAY_TWO = date(2024, 6, 4)


def _calendar(*dates: date) -> SessionCalendar:
    return SessionCalendar(
        calendar_id="NSE_CASH_TEST",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=tuple(dates),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def _ist_close(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).astimezone(UTC)


def _policy(calendar: SessionCalendar | None) -> HistoryValidationPolicy:
    if calendar is None:
        return HistoryValidationPolicy()
    return HistoryValidationPolicy(session_calendar=calendar)


def test_intra_session_missing_bar_is_flagged_with_calendar() -> None:
    calendar = _calendar(DAY_ONE)
    records = (
        make_bar_observation(sequence=1, event_time=_ist_close(DAY_ONE, 9, 15)),
        make_bar_observation(sequence=2, event_time=_ist_close(DAY_ONE, 9, 40)),
    )
    report = validate_market_history(records, policy=_policy(calendar))
    codes = {finding.code for finding in report.findings}
    assert HistoricalTruthErrorCode.MISSING_INTERVAL in codes


def test_overnight_gap_requires_next_session_preopen_close() -> None:
    """The Monday 09:05 pre-open close is session-eligible and thus required."""

    records = (
        make_bar_observation(sequence=1, event_time=_ist_close(DAY_ONE, 15, 30)),
        make_bar_observation(sequence=2, event_time=_ist_close(DAY_TWO, 9, 15)),
    )
    with_calendar = validate_market_history(records, policy=_policy(_calendar(DAY_ONE, DAY_TWO)))
    without_calendar = validate_market_history(records, policy=_policy(None))
    assert any(
        finding.code is HistoricalTruthErrorCode.MISSING_INTERVAL
        for finding in with_calendar.findings
    )
    assert any(
        finding.code is HistoricalTruthErrorCode.MISSING_INTERVAL
        for finding in without_calendar.findings
    )


def test_fully_halted_window_excuses_every_intermediate_close() -> None:
    halted_times = [_ist_close(DAY_ONE, 9, minute) for minute in (20, 25, 30, 35)]
    calendar = SessionCalendar(
        calendar_id="NSE_CASH_TEST",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(DAY_ONE,),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=tuple(
            SessionOverride(timestamp=halted, state=SessionState.HALTED) for halted in halted_times
        ),
    )
    records = (
        make_bar_observation(sequence=1, event_time=_ist_close(DAY_ONE, 9, 15)),
        make_bar_observation(sequence=2, event_time=_ist_close(DAY_ONE, 9, 40)),
    )
    report = validate_market_history(records, policy=_policy(calendar))
    assert not any(
        finding.code is HistoricalTruthErrorCode.MISSING_INTERVAL for finding in report.findings
    )


def test_naive_policy_still_flags_simple_gap() -> None:
    records = (
        make_bar_observation(sequence=1),
        make_bar_observation(sequence=3),
    )
    report = validate_market_history(records, policy=HistoryValidationPolicy())
    assert any(
        finding.code is HistoricalTruthErrorCode.MISSING_INTERVAL for finding in report.findings
    )


def test_policy_rejects_unsorted_or_duplicate_overrides() -> None:
    from ats.market.history import InstrumentPolicyOverride
    from pydantic import ValidationError

    good = InstrumentPolicyOverride(instrument="AAA", bar_minimum_availability_delay_ms=0)
    late = InstrumentPolicyOverride(instrument="BBB", bar_minimum_availability_delay_ms=0)
    with pytest.raises(ValidationError):
        HistoryValidationPolicy(instrument_overrides=(late, good))
    duplicate_of_good = InstrumentPolicyOverride(
        instrument="AAA", bar_minimum_availability_delay_ms=5
    )
    with pytest.raises(ValidationError):
        HistoryValidationPolicy(instrument_overrides=(good, duplicate_of_good))
