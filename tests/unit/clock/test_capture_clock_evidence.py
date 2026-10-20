"""Tests for the read-only clock evidence capture tool."""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "clock"))

from capture_clock_evidence import (  # noqa: E402
    NTP_UNIX_DELTA,
    CaptureError,
    NtpReading,
    best_ntp_reading,
    build_anchor,
    export_m1_epochs,
    sntp_query,
)
from clock_profile import (  # noqa: E402
    ClockProfileError,
    Segment,
    check_anchors,
)

HOUR = 3600


def _ntp_bytes(unix: float) -> bytes:
    seconds = int(unix) + NTP_UNIX_DELTA
    fraction = int((unix - int(unix)) * 2**32)
    return struct.pack("!II", seconds, fraction)


@pytest.fixture
def fake_ntp_server() -> Iterator[tuple[int, list[float]]]:
    """Local SNTP server whose clock runs `skew` seconds ahead of time.time()."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    skew: list[float] = [0.0]
    stop = threading.Event()

    def serve() -> None:
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                _, addr = sock.recvfrom(512)
            except TimeoutError:
                continue
            import time

            now = time.time() + skew[0]
            reply = bytearray(48)
            reply[0] = 0x24  # VN=4, Mode=4 (server)
            reply[1] = 2  # stratum
            reply[32:40] = _ntp_bytes(now)
            reply[40:48] = _ntp_bytes(now)
            sock.sendto(bytes(reply), addr)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    yield sock.getsockname()[1], skew
    stop.set()
    worker.join(timeout=2)
    sock.close()


class TestSntp:
    def test_recovers_a_known_clock_error(self, fake_ntp_server: tuple[int, list[float]]) -> None:
        port, skew = fake_ntp_server
        skew[0] = 123.25
        reading = sntp_query("127.0.0.1", port=port, timeout=2)
        assert reading.offset_seconds == pytest.approx(123.25, abs=0.05)
        assert 0 <= reading.round_trip_seconds < 0.5

    def test_rejects_a_client_mode_reply(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))

        def echo() -> None:
            data, addr = sock.recvfrom(512)
            sock.sendto(data, addr)  # mode 3 back: not a server

        threading.Thread(target=echo, daemon=True).start()
        with pytest.raises(CaptureError, match="not a usable server reply"):
            sntp_query("127.0.0.1", port=sock.getsockname()[1], timeout=2)
        sock.close()

    def test_best_reading_prefers_lowest_delay_and_skips_failures(self) -> None:
        def query(server: str) -> NtpReading:
            if server == "down":
                raise OSError("timed out")
            delay = {"slow": 0.4, "fast": 0.02, "awful": 3.0}[server]
            return NtpReading(server, offset_seconds=1.0, round_trip_seconds=delay)

        best = best_ntp_reading(("down", "slow", "fast", "awful"), query)
        assert best.server == "fast"

    def test_refuses_when_nothing_is_tight_enough(self) -> None:
        def query(server: str) -> NtpReading:
            return NtpReading(server, offset_seconds=0.0, round_trip_seconds=2.5)

        with pytest.raises(CaptureError, match="no usable NTP reading"):
            best_ntp_reading(("a", "b"), query)


def _probe(tmp_path: Path, *, server_time: int, written: float, connected: bool = True) -> Path:
    path = tmp_path / "clock-probe.json"
    path.write_text(
        json.dumps({"server_time": server_time, "connected": connected, "server": "Demo-Srv"}),
        encoding="utf-8",
    )
    os.utime(path, (written, written))
    return path


class TestAnchor:
    # PC clock is 7.4s slow; NTP says so. Broker runs UTC+3.
    PC_WRITE = 1_790_000_000.0
    NTP = NtpReading("time.example", offset_seconds=7.4, round_trip_seconds=0.03)

    def test_builds_an_anchor_that_the_profile_accepts(self, tmp_path: Path) -> None:
        true_utc = self.PC_WRITE + 7.4
        probe = _probe(tmp_path, server_time=int(true_utc) + 3 * HOUR, written=self.PC_WRITE)
        anchor = build_anchor(probe, self.NTP, clock=lambda: self.PC_WRITE + 2)

        assert anchor["broker_epoch"] == int(true_utc) + 3 * HOUR
        assert anchor["_observed_offset_seconds"] == 3 * HOUR
        assert "SNTP time.example" in str(anchor["attested_by"])

        attested = int(
            datetime.fromisoformat(str(anchor["attested_utc"]).replace("Z", "+00:00")).timestamp()
        )
        profile = [Segment(1_700_000_000, 1_900_000_000, 3 * HOUR)]
        check_anchors(profile, [(int(anchor["broker_epoch"]), attested, "test")])

    def test_wrong_declared_offset_is_still_caught(self, tmp_path: Path) -> None:
        true_utc = self.PC_WRITE + 7.4
        probe = _probe(tmp_path, server_time=int(true_utc) + 3 * HOUR, written=self.PC_WRITE)
        anchor = build_anchor(probe, self.NTP, clock=lambda: self.PC_WRITE + 2)
        attested = int(
            datetime.fromisoformat(str(anchor["attested_utc"]).replace("Z", "+00:00")).timestamp()
        )
        wrong = [Segment(1_700_000_000, 1_900_000_000, 2 * HOUR)]
        with pytest.raises(ClockProfileError, match="declared offset"):
            check_anchors(wrong, [(int(anchor["broker_epoch"]), attested, "test")])

    def test_stale_probe_is_refused(self, tmp_path: Path) -> None:
        probe = _probe(tmp_path, server_time=1_790_010_800, written=self.PC_WRITE)
        with pytest.raises(CaptureError, match="old"):
            build_anchor(probe, self.NTP, clock=lambda: self.PC_WRITE + 60)

    def test_disconnected_terminal_is_refused(self, tmp_path: Path) -> None:
        probe = _probe(tmp_path, server_time=1_790_010_800, written=self.PC_WRITE, connected=False)
        with pytest.raises(CaptureError, match="disconnected"):
            build_anchor(probe, self.NTP, clock=lambda: self.PC_WRITE + 1)

    def test_broker_clock_off_the_minute_grid_is_refused(self, tmp_path: Path) -> None:
        true_utc = self.PC_WRITE + 7.4
        skewed = int(true_utc) + 3 * HOUR + 20  # 20s off a whole minute
        probe = _probe(tmp_path, server_time=skewed, written=self.PC_WRITE)
        with pytest.raises(CaptureError, match="nearest whole minute"):
            build_anchor(probe, self.NTP, clock=lambda: self.PC_WRITE + 1)


class TestAnchorTolerance:
    PROFILE = [Segment(1_700_000_000, 1_900_000_000, 3 * HOUR)]
    BROKER = 1_800_000_000 + 3 * HOUR

    def test_measurement_slack_within_tolerance_passes(self) -> None:
        check_anchors(self.PROFILE, [(self.BROKER, 1_800_000_000 + 4, "ntp")])
        check_anchors(self.PROFILE, [(self.BROKER, 1_800_000_000 - 5, "ntp")])

    def test_beyond_tolerance_fails(self) -> None:
        with pytest.raises(ClockProfileError, match="tolerance 5s"):
            check_anchors(self.PROFILE, [(self.BROKER, 1_800_000_000 + 6, "ntp")])

    def test_tolerance_cannot_be_widened_past_half_a_minute(self) -> None:
        with pytest.raises(ClockProfileError, match=r"\[0, 30\)"):
            check_anchors(self.PROFILE, [], tolerance_seconds=30)


class _FakeSdk:
    TIMEFRAME_M1 = 1

    def __init__(self, times: list[int]) -> None:
        self.times = times
        self.calls: list[str] = []

    def initialize(self, **_: object) -> bool:
        self.calls.append("initialize")
        return True

    def copy_rates_range(self, *_: object) -> list[dict[str, int]]:
        self.calls.append("copy_rates_range")
        return [{"time": t} for t in self.times]

    def shutdown(self) -> None:
        self.calls.append("shutdown")

    def last_error(self) -> tuple[int, str]:
        return (0, "")

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"capture tool touched forbidden SDK member {name!r}")


class TestExport:
    def test_writes_epochs_and_uses_only_read_calls(self, tmp_path: Path) -> None:
        sdk = _FakeSdk([1_790_000_040, 1_790_000_100, 1_790_000_160])
        out = tmp_path / "bars.txt"
        assert export_m1_epochs("terminal", "XAUUSD", 130, out, sdk=sdk) == 3
        assert sdk.calls == ["initialize", "copy_rates_range", "shutdown"]
        lines = [ln for ln in out.read_text().splitlines() if not ln.startswith("#")]
        assert lines == ["1790000040", "1790000100", "1790000160"]

    def test_empty_history_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(CaptureError, match="no M1 bars"):
            export_m1_epochs("t", "XAUUSD", 130, tmp_path / "b.txt", sdk=_FakeSdk([]))

    def test_shutdown_runs_even_if_the_read_fails(self, tmp_path: Path) -> None:
        sdk = _FakeSdk([])

        def boom(*_: object) -> None:
            raise RuntimeError("ipc dropped")

        sdk.copy_rates_range = boom  # type: ignore[method-assign]
        with pytest.raises(RuntimeError):
            export_m1_epochs("t", "XAUUSD", 130, tmp_path / "b.txt", sdk=sdk)
        assert sdk.calls[-1] == "shutdown"


def test_capture_script_never_names_an_order_function() -> None:
    source = (
        Path(__file__).resolve().parents[3] / "scripts" / "clock" / "capture_clock_evidence.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("order_send", "order_check", "positions_get", "orders_get"):
        assert forbidden not in source
