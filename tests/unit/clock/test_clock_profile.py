"""Parity tests for the broker clock profile builder.

These assert that the Python twin behaves exactly as the MQL loader and
`VerifiedUTC` do. A divergence would let a profile pass CI and then blank the
signal engine on the terminal with only HISTORICAL_CLOCK_OR_PRICE_INVALID to
show for it.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "clock"))

from clock_profile import (  # noqa: E402
    ClockProfileError,
    Segment,
    assert_dead_zones_are_safe,
    find_dead_zones,
    is_market_closed,
    read_csv,
    render_csv,
    sha256_of,
    validate_segments,
    verified_utc,
    verify_bar_times,
)

HOUR = 3600


def epoch(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp())


# Boundaries sit at 00:00 UTC on a Sunday, inside the weekend closure.
WINTER_TO_SUMMER = epoch("2026-03-29T00:00:00")
SUMMER_TO_WINTER = epoch("2026-10-25T00:00:00")

SAFE_PROFILE = [
    Segment(epoch("2025-10-26T00:00:00"), WINTER_TO_SUMMER, 2 * HOUR),
    Segment(WINTER_TO_SUMMER, SUMMER_TO_WINTER, 3 * HOUR),
    Segment(SUMMER_TO_WINTER, epoch("2027-03-28T00:00:00"), 2 * HOUR),
]


class TestStructuralContract:
    """Every rule the EA's LoadClockProfile enforces."""

    def test_accepts_a_well_formed_profile(self) -> None:
        validate_segments(SAFE_PROFILE)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ClockProfileError, match="no segments"):
            validate_segments([])

    def test_rejects_non_positive_begin(self) -> None:
        with pytest.raises(ClockProfileError, match="begin must be positive"):
            validate_segments([Segment(0, 100, 0)])

    def test_rejects_end_not_after_begin(self) -> None:
        with pytest.raises(ClockProfileError, match="strictly after begin"):
            validate_segments([Segment(100, 100, 0)])

    def test_rejects_offset_beyond_fourteen_hours(self) -> None:
        with pytest.raises(ClockProfileError, match=r"exceeds \+/-14h"):
            validate_segments([Segment(100, 200, 15 * HOUR)])

    def test_accepts_offset_at_the_fourteen_hour_boundary(self) -> None:
        validate_segments([Segment(100, 200, 14 * HOUR)])
        validate_segments([Segment(100, 200, -14 * HOUR)])

    def test_rejects_sub_minute_offset(self) -> None:
        with pytest.raises(ClockProfileError, match="whole number of minutes"):
            validate_segments([Segment(100, 200, 90)])

    def test_rejects_overlapping_rows(self) -> None:
        with pytest.raises(ClockProfileError, match="non-overlapping"):
            validate_segments(
                [Segment(1000, 5000, 0), Segment(4000, 9000, 0)]
            )

    def test_rejects_more_than_the_segment_limit(self) -> None:
        many = [Segment(i * 100 + 1, i * 100 + 50, 0) for i in range(1025)]
        with pytest.raises(ClockProfileError, match="exceeds the EA's limit"):
            validate_segments(many)


class TestVerifiedUtcParity:
    """The one-match rule, which is where this whole design lives or dies."""

    def test_resolves_an_unambiguous_timestamp(self) -> None:
        broker = WINTER_TO_SUMMER + 10 * 86400 + 3 * HOUR
        assert verified_utc(SAFE_PROFILE, broker) == broker - 3 * HOUR

    def test_returns_minus_one_when_nothing_matches(self) -> None:
        assert verified_utc(SAFE_PROFILE, 1) == -1

    def test_returns_minus_one_when_two_segments_match(self) -> None:
        # Fall-back overlap: the hour of broker time immediately after the
        # summer segment's image ends is explained by both neighbours.
        ambiguous = SUMMER_TO_WINTER + 2 * HOUR + 60
        assert verified_utc(SAFE_PROFILE, ambiguous) == -1

    def test_boundaries_are_half_open(self) -> None:
        segment = Segment(1_000_000, 1_000_600, 0)
        assert verified_utc([segment], 1_000_000) == 1_000_000
        assert verified_utc([segment], 1_000_599) == 1_000_599
        assert verified_utc([segment], 1_000_600) == -1


class TestDeadZones:
    def test_offset_change_always_produces_a_dead_zone(self) -> None:
        zones = find_dead_zones(SAFE_PROFILE)
        assert len(zones) == 2
        assert {z.kind for z in zones} == {"UNCOVERED", "AMBIGUOUS"}
        assert all(z.width_seconds == HOUR for z in zones)

    def test_constant_offset_has_no_dead_zone(self) -> None:
        flat = [Segment(1_000_000, 2_000_000, 2 * HOUR)]
        assert find_dead_zones(flat) == []

    def test_weekend_boundary_passes_the_safety_gate(self) -> None:
        assert len(assert_dead_zones_are_safe(SAFE_PROFILE)) == 2

    def test_midweek_boundary_is_rejected(self) -> None:
        # A boundary at the true 01:00 UTC DST instant on a Wednesday would put
        # the ambiguous hour squarely in an open market.
        wednesday = epoch("2026-07-01T01:00:00")
        unsafe = [
            Segment(epoch("2026-01-01T00:00:00"), wednesday, 2 * HOUR),
            Segment(wednesday, epoch("2026-12-01T00:00:00"), 3 * HOUR),
        ]
        with pytest.raises(ClockProfileError, match="open-market"):
            assert_dead_zones_are_safe(unsafe)


class TestMarketClosure:
    @pytest.mark.parametrize(
        ("moment", "closed"),
        [
            ("2026-10-24T22:00:00", True),   # Saturday
            ("2026-10-23T21:30:00", True),   # Friday after the close
            ("2026-10-23T20:30:00", False),  # Friday before the close
            ("2026-10-25T21:00:00", True),   # Sunday before the open
            ("2026-10-25T22:30:00", False),  # Sunday after the open
            ("2026-10-21T12:00:00", False),  # Wednesday midday
        ],
    )
    def test_weekly_closure_window(self, moment: str, closed: bool) -> None:
        assert is_market_closed(epoch(moment)) is closed


class TestObservedBars:
    def test_accepts_bars_that_all_resolve(self) -> None:
        base = WINTER_TO_SUMMER + 30 * 86400 + 3 * HOUR
        verify_bar_times(SAFE_PROFILE, [base + i * 60 for i in range(500)])

    def test_rejects_a_single_unresolvable_bar(self) -> None:
        base = WINTER_TO_SUMMER + 30 * 86400 + 3 * HOUR
        bars = [base + i * 60 for i in range(500)]
        bars.append(SUMMER_TO_WINTER + 2 * HOUR + 120)
        with pytest.raises(ClockProfileError, match="do not resolve"):
            verify_bar_times(SAFE_PROFILE, bars)


class TestRendering:
    def test_csv_has_no_header_and_lf_endings(self) -> None:
        text = render_csv(SAFE_PROFILE)
        assert "\r" not in text
        assert text.endswith("\n")
        first = text.splitlines()[0].split(",")
        assert len(first) == 3 and all(f.lstrip("-").isdigit() for f in first)

    def test_round_trips_through_the_csv(self, tmp_path: Path) -> None:
        path = tmp_path / "clock-profile.csv"
        path.write_text(render_csv(SAFE_PROFILE), encoding="utf-8", newline="\n")
        assert read_csv(path) == SAFE_PROFILE

    def test_hash_is_stable_and_sixty_four_hex(self) -> None:
        digest = sha256_of(render_csv(SAFE_PROFILE))
        assert len(digest) == 64
        assert digest == sha256_of(render_csv(SAFE_PROFILE))
