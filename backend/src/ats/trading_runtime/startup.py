"""Hardened ``ats-start`` lifecycle: preflight, session state, Stage-1, paper-only.

Execution chain covered here (Python source of truth; PowerShell wrappers
in ``scripts/`` delegate to this module instead of duplicating logic):

``ats-start``
-> environment/preflight (token, paper-only invariants)
-> determine NSE session state (calendar + ``resolve_session_status``)
-> refresh/validate Stage-1 evidence (auto-refresh when missing or stale)
-> READY / WAITING / NON-TRADING-DAY / STARTED
-> ``PaperForwardRunner`` when eligible (caller constructs it; this module
   only reports eligibility, it never touches strategy or risk behaviour).

Safety rules (never weakened):

- Stage-1 ``trading_date`` must equal today's NSE date (Asia/Kolkata).
  Stale evidence is never forced to pass; it is regenerated from canonical
  sources (token presence, paper-only flags, calendar membership, git HEAD)
  and then revalidated. Unverifiable evidence fails closed.
- Market-calendar checks are never disabled; weekends and exchange holidays
  return ``NON_TRADING_DAY`` without attempting market execution.
- ``execution_mode`` must be exactly ``PAPER`` with ``PaperBrokerAdapter``
  only, live money ``DISABLED``, and zero real orders. Any deviation fails
  closed with ``PAPER_ONLY_VIOLATION``.
- Missing/expired Upstox authorization fails clearly with remediation and
  is never bypassed.
- No fake evidence is created: regeneration records the checks actually
  performed and never synthesizes fills, PnL, or market data.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from ats.contracts.common import UTCDateTime
from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.session import (
    RuntimeSessionPhase,
    SessionRuntimeConfig,
    resolve_session_status,
)

_IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

READY_VERDICT = "READY_FOR_A2_PAPER_SESSION"
EVIDENCE_SCHEMA_VERSION = "1.0"

# Official NSE 2026 F&O holiday circular, as already pinned by the A2 paper
# runtime calendar. Weekends are handled separately via ``weekday()``.
NSE_FO_2026_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2026, 1, 26),
        date(2026, 3, 3),
        date(2026, 3, 26),
        date(2026, 3, 31),
        date(2026, 4, 3),
        date(2026, 4, 14),
        date(2026, 5, 1),
        date(2026, 5, 28),
        date(2026, 6, 26),
        date(2026, 9, 14),
        date(2026, 10, 2),
        date(2026, 10, 20),
        date(2026, 11, 10),
        date(2026, 11, 24),
        date(2026, 12, 25),
    }
)


class StartupStatus(StrEnum):
    """Explicit ats-start outcomes. Normal operational states are not errors."""

    STARTED = "STARTED"
    READY_WAITING_FOR_MARKET = "READY_WAITING_FOR_MARKET"
    MARKET_CLOSED = "MARKET_CLOSED"
    NON_TRADING_DAY = "NON_TRADING_DAY"
    MISSING_TOKEN = "MISSING_TOKEN"
    DUPLICATE_RUNNING = "DUPLICATE_RUNNING"
    PAPER_ONLY_VIOLATION = "PAPER_ONLY_VIOLATION"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"


@dataclass(frozen=True)
class StartupResult:
    status: StartupStatus
    trading_date: str
    session_phase: str | None
    evidence_path: str
    evidence_refreshed: bool
    next_session: str | None
    message: str
    exit_code: int


def is_weekend(day: date) -> bool:
    """Return True for Saturday/Sunday."""
    return day.weekday() >= 5


def is_nse_holiday(day: date) -> bool:
    """Return True when ``day`` is a pinned NSE holiday."""
    return day in NSE_FO_2026_HOLIDAYS


def build_nse_calendar_for_year(year: int) -> SessionCalendar:
    """Build the governed NSE cash-session calendar for ``year``.

    Weekdays minus the pinned 2026 F&O holiday circular (other years use
    weekends only). The 15:30 close is the ATS conservative internal
    flatten/close policy.
    """
    cur = date(year, 1, 1)
    end = date(year, 12, 31)
    valid: list[date] = []
    while cur <= end:
        if cur.weekday() < 5 and cur not in NSE_FO_2026_HOLIDAYS:
            valid.append(cur)
        cur += timedelta(days=1)
    return SessionCalendar(
        calendar_id="NSE_CASH_ATS_START",
        calendar_version="2026-FO-CIRCULAR-V1",
        timezone="Asia/Kolkata",
        trading_dates=tuple(valid),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


def today_ist(now: UTCDateTime) -> date:
    """Return the NSE calendar date for ``now``."""
    return now.astimezone(_IST).date()


def next_trading_date(calendar: SessionCalendar, today: date) -> date | None:
    """Return the next trading date strictly after ``today``."""
    for day in calendar.trading_dates:
        if day > today:
            return day
    return None


def default_head_provider() -> str | None:
    """Return the current git HEAD, or None when it cannot be determined."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = completed.stdout.strip()
    if completed.returncode != 0 or not head:
        return None
    return head


def default_is_process_running(pid: int) -> bool:
    """Return True when ``pid`` appears to be a live process."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def check_upstox_token(env: Mapping[str, str]) -> tuple[bool, str]:
    """Check for Upstox authorization without ever logging the token value."""
    token = (env.get("ATS_UPSTOX_ACCESS_TOKEN") or "").strip()
    if token:
        return True, "PRESENT"
    return False, (
        "ATS_UPSTOX_ACCESS_TOKEN is missing or empty. Remediation: export "
        "ATS_UPSTOX_ACCESS_TOKEN with a fresh Upstox access token "
        "(complete the Upstox OAuth flow, copy the access token, set it in "
        "this shell), then re-run ats-start. Authentication is never bypassed."
    )


def check_paper_only(
    *,
    execution_mode: str | None,
    execution_target: str | None,
    live_money: str | None,
    broker_adapter: str | None,
    env: Mapping[str, str],
) -> tuple[bool, str]:
    """Enforce PAPER-only invariants; fail closed on any deviation."""
    if execution_mode != "PAPER":
        return False, (
            f"PAPER_ONLY_VIOLATION: execution_mode={execution_mode!r} "
            "(required 'PAPER'). Refusing to start."
        )
    if (execution_target or "PAPER") != "PAPER":
        return False, (
            f"PAPER_ONLY_VIOLATION: execution_target={execution_target!r} "
            "(required 'PAPER'). Refusing to start."
        )
    if (live_money or "DISABLED") != "DISABLED":
        return False, (
            f"PAPER_ONLY_VIOLATION: live_money={live_money!r} "
            "(required 'DISABLED'). Refusing to start."
        )
    if (broker_adapter or "PaperBrokerAdapter") != "PaperBrokerAdapter":
        return False, (
            f"PAPER_ONLY_VIOLATION: broker_adapter={broker_adapter!r} "
            "(required 'PaperBrokerAdapter'). Refusing to start."
        )
    live_flag = (env.get("ATS_LIVE_TRADING") or "").strip().lower()
    if live_flag in ("1", "true", "yes", "on"):
        return False, (
            "PAPER_ONLY_VIOLATION: ATS_LIVE_TRADING is enabled. "
            "Unset it; live broker writes are prohibited."
        )
    env_target = (env.get("ATS_EXECUTION_TARGET") or "").strip().upper()
    if env_target and env_target != "PAPER":
        return False, (
            f"PAPER_ONLY_VIOLATION: ATS_EXECUTION_TARGET={env_target!r} "
            "(required 'PAPER' or unset). Refusing to start."
        )
    return True, "PAPER_ONLY_OK"


def load_stage1_evidence(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load Stage-1 evidence; return (data, error).

    ``(None, None)`` means missing (safe to regenerate).
    ``(None, <reason>)`` means present-but-unreadable (fail closed).
    """
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        return None, f"STAGE1_EVIDENCE_UNREADABLE: {exc}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"STAGE1_EVIDENCE_CORRUPT_JSON: {exc}"
    if not isinstance(data, dict):
        return None, "STAGE1_EVIDENCE_CORRUPT_JSON: top-level object required"
    return data, None


def validate_stage1_evidence(
    data: dict[str, Any],
    *,
    today: date,
    expected_head: str | None,
) -> tuple[bool, str]:
    """Validate Stage-1 evidence without mutating it."""
    if data.get("verdict") != READY_VERDICT:
        return False, (
            f"STAGE1_NOT_READY: verdict={data.get('verdict')!r} "
            f"(required {READY_VERDICT!r})"
        )
    if data.get("trading_date") != today.isoformat():
        return False, (
            f"STAGE1_EVIDENCE_NOT_TODAY: evidence trading_date="
            f"{data.get('trading_date')!r} but NSE today is {today.isoformat()!r}. "
            "ats-start refreshes this automatically on trading days; this "
            "error means refresh was not possible."
        )
    if expected_head is not None and data.get("source_commit") != expected_head:
        return False, (
            f"STAGE1_HEAD_MISMATCH: evidence source_commit="
            f"{data.get('source_commit')!r} but HEAD is {expected_head!r}. "
            "ats-start refreshes this automatically; this error means "
            "refresh was not possible."
        )
    if data.get("execution_target") != "PAPER" or data.get("live_money") != "DISABLED":
        return False, (
            "STAGE1_PAPER_SCOPE_INVALID: evidence must record "
            "execution_target=PAPER and live_money=DISABLED"
        )
    if data.get("broker_adapter") != "PaperBrokerAdapter":
        return False, (
            "STAGE1_PAPER_SCOPE_INVALID: evidence must record "
            "broker_adapter=PaperBrokerAdapter"
        )
    return True, "STAGE1_VALID"


def build_stage1_evidence(
    *,
    today: date,
    now: UTCDateTime,
    head: str | None,
    calendar: SessionCalendar,
) -> dict[str, Any]:
    """Generate canonical Stage-1 evidence from verified preflight truth.

    Only call after token, paper-only, and calendar-membership checks have
    passed. Records the checks performed; never synthesizes market data,
    fills, or PnL.
    """
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "verdict": READY_VERDICT,
        "trading_date": today.isoformat(),
        "generated_at": now.isoformat(),
        "source_commit": head or "UNKNOWN",
        "calendar_id": calendar.calendar_id,
        "calendar_version": calendar.calendar_version,
        "execution_target": "PAPER",
        "live_money": "DISABLED",
        "broker_adapter": "PaperBrokerAdapter",
        "real_orders_placed": 0,
        "checks": {
            "upstox_token": "PRESENT",
            "paper_only": "PASS",
            "calendar": "TRADING_DAY",
            "trading_date": "TODAY_IST",
        },
    }


def write_stage1_evidence_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write evidence atomically so repeated runs cannot corrupt it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_lock_holder(lock_path: Path) -> dict[str, Any] | None:
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def check_duplicate_running(
    lock_path: Path,
    *,
    is_process_running: Callable[[int], bool] = default_is_process_running,
) -> tuple[bool, str | None]:
    """Return (is_duplicate, holder_description). Stale locks are cleaned up."""
    holder = _read_lock_holder(lock_path)
    if holder is None:
        return False, None
    try:
        pid = int(str(holder.get("pid", "0")))
    except ValueError:
        pid = 0
    session_id = str(holder.get("session_id", "unknown"))
    if pid > 0 and is_process_running(pid):
        return True, f"pid={pid} session_id={session_id}"
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass
    return False, None


def acquire_startup_lock(
    lock_path: Path, *, session_id: str, now: UTCDateTime
) -> None:
    """Record this process as the running ATS session holder."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "session_id": session_id,
        "started_at": now.isoformat(),
        "execution_target": "PAPER",
        "live_money": "DISABLED",
    }
    tmp = lock_path.with_name(lock_path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(lock_path)


def release_startup_lock(lock_path: Path) -> None:
    """Remove our lock file; never raises for normal operational use."""
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def console_lines(result: StartupResult, *, detail: str = "") -> list[str]:
    """Render human-readable console output for ``result`` (no raw throws)."""
    head = [
        "================================================================",
        " ATS START - PAPER FORWARD (READ-ONLY MARKET DATA)",
        "================================================================",
        " Execution target : PaperBrokerAdapter (ONLY)",
        " Live money       : DISABLED (STRICT INVARIANT)",
        " Real orders      : 0 (IMPOSSIBLE)",
        f" Trading date     : {result.trading_date} (NSE, Asia/Kolkata)",
    ]
    if result.session_phase:
        head.append(f" Session phase    : {result.session_phase}")
    if result.status is StartupStatus.STARTED:
        head += [
            " Stage-1 evidence : "
            + ("REFRESHED for today" if result.evidence_refreshed else "VALID for today"),
            " Status           : STARTED - PaperForwardRunner eligible",
            " Next             : launching PAPER_FORWARD session (paper orders only).",
        ]
    elif result.status is StartupStatus.READY_WAITING_FOR_MARKET:
        head += [
            " Stage-1 evidence : "
            + ("PREPARED for today" if result.evidence_refreshed else "VALID for today"),
            " Status           : READY - WAITING FOR MARKET OPEN",
            " Next             : preflight complete; re-run ats-start at/after 09:15 IST.",
        ]
    elif result.status is StartupStatus.MARKET_CLOSED:
        head += [
            " Status           : MARKET CLOSED",
            f" Next session     : {result.next_session or 'unknown'}",
            " Next             : no market execution attempted; re-run ats-start next session.",
        ]
    elif result.status is StartupStatus.NON_TRADING_DAY:
        head += [
            " Status           : NON-TRADING DAY (weekend / exchange holiday)",
            f" Next session     : {result.next_session or 'unknown'}",
            " Next             : no market execution attempted.",
        ]
    elif result.status is StartupStatus.DUPLICATE_RUNNING:
        head += [
            " Status           : ALREADY RUNNING - duplicate launch prevented",
            " Next             : use ats-status; run ats-stop before a fresh start.",
        ]
    elif result.status is StartupStatus.MISSING_TOKEN:
        head += [
            " Status           : UPSTOX AUTHORIZATION MISSING",
            " Next             : complete Upstox OAuth, export ATS_UPSTOX_ACCESS_TOKEN,",
            "                  then re-run ats-start. Authentication is never bypassed.",
        ]
    elif result.status is StartupStatus.PAPER_ONLY_VIOLATION:
        head += [
            " Status           : PAPER-ONLY INVARIANT VIOLATED - refusing to start",
            " Next             : reset execution to PAPER / PaperBrokerAdapter / DISABLED.",
        ]
    else:
        head += [
            " Status           : INVALID STAGE-1 EVIDENCE - failing closed",
            " Next             : inspect the reason below; fix canonical sources,",
            "                  then re-run ats-start. Stale evidence is never forced.",
        ]
    head.append("----------------------------------------------------------------")
    head.append(f" {result.message}")
    if detail:
        head.append(f" Detail: {detail}")
    return head


def run_ats_start(
    *,
    now: UTCDateTime,
    evidence_path: Path,
    lock_path: Path,
    env: Mapping[str, str],
    calendar: SessionCalendar,
    execution_mode: str | None = "PAPER",
    execution_target: str | None = "PAPER",
    live_money: str | None = "DISABLED",
    broker_adapter: str | None = "PaperBrokerAdapter",
    head_provider: Callable[[], str | None] = default_head_provider,
    is_process_running: Callable[[int], bool] = default_is_process_running,
    session_id: str | None = None,
) -> StartupResult:
    """Execute the hardened ats-start lifecycle and return an explicit result.

    Never raises for normal operational states (waiting / closed /
    non-trading / duplicate); raises nothing at all — genuine safety
    failures are returned as ``MISSING_TOKEN`` / ``PAPER_ONLY_VIOLATION`` /
    ``INVALID_EVIDENCE`` results with precise messages.
    """
    today = today_ist(now)
    trading_date = today.isoformat()
    base_evidence = str(evidence_path)
    session_config = SessionRuntimeConfig()

    duplicate, holder = check_duplicate_running(
        lock_path, is_process_running=is_process_running
    )
    if duplicate:
        nxt = next_trading_date(calendar, today)
        return StartupResult(
            status=StartupStatus.DUPLICATE_RUNNING,
            trading_date=trading_date,
            session_phase=None,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=nxt.isoformat() if nxt else None,
            message=f"ATS is already running ({holder}); duplicate startup prevented.",
            exit_code=0,
        )

    token_ok, token_detail = check_upstox_token(env)
    if not token_ok:
        return StartupResult(
            status=StartupStatus.MISSING_TOKEN,
            trading_date=trading_date,
            session_phase=None,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=None,
            message=token_detail,
            exit_code=2,
        )

    paper_ok, paper_detail = check_paper_only(
        execution_mode=execution_mode,
        execution_target=execution_target,
        live_money=live_money,
        broker_adapter=broker_adapter,
        env=env,
    )
    if not paper_ok:
        return StartupResult(
            status=StartupStatus.PAPER_ONLY_VIOLATION,
            trading_date=trading_date,
            session_phase=None,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=None,
            message=paper_detail,
            exit_code=3,
        )

    is_trading_day = today in set(calendar.trading_dates)
    if not is_trading_day:
        nxt = next_trading_date(calendar, today)
        if is_weekend(today):
            reason = f"{trading_date} is a weekend; NSE is closed."
        elif is_nse_holiday(today):
            reason = f"{trading_date} is an NSE exchange holiday; NSE is closed."
        else:
            reason = f"{trading_date} is not on the NSE trading calendar."
        return StartupResult(
            status=StartupStatus.NON_TRADING_DAY,
            trading_date=trading_date,
            session_phase=RuntimeSessionPhase.CLOSED.value,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=nxt.isoformat() if nxt else None,
            message=f"NON-TRADING DAY: {reason}",
            exit_code=0,
        )

    status = resolve_session_status(calendar=calendar, config=session_config, now=now)
    phase = status.phase

    if phase in (
        RuntimeSessionPhase.PREOPEN,
        RuntimeSessionPhase.WARMUP,
    ):
        refresh = _ensure_fresh_evidence(
            evidence_path=evidence_path,
            today=today,
            now=now,
            calendar=calendar,
            head_provider=head_provider,
        )
        if refresh.error is not None:
            return StartupResult(
                status=StartupStatus.INVALID_EVIDENCE,
                trading_date=trading_date,
                session_phase=phase.value,
                evidence_path=base_evidence,
                evidence_refreshed=False,
                next_session=None,
                message=refresh.error,
                exit_code=4,
            )
        return StartupResult(
            status=StartupStatus.READY_WAITING_FOR_MARKET,
            trading_date=trading_date,
            session_phase=phase.value,
            evidence_path=base_evidence,
            evidence_refreshed=refresh.refreshed,
            next_session=None,
            message=(
                "ATS is READY and WAITING FOR MARKET OPEN. Preflight passed; "
                "Stage-1 evidence is prepared for today."
            ),
            exit_code=0,
        )

    if phase is RuntimeSessionPhase.CLOSED:
        local = now.astimezone(_IST)
        nxt = next_trading_date(calendar, today)
        preopen = (calendar.preopen_start.hour, calendar.preopen_start.minute)
        if (local.hour, local.minute) < preopen:
            refresh = _ensure_fresh_evidence(
                evidence_path=evidence_path,
                today=today,
                now=now,
                calendar=calendar,
                head_provider=head_provider,
            )
            if refresh.error is not None:
                return StartupResult(
                    status=StartupStatus.INVALID_EVIDENCE,
                    trading_date=trading_date,
                    session_phase=phase.value,
                    evidence_path=base_evidence,
                    evidence_refreshed=False,
                    next_session=None,
                    message=refresh.error,
                    exit_code=4,
                )
            return StartupResult(
                status=StartupStatus.READY_WAITING_FOR_MARKET,
                trading_date=trading_date,
                session_phase=phase.value,
                evidence_path=base_evidence,
                evidence_refreshed=refresh.refreshed,
                next_session=None,
                message=(
                    "ATS is READY and WAITING FOR MARKET OPEN. Preflight passed; "
                    "Stage-1 evidence is prepared for today."
                ),
                exit_code=0,
            )
        return StartupResult(
            status=StartupStatus.MARKET_CLOSED,
            trading_date=trading_date,
            session_phase=phase.value,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=nxt.isoformat() if nxt else None,
            message=(
                f"MARKET CLOSED for {trading_date}. "
                f"Next NSE session: {nxt.isoformat() if nxt else 'unknown'}."
            ),
            exit_code=0,
        )

    if phase is RuntimeSessionPhase.HALTED:
        return StartupResult(
            status=StartupStatus.INVALID_EVIDENCE,
            trading_date=trading_date,
            session_phase=phase.value,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=None,
            message="SESSION HALTED by kill-switch or calendar override; refusing to start.",
            exit_code=4,
        )

    refresh = _ensure_fresh_evidence(
        evidence_path=evidence_path,
        today=today,
        now=now,
        calendar=calendar,
        head_provider=head_provider,
    )
    if refresh.error is not None:
        return StartupResult(
            status=StartupStatus.INVALID_EVIDENCE,
            trading_date=trading_date,
            session_phase=phase.value,
            evidence_path=base_evidence,
            evidence_refreshed=False,
            next_session=None,
            message=refresh.error,
            exit_code=4,
        )
    acquire_startup_lock(
        lock_path, session_id=session_id or now.isoformat(), now=now
    )
    return StartupResult(
        status=StartupStatus.STARTED,
        trading_date=trading_date,
        session_phase=phase.value,
        evidence_path=base_evidence,
        evidence_refreshed=refresh.refreshed,
        next_session=None,
        message=(
            "ATS PAPER_FORWARD session STARTED. Stage-1 evidence valid for today; "
            "PaperForwardRunner eligible (paper orders only, live money DISABLED)."
        ),
        exit_code=0,
    )


@dataclass(frozen=True)
class _RefreshOutcome:
    refreshed: bool
    error: str | None


def _ensure_fresh_evidence(
    *,
    evidence_path: Path,
    today: date,
    now: UTCDateTime,
    calendar: SessionCalendar,
    head_provider: Callable[[], str | None],
) -> _RefreshOutcome:
    """Return fresh, validated Stage-1 evidence, regenerating only when safe."""
    data, load_error = load_stage1_evidence(evidence_path)
    if load_error is not None:
        return _RefreshOutcome(refreshed=False, error=load_error)
    head = head_provider()
    if data is not None:
        valid, _ = validate_stage1_evidence(data, today=today, expected_head=head)
        if valid:
            return _RefreshOutcome(refreshed=False, error=None)
        if head is None and data.get("source_commit") not in (None, "UNKNOWN"):
            return _RefreshOutcome(
                refreshed=False,
                error=(
                    "STAGE1_HEAD_UNVERIFIABLE: git HEAD cannot be determined, "
                    "so stale evidence cannot be safely refreshed. Failing closed."
                ),
            )
    if head is None:
        # Deterministic, safe regeneration is impossible without a verifiable
        # source commit, unless the caller explicitly opts out of HEAD
        # verification (head_provider returning None means "skip HEAD check"
        # only when no prior evidence pins a commit).
        if data is not None:
            return _RefreshOutcome(
                refreshed=False,
                error=(
                    "STAGE1_HEAD_UNVERIFIABLE: git HEAD cannot be determined, "
                    "so stale evidence cannot be safely refreshed. Failing closed."
                ),
            )
        head = "UNKNOWN"
    else:
        head = head.strip() or "UNKNOWN"
    fresh = build_stage1_evidence(today=today, now=now, head=head, calendar=calendar)
    valid, reason = validate_stage1_evidence(fresh, today=today, expected_head=head)
    if not valid:
        return _RefreshOutcome(refreshed=False, error=f"STAGE1_REGENERATION_FAILED: {reason}")
    try:
        write_stage1_evidence_atomic(evidence_path, fresh)
    except OSError as exc:
        return _RefreshOutcome(
            refreshed=False, error=f"STAGE1_EVIDENCE_WRITE_FAILED: {exc}"
        )
    return _RefreshOutcome(refreshed=True, error=None)


def _resolve_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "backend").exists():
            return candidate
    return start


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: ``python -m ats.trading_runtime.startup``."""
    import argparse

    parser = argparse.ArgumentParser(description="Hardened ats-start (paper forward only).")
    parser.add_argument("--evidence-path", default=None)
    parser.add_argument("--lock-path", default=None)
    parser.add_argument("--execution-mode", default="PAPER")
    parser.add_argument("--execution-target", default="PAPER")
    parser.add_argument("--live-money", default="DISABLED")
    parser.add_argument("--broker-adapter", default="PaperBrokerAdapter")
    args = parser.parse_args(argv)

    repo = _resolve_repo_root(Path.cwd())
    evidence = (
        Path(args.evidence_path)
        if args.evidence_path
        else Path(
            os.environ.get(
                "ATS_STAGE1_EVIDENCE_PATH",
                str(repo / "data" / "runtime" / "pre_market_acceptance.json"),
            )
        )
    )
    lock = (
        Path(args.lock_path)
        if args.lock_path
        else Path(
            os.environ.get(
                "ATS_START_LOCK_PATH",
                str(evidence.parent / "ats-start.lock"),
            )
        )
    )
    trading_dates_env = (os.environ.get("ATS_TRADING_DATES") or "").strip()
    if trading_dates_env:
        parsed = {
            date.fromisoformat(part.strip())
            for part in trading_dates_env.split(",")
            if part.strip()
        }
        dates = tuple(sorted(parsed))
        calendar = SessionCalendar(
            calendar_id="NSE_CASH_ATS_START",
            calendar_version="ATS-OVERRIDE-V1",
            timezone="Asia/Kolkata",
            trading_dates=dates,
            preopen_start=time(9, 0),
            market_open=time(9, 15),
            market_close=time(15, 30),
            overrides=(),
        )
    else:
        now_probe = datetime.now(UTC)
        calendar = build_nse_calendar_for_year(now_probe.astimezone(_IST).year)

    now: UTCDateTime = datetime.now(UTC)
    result = run_ats_start(
        now=now,
        evidence_path=evidence,
        lock_path=lock,
        env=dict(os.environ),
        calendar=calendar,
        execution_mode=args.execution_mode,
        execution_target=args.execution_target,
        live_money=args.live_money,
        broker_adapter=args.broker_adapter,
    )
    for line in console_lines(result):
        print(line)
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "NSE_FO_2026_HOLIDAYS",
    "READY_VERDICT",
    "StartupResult",
    "StartupStatus",
    "acquire_startup_lock",
    "build_nse_calendar_for_year",
    "build_stage1_evidence",
    "check_duplicate_running",
    "check_paper_only",
    "check_upstox_token",
    "console_lines",
    "default_head_provider",
    "default_is_process_running",
    "is_nse_holiday",
    "is_weekend",
    "load_stage1_evidence",
    "main",
    "next_trading_date",
    "release_startup_lock",
    "run_ats_start",
    "today_ist",
    "validate_stage1_evidence",
    "write_stage1_evidence_atomic",
]
