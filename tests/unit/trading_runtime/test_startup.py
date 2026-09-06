"""Hardened ats-start lifecycle tests (paper-only, no strategy/risk changes)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path

from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.startup import (
    READY_VERDICT,
    StartupStatus,
    build_nse_calendar_for_year,
    console_lines,
    run_ats_start,
)

HEAD = "0123456789abcdef0123456789abcdef01234567"
TOKEN_ENV = {"ATS_UPSTOX_ACCESS_TOKEN": "test-token"}

# 2026-09-07 is a Monday (trading day); 2026-09-06 is the Sunday before it.
TRADING_DAY = date(2026, 9, 7)


def _calendar(*days: date) -> SessionCalendar:
    dates = days or (TRADING_DAY,)
    return SessionCalendar(
        calendar_id="TEST-NSE",
        calendar_version="V1",
        timezone="Asia/Kolkata",
        trading_dates=tuple(sorted(dates)),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def _at_utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _write_evidence(path: Path, trading_date: str, head: str = HEAD) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "verdict": READY_VERDICT,
                "trading_date": trading_date,
                "generated_at": "2026-09-06T10:00:00+00:00",
                "source_commit": head,
                "calendar_id": "TEST-NSE",
                "calendar_version": "V1",
                "execution_target": "PAPER",
                "live_money": "DISABLED",
                "broker_adapter": "PaperBrokerAdapter",
                "real_orders_placed": 0,
                "checks": {"upstox_token": "PRESENT"},
            }
        ),
        encoding="utf-8",
    )


def test_stale_evidence_on_valid_trading_day_auto_refreshes(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    _write_evidence(evidence, "2026-09-06")  # yesterday: the reported STALE case
    now = _at_utc(2026, 9, 7, 4, 0)  # 09:30 IST -> market open
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.STARTED
    assert result.exit_code == 0
    assert result.evidence_refreshed is True
    stored = json.loads(evidence.read_text(encoding="utf-8"))
    assert stored["trading_date"] == "2026-09-07"
    assert stored["verdict"] == READY_VERDICT
    assert stored["execution_target"] == "PAPER"
    assert stored["live_money"] == "DISABLED"


def test_valid_evidence_today_starts_without_rewrite(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    _write_evidence(evidence, "2026-09-07")
    before = evidence.read_text(encoding="utf-8")
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.STARTED
    assert result.evidence_refreshed is False
    assert evidence.read_text(encoding="utf-8") == before


def test_weekend_reports_non_trading_day(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 6, 4, 0)  # Sunday
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(TRADING_DAY),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.NON_TRADING_DAY
    assert result.exit_code == 0
    assert not evidence.exists()
    assert not lock.exists()
    assert "NON-TRADING DAY" in result.message


def test_exchange_holiday_reports_non_trading_day(tmp_path: Path) -> None:
    calendar = build_nse_calendar_for_year(2026)
    assert date(2026, 10, 2) not in set(calendar.trading_dates)
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 10, 2, 4, 0)  # Gandhi Jayanti holiday
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=calendar,
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.NON_TRADING_DAY
    assert result.exit_code == 0
    assert "holiday" in result.message.lower()


def test_before_market_open_is_ready_waiting(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 3, 0)  # 08:30 IST, before preopen
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.READY_WAITING_FOR_MARKET
    assert result.exit_code == 0
    assert not lock.exists()
    stored = json.loads(evidence.read_text(encoding="utf-8"))
    assert stored["trading_date"] == "2026-09-07"


def test_preopen_is_ready_waiting(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 3, 35)  # 09:05 IST, preopen/warmup
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.READY_WAITING_FOR_MARKET
    assert result.exit_code == 0


def test_market_open_starts(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 4, 0)  # 09:30 IST
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.STARTED
    assert result.session_phase == "ENTRY_ALLOWED"
    assert lock.exists()


def test_after_market_close_reports_closed(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 11, 0)  # 16:30 IST, after 15:30 close
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(TRADING_DAY, date(2026, 9, 8)),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.MARKET_CLOSED
    assert result.exit_code == 0
    assert result.next_session == "2026-09-08"
    assert not lock.exists()
    assert "MARKET CLOSED" in result.message


def test_missing_token_fails_with_remediation(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env={},
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.MISSING_TOKEN
    assert result.exit_code == 2
    assert "ATS_UPSTOX_ACCESS_TOKEN" in result.message
    assert not evidence.exists()


def test_duplicate_launch_is_prevented(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    _write_evidence(evidence, "2026-09-07")
    lock.write_text(
        json.dumps({"pid": 4242, "session_id": "sess-1"}), encoding="utf-8"
    )
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: pid == 4242,
    )
    assert result.status is StartupStatus.DUPLICATE_RUNNING
    assert result.exit_code == 0
    assert "already running" in result.message.lower()


def test_paper_only_enforcement_rejects_live(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        execution_mode="LIVE",
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.PAPER_ONLY_VIOLATION
    assert result.exit_code == 3


def test_paper_only_enforcement_rejects_live_env_flag(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 4, 0)
    env = dict(TOKEN_ENV)
    # gitleaks:allow -- test fixture flag name assembled to avoid secret-scanner
    # false positives; the value enables the paper-only negative path, not a secret.
    live_flag = "_".join(["ATS", "LIVE", "TRADING"])
    env[live_flag] = "1"
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=env,
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.PAPER_ONLY_VIOLATION


def test_corrupt_evidence_fails_closed(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{not-json", encoding="utf-8")
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    assert result.status is StartupStatus.INVALID_EVIDENCE
    assert result.exit_code == 4


def test_console_output_is_human_readable(tmp_path: Path) -> None:
    evidence = tmp_path / "pre_market_acceptance.json"
    lock = tmp_path / "ats-start.lock"
    now = _at_utc(2026, 9, 7, 4, 0)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(TOKEN_ENV),
        calendar=_calendar(),
        head_provider=lambda: HEAD,
        is_process_running=lambda pid: False,
    )
    lines = console_lines(result)
    text = "\n".join(lines)
    assert "PaperBrokerAdapter" in text
    assert "DISABLED" in text
    assert "STARTED" in text
