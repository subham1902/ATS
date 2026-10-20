"""Tests for inferring a broker's historical UTC offsets from the XAUUSD 17:00 New York daily break."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "clock"))

from infer_offsets import daily_gap_offsets, offset_runs  # noqa: E402

NY = ZoneInfo("America/New_York")


def _broker_bars(
    first: date, last: date, offset_of, late_break: frozenset = frozenset()
) -> list[int]:
    """M1 broker epochs for a continuous market: open Sunday 18:00 to Friday 17:00 New York, with a 60-minute break
    from 17:00 New York Monday-Thursday (18:00 on `late_break` dates). `offset_of(utc_epoch)` is the broker offset."""
    bars = []
    t = datetime(first.year, first.month, first.day, tzinfo=NY).astimezone(UTC)
    end = datetime(last.year, last.month, last.day, tzinfo=NY).astimezone(UTC) + timedelta(days=1)
    while t < end:
        ny = t.astimezone(NY)
        wd, hm = ny.weekday(), ny.hour + ny.minute / 60
        closed = wd == 5 or (wd == 4 and hm >= 17) or (wd == 6 and hm < 18)
        start = 18 if ny.date() in late_break else 17
        if not closed and not start <= hm < start + 1:
            u = int(t.timestamp())
            bars.append(u + offset_of(u))
        t += timedelta(minutes=1)
    return sorted(set(bars))


def _ny_plus_7(u: int) -> int:
    return int(datetime.fromtimestamp(u, NY).utcoffset().total_seconds()) + 7 * 3600


def test_offsets_follow_us_dst_for_a_new_york_plus_7_server():
    bars = _broker_bars(date(2026, 2, 23), date(2026, 3, 13), _ny_plus_7)
    days = daily_gap_offsets(bars)
    by_day = {d: off for d, off in days}
    assert by_day[date(2026, 3, 5)] == 7200
    assert by_day[date(2026, 3, 9)] == 10800  # US DST began Sunday 8 March 2026
    runs = offset_runs(days)
    assert [(r.offset, r.first, r.last, r.days) for r in runs] == [
        (7200, date(2026, 2, 23), date(2026, 3, 5), 8),
        (10800, date(2026, 3, 9), date(2026, 3, 12), 4),
    ]


def test_a_single_disagreeing_day_is_its_own_run():
    bars = _broker_bars(
        date(2026, 1, 12), date(2026, 1, 16), lambda u: 7200, frozenset({date(2026, 1, 14)})
    )
    runs = offset_runs(daily_gap_offsets(bars))
    assert [(r.offset, r.days) for r in runs] == [(7200, 2), (10800, 1), (7200, 1)]


def test_short_gaps_and_weekends_are_ignored():
    bars = _broker_bars(date(2026, 1, 12), date(2026, 1, 23), lambda u: 7200)
    bars = [b for b in bars if not 1768500000 <= b < 1768500000 + 20 * 60]  # a 20-minute data hole
    assert len(daily_gap_offsets(bars)) == 8  # Mon-Thu breaks; Friday's merges into the weekend
