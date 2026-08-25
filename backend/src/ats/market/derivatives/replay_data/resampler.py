"""Session-anchored deterministic 1-minute to 5-minute resampling."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ats.market.calendar import SessionCalendar

from .models import (
    FiveMinuteDerivativeBar,
    IncompleteBucketEvidence,
    OneMinuteDerivativeBar,
    ResampleResult,
)

_IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
_MINUTE = timedelta(minutes=1)


def resample_one_minute_to_five(
    bars: tuple[OneMinuteDerivativeBar, ...], *, calendar: SessionCalendar
) -> ResampleResult:
    if not bars:
        return ResampleResult(bars=(), excluded_buckets=())
    _validate_input(bars, calendar)
    instrument_id = bars[0].instrument_id
    buckets: dict[datetime, list[OneMinuteDerivativeBar]] = defaultdict(list)
    for bar in bars:
        local = bar.minute_start.astimezone(_IST)
        anchor = datetime.combine(local.date(), calendar.market_open, tzinfo=_IST)
        offset_minutes = int((local - anchor).total_seconds() // 60)
        bucket_start = anchor + timedelta(minutes=(offset_minutes // 5) * 5)
        buckets[bucket_start].append(bar)

    complete: list[FiveMinuteDerivativeBar] = []
    excluded: list[IncompleteBucketEvidence] = []
    bucket_start = min(buckets)
    final_bucket_start = max(buckets)
    while bucket_start <= final_bucket_start:
        source = buckets.get(bucket_start, [])
        expected = tuple(bucket_start + index * _MINUTE for index in range(5))
        actual = {item.minute_start.astimezone(_IST) for item in source}
        missing = tuple(item for item in expected if item not in actual)
        bucket_close = bucket_start + timedelta(minutes=5)
        if missing:
            excluded.append(
                IncompleteBucketEvidence(
                    instrument_id=instrument_id,
                    bucket_close=bucket_close,
                    actual_minute_count=len(source),
                    missing_minute_starts=missing,
                    disposition="EXCLUDED_FROM_AUTHORITATIVE_REPLAY",
                )
            )
            bucket_start += timedelta(minutes=5)
            continue
        complete.append(
            FiveMinuteDerivativeBar(
                instrument_id=instrument_id,
                bar_close=bucket_close,
                timeframe="5m",
                open=source[0].open,
                high=max(item.high for item in source),
                low=min(item.low for item in source),
                close=source[-1].close,
                volume=sum((item.volume for item in source), start=source[0].volume * 0),
                open_interest=source[-1].open_interest,
                source_minute_count=5,
                quality="COMPLETE",
            )
        )
        bucket_start += timedelta(minutes=5)
    return ResampleResult(bars=tuple(complete), excluded_buckets=tuple(excluded))


def _validate_input(bars: tuple[OneMinuteDerivativeBar, ...], calendar: SessionCalendar) -> None:
    instrument_id = bars[0].instrument_id
    timestamps = tuple(item.minute_start for item in bars)
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("duplicate minute timestamp")
    if timestamps != tuple(sorted(timestamps)):
        raise ValueError("one-minute bars must be strictly ordered")
    dates: set[object] = set()
    for bar in bars:
        if bar.instrument_id != instrument_id:
            raise ValueError("one resample call accepts one instrument only")
        local = bar.minute_start.astimezone(_IST)
        dates.add(local.date())
        if local.date() not in calendar.trading_dates:
            raise ValueError("bar is outside configured trading dates")
        local_time = local.timetz().replace(tzinfo=None)
        if not calendar.market_open <= local_time < calendar.market_close:
            raise ValueError("bar is outside configured market session")
    if len(dates) != 1:
        raise ValueError("cross-session resampling is forbidden")


__all__ = ["resample_one_minute_to_five"]
