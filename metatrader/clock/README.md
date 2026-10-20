# Broker clock profile: MetaQuotes-Demo

Installed 2026-10-20 for the read-only `ATSSmallAccountS3_1000` observer (ATS account
`ACC-1fc15e3b5ea64c70be10de314dd55ca2`, DEMO). After install the observer left
`CLOCK_PROFILE_REQUIRED` and reports `NO_QUALIFYING_RETEST`; `execution_authority` stays `NONE`.

## EXPIRY: the profile ends 2026-10-25T00:00:00Z

The single segment stops at the Sunday of the EU DST change. Before the market reopens after the
2026-10-24/25 weekend the profile must be re-captured and extended, or the observer stops resolving
broker time again. The evidence below cannot tell which DST schedule this server uses next, so
the next segment has to come from bars observed after that weekend:

1. Re-run `scripts/clock/capture_clock_evidence.py` (new anchor + bars) once the market has
   reopened on 2026-10-26.
2. Compare the daily-break start in broker time before and after the weekend (it is 23:00 now).
   A shift of one hour dates an EU change; no shift until the 2026-11-01 weekend dates a US change.
3. Add the next segment from that evidence, rebuild, reinstall, and update the EA hash input.

## Evidence

| Item | Value |
|---|---|
| Anchor | broker 1792521577 = 2026-10-20T15:39:38Z, SNTP time.google.com, offset +10800 s (`evidence/anchor-capture-2026-10-20.txt`) |
| Bars | `observed-m1-epochs.txt` (not committed): 120,986 XAUUSD M1 broker-time opens, 2026-06-12 to 2026-10-20, sha256 `9b9879354bc604505f3f8a11a7f1737c1676cc4dfb48466d3e796fcae48c99e7` |
| Daily break | `infer_offsets.py` found 73 daily-break gaps: 72 start at 23:00 broker time and last 2 h (23:00 to 01:00) on every trading day 2026-06-15 to 2026-10-19, and one is the US Labor Day early close (2026-09-07, 21:30). The break never moved, so the offset was constant and equals the anchor. |
| Profile | `clock-profile.csv` = `1781268000,1792886400,10800`, sha256 `0b5ca25556de43da4268e505833e1820a8e8577f52435497df538abb5ca02c10` |
| Build | `clock_profile.py build ... --bars observed-m1-epochs.txt`: 1 segment, no dead zones, anchor within tolerance, all 120,986 bars resolve to exactly one UTC instant |

### The break does not start at 17:00 New York on this server

`infer_offsets.py` measures each daily break against 17:00 America/New_York, the documented XAUUSD
maintenance break. On MetaQuotes-Demo the break starts at **16:00 New York** in this window, so the
script reports +7200 for every day while the anchor proves +10800. Converting every break start with
the built profile gives 16:00 New York for 72 of 73 days (Labor Day: 14:30) and 17:00 for none.

Older MetaQuotes-Demo bars (2024-09 to 2026-10, from the bot terminal) show the server clock followed
**EU** DST dates in 2024 and 2025: the break moved one hour in broker time only in the weeks between
the US and EU changes. In 2026 it stays at 23:00 broker time through the 2026-03-29 EU change, so
the pattern changed and the next change date is not established. That is why the profile stops at
2026-10-25.

## Files

- `clock-profile.declaration.json`: the human-authored declaration (anchor, segment, basis).
- `clock-profile.csv`: the built profile, installed as `MQL5\Files\ATS\SmallAccount\clock-profile.csv`.
- `evidence/`: capture output.
- `../../scripts/clock/infer_offsets.py`: daily-break offset inference.
