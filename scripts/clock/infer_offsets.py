"""Infer a broker's historical UTC offsets from the XAUUSD daily maintenance break.

The break starts at 17:00 America/New_York every trading day. For each weekday gap in the
broker's M1 bar opens (45 min to 6 h of missing minutes), offset = gap start (broker clock)
minus 17:00 New York that day (as UTC). Consecutive days with the same offset form runs; a
change between runs dates the broker's offset changes.

Usage: python scripts/clock/infer_offsets.py metatrader/clock/observed-m1-epochs.txt
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MIN_GAP = 45 * 60
MAX_GAP = 6 * 3600


@dataclass(frozen=True)
class Run:
    offset: int
    first: date
    last: date
    days: int


def _ny_break_utc(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 17, 0, tzinfo=NY).timestamp())


def daily_gap_offsets(broker_epochs: Sequence[int]) -> list[tuple[date, int]]:
    """(New York trading date, offset seconds rounded to the minute) for every daily-break gap."""
    bars = sorted(set(int(b) for b in broker_epochs))
    out: list[tuple[date, int]] = []
    for prev, nxt in zip(bars, bars[1:], strict=False):
        missing = nxt - prev - 60
        if not MIN_GAP <= missing <= MAX_GAP:
            continue
        start = prev + 60  # first missing minute, broker clock
        naive = datetime.fromtimestamp(start, UTC).date()
        for d in (naive - timedelta(days=1), naive):
            off = start - _ny_break_utc(d)
            if -12 * 3600 <= off < 12 * 3600:
                out.append((d, int(round(off / 60)) * 60))
                break
    return out


def offset_runs(days: Sequence[tuple[date, int]]) -> list[Run]:
    runs: list[Run] = []
    for d, off in days:
        if runs and runs[-1].offset == off:
            r = runs[-1]
            runs[-1] = Run(off, r.first, d, r.days + 1)
        else:
            runs.append(Run(off, d, d, 1))
    return runs


def _read(path: Path) -> list[int]:
    return [int(x) for x in path.read_text().split() if x.strip().lstrip("-").isdigit()]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(__doc__)
        return 2
    days = daily_gap_offsets(_read(Path(args[0])))
    runs = offset_runs(days)
    print(f"{len(days)} daily-break gaps, {len(runs)} runs")
    for r in runs:
        hours = r.offset / 3600
        span = f"{r.first} .. {r.last}  {r.days} days, all agree"
        print(f"offset {r.offset:+6d} s (UTC{hours:+.2f}h)  {span}")
    for a, b in zip(runs, runs[1:], strict=False):
        print(
            f"change {a.offset:+d} -> {b.offset:+d} between "
            f"{a.last} ({a.last:%a}) and {b.first} ({b.first:%a})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
