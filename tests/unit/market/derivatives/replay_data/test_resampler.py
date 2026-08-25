from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from ats.market.calendar import SessionCalendar
from ats.market.derivatives.replay_data import (
    OneMinuteDerivativeBar,
    resample_one_minute_to_five,
)
from pydantic import ValidationError

IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
SESSION = date(2026, 8, 24)


def calendar(*, extra_date: date | None = None) -> SessionCalendar:
    dates = (SESSION,) if extra_date is None else (SESSION, extra_date)
    return SessionCalendar(
        calendar_id="TEST_ONLY_NSE_FO",
        calendar_version="1.0.0-test",
        timezone="Asia/Kolkata",
        trading_dates=dates,
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def minute(index: int, **changes: object) -> OneMinuteDerivativeBar:
    price = Decimal("100") + index
    values = {
        "instrument_id": "TEST_ONLY_NIFTY_CE",
        "minute_start": datetime(2026, 8, 24, 9, 15, tzinfo=IST) + timedelta(minutes=index),
        "open": price,
        "high": price + Decimal("2"),
        "low": price - Decimal("1"),
        "close": price + Decimal("1"),
        "volume": Decimal(index + 1),
        "open_interest": Decimal(1000 + index),
    }
    values.update(changes)
    return OneMinuteDerivativeBar.model_validate(values)


def test_exact_ohlcv_and_last_oi_rules() -> None:
    result = resample_one_minute_to_five(tuple(minute(i) for i in range(5)), calendar=calendar())
    bar = result.bars[0]
    assert bar.open == Decimal("100")
    assert bar.high == Decimal("106")
    assert bar.low == Decimal("99")
    assert bar.close == Decimal("105")
    assert bar.volume == Decimal("15")
    assert bar.open_interest == Decimal("1004")
    assert bar.bar_close.astimezone(IST).time() == time(9, 20)
    assert not result.excluded_buckets


def test_incomplete_bucket_is_explicitly_excluded_without_fill() -> None:
    result = resample_one_minute_to_five(
        (minute(0), minute(1), minute(3), minute(4)), calendar=calendar()
    )
    assert not result.bars
    assert result.excluded_buckets[0].actual_minute_count == 4
    assert result.excluded_buckets[0].missing_minute_starts[0].astimezone(IST).time() == time(9, 17)


def test_entirely_missing_bucket_is_explicitly_excluded() -> None:
    source = tuple(minute(i) for i in range(5)) + tuple(minute(i) for i in range(10, 15))
    result = resample_one_minute_to_five(source, calendar=calendar())
    assert len(result.bars) == 2
    assert result.excluded_buckets[0].actual_minute_count == 0
    assert len(result.excluded_buckets[0].missing_minute_starts) == 5


def test_future_suffix_does_not_change_completed_prefix() -> None:
    prefix = tuple(minute(i) for i in range(5))
    first = resample_one_minute_to_five(prefix, calendar=calendar())
    with_future = resample_one_minute_to_five(
        prefix + tuple(minute(i) for i in range(5, 10)), calendar=calendar()
    )
    assert with_future.bars[0] == first.bars[0]


def test_identical_input_is_byte_deterministic() -> None:
    bars = tuple(minute(i) for i in range(10))
    first = resample_one_minute_to_five(bars, calendar=calendar())
    second = resample_one_minute_to_five(bars, calendar=calendar())
    assert first.model_dump_json() == second.model_dump_json()


def test_duplicate_and_out_of_order_minutes_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        resample_one_minute_to_five((minute(0), minute(0)), calendar=calendar())
    with pytest.raises(ValueError, match="strictly ordered"):
        resample_one_minute_to_five((minute(1), minute(0)), calendar=calendar())


def test_cross_session_and_outside_session_rejected() -> None:
    next_day = date(2026, 8, 25)
    other = minute(0, minute_start=datetime(2026, 8, 25, 9, 15, tzinfo=IST))
    with pytest.raises(ValueError, match="cross-session"):
        resample_one_minute_to_five((minute(0), other), calendar=calendar(extra_date=next_day))
    before_open = minute(0, minute_start=datetime(2026, 8, 24, 9, 14, tzinfo=IST))
    with pytest.raises(ValueError, match="outside configured market session"):
        resample_one_minute_to_five((before_open,), calendar=calendar())


def test_timezone_binding_normalizes_to_utc_deterministically() -> None:
    result = resample_one_minute_to_five(tuple(minute(i) for i in range(5)), calendar=calendar())
    assert result.bars[0].bar_close.tzinfo is UTC
    assert result.bars[0].bar_close == datetime(2026, 8, 24, 3, 50, tzinfo=UTC)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("volume", Decimal("-1")),
        ("open_interest", Decimal("-1")),
        ("close", Decimal("NaN")),
        ("high", Decimal("Infinity")),
    ),
)
def test_nonfinite_or_negative_source_values_rejected(field: str, value: Decimal) -> None:
    with pytest.raises(ValidationError):
        minute(0, **{field: value})
