"""Build and verify the ATS broker clock profile consumed by the MT5 observer.

The native EA (`metatrader/Experts/ATSSmallAccount/SmallAccountSignals.mqh`)
loads a CSV of `begin,end,offset` rows and resolves every broker timestamp with
`VerifiedUTC`, which accepts a timestamp only when it falls inside EXACTLY ONE
segment. Zero matches or two matches both return -1, and a single -1 anywhere in
the M1 warmup history aborts `LoadSignalBars` entirely. The signal engine then
stays dark.

This module is the only sanctioned producer of that CSV. It does not guess a
broker timezone: offsets must be declared with dated evidence and are then
checked against observed anchors. Its job is to prove, before the file is ever
installed, that no real market bar can land in an ambiguous or uncovered region
of the mapping.

Contract reproduced from the EA, field for field:

* three integer columns per row: begin, end, offset
* ``begin > 0`` and ``end > begin``
* ``abs(offset) <= 14 * 3600`` and ``offset % 60 == 0``
* at most 1024 segments
* rows sorted and non-overlapping in UTC: ``begin >= previous end``
* file no larger than 1 MiB, SHA-256 matching the EA's ``ClockProfileHash`` input
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

MAX_ABS_OFFSET_SECONDS: Final[int] = 14 * 3600
MAX_SEGMENTS: Final[int] = 1024
MAX_PROFILE_BYTES: Final[int] = 1024 * 1024
OFFSET_GRANULARITY_SECONDS: Final[int] = 60

# Default XAUUSD weekend closure, in UTC. Friday 21:00 to Sunday 22:00 is the
# widest window that every broker surveyed keeps shut; narrow it per broker with
# --closure rather than widening it.
DEFAULT_CLOSURE_OPEN_WEEKDAY: Final[int] = 4  # Friday
DEFAULT_CLOSURE_OPEN_SECOND: Final[int] = 21 * 3600
DEFAULT_CLOSURE_SHUT_WEEKDAY: Final[int] = 6  # Sunday
DEFAULT_CLOSURE_SHUT_SECOND: Final[int] = 22 * 3600


class ClockProfileError(Exception):
    """Raised when a profile violates the native EA's loading contract."""


@dataclass(frozen=True)
class Segment:
    """One contiguous UTC window over which the broker offset is constant."""

    begin: int
    end: int
    offset: int

    @property
    def broker_begin(self) -> int:
        """First broker-clock second this segment can explain."""
        return self.begin + self.offset

    @property
    def broker_end(self) -> int:
        """One past the last broker-clock second this segment can explain."""
        return self.end + self.offset

    def describe(self) -> str:
        return (
            f"[{_iso(self.begin)} .. {_iso(self.end)}) "
            f"offset {_hours(self.offset)}"
        )


@dataclass(frozen=True)
class DeadZone:
    """A broker-time range the EA will reject, with the reason it rejects it."""

    broker_begin: int
    broker_end: int
    match_count: int

    @property
    def kind(self) -> str:
        return "UNCOVERED" if self.match_count == 0 else "AMBIGUOUS"

    @property
    def width_seconds(self) -> int:
        return self.broker_end - self.broker_begin


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    magnitude = abs(seconds)
    return f"{sign}{magnitude // 3600:02d}:{(magnitude % 3600) // 60:02d}"


def _parse_utc(value: str) -> int:
    """Parse an explicit UTC timestamp. Naive or non-UTC input is refused."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ClockProfileError(f"not an ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ClockProfileError(
            f"timestamp {value!r} has no timezone; declare UTC explicitly"
        )
    if parsed.utcoffset() != UTC.utcoffset(None):
        raise ClockProfileError(
            f"timestamp {value!r} is not UTC; the profile is defined in UTC only"
        )
    return int(parsed.timestamp())


def validate_segments(segments: Sequence[Segment]) -> None:
    """Enforce every structural rule the EA's LoadClockProfile applies.

    Mirrors the MQL loader exactly. A profile that passes here is one the EA
    will accept; a profile that fails here would have been silently rejected on
    the terminal, leaving `signal_status` at CLOCK_PROFILE_REQUIRED with no
    further explanation.
    """
    if not segments:
        raise ClockProfileError("profile contains no segments")
    if len(segments) > MAX_SEGMENTS:
        raise ClockProfileError(
            f"{len(segments)} segments exceeds the EA's limit of {MAX_SEGMENTS}"
        )
    previous: Segment | None = None
    for index, segment in enumerate(segments):
        where = f"segment {index}"
        if segment.begin <= 0:
            raise ClockProfileError(f"{where}: begin must be positive")
        if segment.end <= segment.begin:
            raise ClockProfileError(f"{where}: end must be strictly after begin")
        if abs(segment.offset) > MAX_ABS_OFFSET_SECONDS:
            raise ClockProfileError(
                f"{where}: offset {segment.offset}s exceeds +/-14h"
            )
        if segment.offset % OFFSET_GRANULARITY_SECONDS != 0:
            raise ClockProfileError(
                f"{where}: offset {segment.offset}s is not a whole number of minutes"
            )
        if previous is not None and segment.begin < previous.end:
            raise ClockProfileError(
                f"{where}: begins before the previous segment ends; "
                "rows must be sorted and non-overlapping in UTC"
            )
        previous = segment


def find_dead_zones(segments: Sequence[Segment]) -> list[DeadZone]:
    """Locate every broker-time range where VerifiedUTC will return -1.

    Segments are non-overlapping in UTC, but once each is shifted by its own
    offset the broker-time images can gap apart or overlap. A gap is a broker
    timestamp no segment explains; an overlap is one that two segments explain
    differently. The EA treats both as fatal, so both are reported here.
    """
    if not segments:
        return []
    boundaries: set[int] = set()
    for segment in segments:
        boundaries.add(segment.broker_begin)
        boundaries.add(segment.broker_end)
    ordered = sorted(boundaries)

    dead: list[DeadZone] = []
    # Pairwise over sorted boundaries; the lengths differ by design.
    for left, right in zip(ordered, ordered[1:], strict=False):
        midpoint = left + (right - left) // 2
        matches = sum(
            1
            for segment in segments
            if segment.broker_begin <= midpoint < segment.broker_end
        )
        if matches == 1:
            continue
        if dead and dead[-1].broker_end == left and dead[-1].match_count == matches:
            merged = dead.pop()
            dead.append(DeadZone(merged.broker_begin, right, matches))
        else:
            dead.append(DeadZone(left, right, matches))
    return dead


def _weekday_second(epoch: int) -> tuple[int, int]:
    moment = datetime.fromtimestamp(epoch, tz=UTC)
    second = moment.hour * 3600 + moment.minute * 60 + moment.second
    return moment.weekday(), second


def is_market_closed(
    epoch: int,
    open_weekday: int = DEFAULT_CLOSURE_OPEN_WEEKDAY,
    open_second: int = DEFAULT_CLOSURE_OPEN_SECOND,
    shut_weekday: int = DEFAULT_CLOSURE_SHUT_WEEKDAY,
    shut_second: int = DEFAULT_CLOSURE_SHUT_SECOND,
) -> bool:
    """Whether a UTC instant falls inside the weekly XAUUSD closure."""
    weekday, second = _weekday_second(epoch)
    start = open_weekday * 86400 + open_second
    stop = shut_weekday * 86400 + shut_second
    position = weekday * 86400 + second
    if start <= stop:
        return start <= position < stop
    return position >= start or position < stop


def assert_dead_zones_are_safe(
    segments: Sequence[Segment],
    *,
    closure: tuple[int, int, int, int] = (
        DEFAULT_CLOSURE_OPEN_WEEKDAY,
        DEFAULT_CLOSURE_OPEN_SECOND,
        DEFAULT_CLOSURE_SHUT_WEEKDAY,
        DEFAULT_CLOSURE_SHUT_SECOND,
    ),
) -> list[DeadZone]:
    """Require every dead zone to sit inside the weekend closure.

    A dead zone is unavoidable wherever the offset changes: the EA's one-match
    rule cannot be satisfied across a discontinuity. It is harmless only if no
    real M1 bar carries a timestamp inside it. Placing each offset change inside
    the weekend closure -- rather than at the broker's actual DST instant -- is
    what makes the profile survivable. This function is the gate that proves it.
    """
    dead = find_dead_zones(segments)
    unsafe: list[str] = []
    for zone in dead:
        # Walk the zone on a one-minute grid: M1 bars can only open on minute
        # boundaries, so this samples every timestamp that could actually occur.
        cursor = zone.broker_begin - (zone.broker_begin % 60)
        while cursor < zone.broker_end:
            if not is_market_closed(cursor, *closure):
                unsafe.append(
                    f"{zone.kind} broker-time window "
                    f"[{_iso(zone.broker_begin)} .. {_iso(zone.broker_end)}) "
                    f"({zone.width_seconds // 60} min) is open-market at "
                    f"{_iso(cursor)}"
                )
                break
            cursor += 60
    if unsafe:
        raise ClockProfileError(
            "offset changes land while the market is open; move the segment "
            "boundary into the weekend closure:\n  - " + "\n  - ".join(unsafe)
        )
    return dead


def verified_utc(segments: Sequence[Segment], broker_time: int) -> int:
    """Pure-Python twin of the EA's VerifiedUTC. Returns -1 on any ambiguity.

    Kept byte-for-byte faithful to the MQL so the parity tests compare like with
    like. Any divergence here would let a profile pass CI and fail on the
    terminal, which is the exact failure this tooling exists to prevent.
    """
    found = -1
    count = 0
    for segment in segments:
        utc = broker_time - segment.offset
        if segment.begin <= utc < segment.end:
            found = utc
            count += 1
    return found if count == 1 else -1


def verify_bar_times(segments: Sequence[Segment], broker_times: Sequence[int]) -> None:
    """Assert every observed broker bar timestamp resolves to exactly one UTC.

    Run this against a real M1 export covering at least HistoryWarmupDays before
    installing a profile. One rejected bar is enough to blank the signal engine,
    and the EA reports only HISTORICAL_CLOCK_OR_PRICE_INVALID when it happens.
    """
    rejected: list[int] = [t for t in broker_times if verified_utc(segments, t) < 0]
    if rejected:
        shown = ", ".join(_iso(t) for t in rejected[:5])
        more = f" (and {len(rejected) - 5} more)" if len(rejected) > 5 else ""
        raise ClockProfileError(
            f"{len(rejected)} of {len(broker_times)} observed bars do not resolve "
            f"to exactly one UTC instant: {shown}{more}"
        )


def check_anchors(
    segments: Sequence[Segment], anchors: Sequence[tuple[int, int, str]]
) -> None:
    """Cross-check the declared offsets against attested simultaneous readings.

    Each anchor is (broker_epoch, attested_utc_epoch, source). The observer EA
    writes these into clock-probe.json as `server_time` and `gmt`, but its own
    comment warns that TimeGMT requires independent validation -- so the UTC side
    must be attested by something other than the terminal before it is used here.
    """
    for broker_epoch, attested_utc, source in anchors:
        resolved = verified_utc(segments, broker_epoch)
        if resolved < 0:
            raise ClockProfileError(
                f"anchor from {source}: broker time {_iso(broker_epoch)} does not "
                "resolve to exactly one UTC instant under this profile"
            )
        if resolved != attested_utc:
            drift = resolved - attested_utc
            raise ClockProfileError(
                f"anchor from {source}: profile maps broker {_iso(broker_epoch)} "
                f"to {_iso(resolved)} but the attested UTC is {_iso(attested_utc)} "
                f"({drift:+d}s). The declared offset is wrong, or the attestation is."
            )


def load_declaration(path: Path) -> tuple[list[Segment], list[tuple[int, int, str]]]:
    """Read the human-authored JSON declaration into segments and anchors."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClockProfileError(f"cannot read declaration {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClockProfileError("declaration must be a JSON object")

    raw_segments = raw.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ClockProfileError("declaration has no 'segments' array")

    segments: list[Segment] = []
    for index, entry in enumerate(raw_segments):
        if not isinstance(entry, dict):
            raise ClockProfileError(f"segment {index} is not an object")
        for key in ("begin_utc", "end_utc", "offset_seconds", "basis"):
            if key not in entry:
                raise ClockProfileError(f"segment {index} is missing '{key}'")
        basis = entry["basis"]
        if not isinstance(basis, str) or not basis.strip():
            raise ClockProfileError(
                f"segment {index}: 'basis' must cite the dated evidence for this "
                "offset. An undocumented offset is a guess and is refused."
            )
        offset = entry["offset_seconds"]
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise ClockProfileError(f"segment {index}: offset_seconds must be an int")
        segments.append(
            Segment(
                begin=_parse_utc(str(entry["begin_utc"])),
                end=_parse_utc(str(entry["end_utc"])),
                offset=offset,
            )
        )

    anchors: list[tuple[int, int, str]] = []
    for index, entry in enumerate(raw.get("anchors", []) or []):
        if not isinstance(entry, dict):
            raise ClockProfileError(f"anchor {index} is not an object")
        for key in ("broker_epoch", "attested_utc", "attested_by"):
            if key not in entry:
                raise ClockProfileError(f"anchor {index} is missing '{key}'")
        attested_by = str(entry["attested_by"])
        if attested_by.strip().upper() in {"", "TERMINAL", "TIMEGMT", "MT5"}:
            raise ClockProfileError(
                f"anchor {index}: the terminal cannot attest its own clock. "
                "Name an independent UTC source."
            )
        broker_epoch = entry["broker_epoch"]
        if not isinstance(broker_epoch, int) or isinstance(broker_epoch, bool):
            raise ClockProfileError(f"anchor {index}: broker_epoch must be an int")
        anchors.append((broker_epoch, _parse_utc(str(entry["attested_utc"])), attested_by))
    return segments, anchors


def render_csv(segments: Sequence[Segment]) -> str:
    """Render the exact bytes the EA will hash and parse.

    No header row: the MQL CSV reader would read it as a data row and fail the
    NumericInteger check. LF endings only, one trailing newline.
    """
    return "".join(f"{s.begin},{s.end},{s.offset}\n" for s in segments)


def read_csv(path: Path) -> list[Segment]:
    """Parse an existing profile CSV back into segments."""
    text = path.read_text(encoding="utf-8")
    segments: list[Segment] = []
    for number, row in enumerate(csv.reader(text.splitlines()), start=1):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue
        if len(row) != 3:
            raise ClockProfileError(f"line {number}: expected 3 columns, got {len(row)}")
        try:
            begin, end, offset = (int(field.strip()) for field in row)
        except ValueError as exc:
            raise ClockProfileError(f"line {number}: non-integer field") from exc
        segments.append(Segment(begin=begin, end=end, offset=offset))
    return segments


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _report(segments: Sequence[Segment], dead: Sequence[DeadZone], digest: str) -> None:
    print(f"segments      : {len(segments)}")
    for segment in segments:
        print(f"  {segment.describe()}")
    if dead:
        print(f"dead zones    : {len(dead)} (all inside the weekend closure)")
        for zone in dead:
            print(
                f"  {zone.kind:<9} broker [{_iso(zone.broker_begin)} .. "
                f"{_iso(zone.broker_end)}) {zone.width_seconds // 60} min"
            )
    else:
        print("dead zones    : none")
    print(f"sha256        : {digest}")
    print()
    print("Set these EA inputs:")
    print("  ClockProfileCsv  = ATS\\SmallAccount\\clock-profile.csv")
    print(f"  ClockProfileHash = {digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clock_profile",
        description="Build and verify the ATS broker clock profile.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build a profile CSV from a declaration")
    build.add_argument("declaration", type=Path)
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--bars", type=Path, help="observed broker M1 epochs, one per line")

    verify = sub.add_parser("verify", help="verify an existing profile CSV")
    verify.add_argument("profile", type=Path)
    verify.add_argument("--expect-hash", type=str)
    verify.add_argument("--bars", type=Path, help="observed broker M1 epochs, one per line")

    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            segments, anchors = load_declaration(args.declaration)
            if not anchors:
                raise ClockProfileError(
                    "declaration has no 'anchors'. A profile without at least one "
                    "independently attested broker/UTC pair is an assumption, not "
                    "evidence, and is refused."
                )
            validate_segments(segments)
            dead = assert_dead_zones_are_safe(segments)
            check_anchors(segments, anchors)
            if args.bars:
                verify_bar_times(segments, _read_bars(args.bars))
            text = render_csv(segments)
            if len(text.encode("utf-8")) > MAX_PROFILE_BYTES:
                raise ClockProfileError("rendered profile exceeds the EA's 1 MiB limit")
            args.out.write_text(text, encoding="utf-8", newline="\n")
            digest = sha256_of(text)
            print(f"wrote         : {args.out}")
            _report(segments, dead, digest)
            return 0

        segments = read_csv(args.profile)
        validate_segments(segments)
        dead = assert_dead_zones_are_safe(segments)
        text = args.profile.read_text(encoding="utf-8")
        digest = sha256_of(text)
        if args.expect_hash and digest != args.expect_hash.strip().lower():
            raise ClockProfileError(
                f"hash mismatch: file is {digest}, EA input says {args.expect_hash}"
            )
        if args.bars:
            verify_bar_times(segments, _read_bars(args.bars))
        _report(segments, dead, digest)
        return 0
    except ClockProfileError as exc:
        print(f"CLOCK_PROFILE_REJECTED: {exc}", file=sys.stderr)
        return 1


def _read_bars(path: Path) -> list[int]:
    values: list[int] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            values.append(int(stripped))
        except ValueError as exc:
            raise ClockProfileError(f"{path}:{number}: not an integer epoch") from exc
    if not values:
        raise ClockProfileError(f"{path} contains no bar timestamps")
    return values


if __name__ == "__main__":
    raise SystemExit(main())
