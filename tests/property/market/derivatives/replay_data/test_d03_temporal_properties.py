from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from ats.market.calendar import SessionCalendar
from ats.market.derivatives.replay_data import (
    OneMinuteDerivativeBar,
    resample_one_minute_to_five,
)

IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def calendar() -> SessionCalendar:
    return SessionCalendar(
        calendar_id="TEST_ONLY_PROPERTY_CALENDAR",
        calendar_version="1.0.0-test",
        timezone="Asia/Kolkata",
        trading_dates=(date(2026, 8, 24),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def bars(count: int, *, offset: int = 0) -> tuple[OneMinuteDerivativeBar, ...]:
    result = []
    for index in range(count):
        sequence = index + offset
        value = Decimal(100 + sequence)
        result.append(
            OneMinuteDerivativeBar(
                instrument_id="TEST_ONLY_PROPERTY_OPTION",
                minute_start=datetime(2026, 8, 24, 9, 15, tzinfo=IST) + timedelta(minutes=sequence),
                open=value,
                high=value + 1,
                low=value - 1,
                close=value,
                volume=Decimal(sequence),
                open_interest=Decimal(1000 + sequence),
            )
        )
    return tuple(result)


@pytest.mark.parametrize("completed_bucket_count", range(1, 8))
def test_any_future_suffix_preserves_every_completed_prefix(
    completed_bucket_count: int,
) -> None:
    prefix = bars(completed_bucket_count * 5)
    expected = resample_one_minute_to_five(prefix, calendar=calendar()).bars
    for future_count in range(1, 10):
        actual = resample_one_minute_to_five(
            prefix + bars(future_count, offset=len(prefix)), calendar=calendar()
        ).bars
        assert actual[: len(expected)] == expected


@pytest.mark.parametrize("completed_bucket_count", range(1, 12))
def test_resample_output_is_monotonic_and_finite(completed_bucket_count: int) -> None:
    result = resample_one_minute_to_five(bars(completed_bucket_count * 5), calendar=calendar())
    closes = tuple(item.bar_close for item in result.bars)
    assert closes == tuple(sorted(closes))
    for item in result.bars:
        assert all(
            value.is_finite()
            for value in (
                item.open,
                item.high,
                item.low,
                item.close,
                item.volume,
                item.open_interest,
            )
        )
