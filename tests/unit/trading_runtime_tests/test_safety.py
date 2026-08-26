from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from ats.contracts.domain.types import LossState
from ats.market.calendar.models import SessionCalendar
from ats.trading_runtime.safety import SafetyFacts, SafetyVerdict, evaluate_p0_safety
from ats.trading_runtime.session import SessionRuntimeConfig, resolve_session_status


def _open_facts(**overrides: object) -> SafetyFacts:
    cal = SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )
    now = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    session = resolve_session_status(calendar=cal, config=SessionRuntimeConfig(), now=now)
    base: dict[str, object] = {
        "session": session,
        "kill_switch_active": False,
        "data_fresh": True,
        "broker_healthy": True,
        "capital_ok": True,
        "clock_healthy": True,
        "position_max_loss_breached": False,
        "daily_loss_limit_breached": False,
        "loss_state": LossState.NORMAL,
        "open_positions": (),
        "current_equity": Decimal("100000"),
        "peak_equity": Decimal("100000"),
    }
    base.update(overrides)
    return SafetyFacts(**base)  # type: ignore[arg-type]


def test_allow_when_all_green() -> None:
    result = evaluate_p0_safety(facts=_open_facts(), evaluation_time=datetime.now(UTC))
    assert result.verdict == SafetyVerdict.ALLOW_NEW_RISK
    assert not result.block_new_risk


def test_stale_blocks_new_risk_but_not_halted() -> None:
    result = evaluate_p0_safety(
        facts=_open_facts(data_fresh=False), evaluation_time=datetime.now(UTC)
    )
    assert result.verdict == SafetyVerdict.BLOCK_NEW_RISK
    assert result.block_new_risk
    assert not result.is_halted


def test_kill_switch_halts() -> None:
    result = evaluate_p0_safety(
        facts=_open_facts(kill_switch_active=True), evaluation_time=datetime.now(UTC)
    )
    assert result.verdict == SafetyVerdict.HALT
    assert result.is_halted
