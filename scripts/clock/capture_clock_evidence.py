"""Capture clock-profile evidence on the operator's Windows machine. Read-only.

Produces the two inputs `clock_profile.py build` needs and cannot obtain itself:

1. An anchor: the broker server time from the observer's `clock-probe.json`,
   paired with an independently attested UTC instant for the same moment.
2. Optionally, the broker-time stamps of real M1 bars, for `--bars`.

Independence is the point. The UTC side comes from an SNTP query, not from the
terminal (`TimeGMT` is explicitly untrusted by the observer) and not from this
PC's clock. The PC clock is used only to measure how old the probe file is,
and that difference cancels any constant error in the PC clock:

    attested_utc = probe_write_moment_on_pc_clock + (ntp_utc - pc_clock)

The M1 export uses the MetaTrader5 package's `initialize`, `copy_rates_range`
and `shutdown` only. This script never imports or calls any order function.

Usage (Windows, with the observer EA attached and running). The probe lives in
the terminal's data folder (File > Open Data Folder) under
MQL5\\Files\\ATS\\SmallAccount\\<account-id>\\clock-probe.json:

    python scripts/clock/capture_clock_evidence.py --probe "<that path>" ^
        --bars-out metatrader/clock/observed-m1-epochs.txt --days 130
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

NTP_UNIX_DELTA: Final[int] = 2_208_988_800
DEFAULT_NTP_SERVERS: Final[tuple[str, ...]] = (
    "time.google.com",
    "time.cloudflare.com",
    "pool.ntp.org",
)
MAX_PROBE_AGE_SECONDS: Final[float] = 10.0
MAX_NTP_ROUND_TRIP_SECONDS: Final[float] = 1.0
MAX_OFFSET_RESIDUAL_SECONDS: Final[float] = 5.0


class CaptureError(Exception):
    """Evidence could not be captured to the required standard."""


@dataclass(frozen=True)
class NtpReading:
    server: str
    offset_seconds: float  # add to the PC clock to obtain UTC
    round_trip_seconds: float


def _ntp_to_unix(raw: bytes) -> float:
    seconds, fraction = struct.unpack("!II", raw)
    return seconds - NTP_UNIX_DELTA + fraction / 2**32


def sntp_query(
    server: str,
    *,
    port: int = 123,
    timeout: float = 3.0,
    clock: Callable[[], float] = time.time,
) -> NtpReading:
    """One SNTP exchange; offset and delay per RFC 4330."""
    packet = b"\x23" + 47 * b"\0"  # LI=0, VN=4, Mode=3 (client)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        t0 = clock()
        sock.sendto(packet, (server, port))
        data, _ = sock.recvfrom(512)
        t3 = clock()
    if len(data) < 48:
        raise CaptureError(f"{server}: short NTP response ({len(data)} bytes)")
    mode = data[0] & 0x7
    stratum = data[1]
    if mode != 4 or not 1 <= stratum <= 15:
        raise CaptureError(f"{server}: not a usable server reply (mode {mode}, stratum {stratum})")
    t1 = _ntp_to_unix(data[32:40])  # server receive
    t2 = _ntp_to_unix(data[40:48])  # server transmit
    offset = ((t1 - t0) + (t2 - t3)) / 2
    delay = (t3 - t0) - (t2 - t1)
    return NtpReading(server=server, offset_seconds=offset, round_trip_seconds=delay)


def best_ntp_reading(
    servers: tuple[str, ...], query: Callable[[str], NtpReading] = sntp_query
) -> NtpReading:
    """Lowest-delay reading across servers; refuses if none is tight enough."""
    readings: list[NtpReading] = []
    failures: list[str] = []
    for server in servers:
        try:
            readings.append(query(server))
        except (OSError, CaptureError) as exc:
            failures.append(f"{server}: {exc}")
    usable = [r for r in readings if 0 <= r.round_trip_seconds <= MAX_NTP_ROUND_TRIP_SECONDS]
    if not usable:
        detail = "; ".join(failures) or "round trips too slow"
        raise CaptureError(f"no usable NTP reading ({detail})")
    return min(usable, key=lambda r: r.round_trip_seconds)


def build_anchor(
    probe_path: Path,
    ntp: NtpReading,
    *,
    clock: Callable[[], float] = time.time,
) -> dict[str, object]:
    """Pair the probe's broker time with NTP-attested UTC for the same moment."""
    try:
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
        written_on_pc_clock = probe_path.stat().st_mtime
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError(f"cannot read probe {probe_path}: {exc}") from exc

    age = clock() - written_on_pc_clock
    if not 0 <= age <= MAX_PROBE_AGE_SECONDS:
        raise CaptureError(
            f"probe is {age:.1f}s old; the observer rewrites it every few seconds. "
            "Is the EA attached, connected, and receiving ticks?"
        )
    if not probe.get("connected"):
        raise CaptureError("probe reports the terminal disconnected")
    server_time = probe.get("server_time")
    if not isinstance(server_time, int) or isinstance(server_time, bool) or server_time <= 0:
        raise CaptureError("probe has no integer server_time")

    attested = written_on_pc_clock + ntp.offset_seconds
    attested_utc = round(attested)
    implied = server_time - attested
    nearest_minute = round(implied / 60) * 60
    residual = implied - nearest_minute
    if abs(residual) > MAX_OFFSET_RESIDUAL_SECONDS:
        raise CaptureError(
            f"broker clock sits {implied:+.1f}s from UTC, {residual:+.1f}s off the nearest "
            "whole minute. The profile requires minute offsets; capture again, and if "
            "this persists the broker clock itself is skewed."
        )
    return {
        "broker_epoch": server_time,
        "attested_utc": datetime.fromtimestamp(attested_utc, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attested_by": (
            f"SNTP {ntp.server} via capture_clock_evidence.py "
            f"(round trip {ntp.round_trip_seconds * 1000:.0f} ms)"
        ),
        "evidence": (
            f"{probe_path.name} server={probe.get('server', '?')} "
            f"observed offset {implied:+.1f}s, nearest minute {nearest_minute:+d}s, "
            f"captured {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        ),
        "_observed_offset_seconds": nearest_minute,
    }


def export_m1_epochs(
    terminal: str, symbol: str, days: int, out: Path, sdk: object | None = None
) -> int:
    """Write broker-time M1 bar opens, one epoch per line. Read-only MT5 calls."""
    if sdk is None:
        try:
            import MetaTrader5 as sdk  # type: ignore[import-not-found,no-redef]
        except ImportError as exc:
            raise CaptureError(
                "MetaTrader5 package not installed (pip install MetaTrader5)"
            ) from exc
    if not sdk.initialize(path=terminal, timeout=10000):  # type: ignore[attr-defined]
        raise CaptureError(f"MetaTrader5.initialize failed: {sdk.last_error()}")  # type: ignore[attr-defined]
    try:
        end = datetime.now(UTC)
        start = datetime.fromtimestamp(end.timestamp() - days * 86400, UTC)
        rates = sdk.copy_rates_range(symbol, sdk.TIMEFRAME_M1, start, end)  # type: ignore[attr-defined]
    finally:
        sdk.shutdown()  # type: ignore[attr-defined]
    if rates is None or len(rates) == 0:
        raise CaptureError(f"no M1 bars returned for {symbol}")
    epochs = [int(r["time"]) for r in rates]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# {symbol} M1 broker-time opens, {len(epochs)} bars, exported "
        f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        + "\n".join(map(str, epochs))
        + "\n",
        encoding="utf-8",
    )
    return len(epochs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture clock-profile evidence (read-only).")
    parser.add_argument("--probe", type=Path, required=True, help="observer clock-probe.json")
    parser.add_argument("--ntp", nargs="+", default=list(DEFAULT_NTP_SERVERS))
    parser.add_argument("--bars-out", type=Path, help="also export M1 broker epochs here")
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--days", type=int, default=130, help=">= HistoryWarmupDays (120)")
    args = parser.parse_args(argv)
    try:
        ntp = best_ntp_reading(tuple(args.ntp))
        anchor = build_anchor(args.probe, ntp)
        offset = anchor.pop("_observed_offset_seconds")
        print("Anchor for the declaration's \"anchors\" array:\n")
        print(json.dumps(anchor, indent=2))
        print(f"\nObserved broker offset now: {offset:+d}s ({offset / 3600:+.2f}h)")
        if args.bars_out:
            n = export_m1_epochs(args.terminal, args.symbol, args.days, args.bars_out)
            print(f"Exported {n} M1 bar times to {args.bars_out}")
        return 0
    except CaptureError as exc:
        print(f"CAPTURE_REJECTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
