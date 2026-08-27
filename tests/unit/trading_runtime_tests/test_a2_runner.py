from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.contracts.common import SystemClock
from ats.portfolio.brain import ExposureDirection
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    A2SessionState,
    UpstoxMarketFeedAdapter,
    create_a2_paper_app,
)
from ats.trading_runtime.candidate_factory import build_opportunity_candidate
from fastapi.testclient import TestClient


def test_controller_start_and_stop() -> None:
    config = A2PaperSessionConfig(execution_target="PAPER", live_money="DISABLED")
    controller = A2PaperSessionController(config=config)

    assert controller.state == A2SessionState.STOPPED
    started = controller.start(require_token=False)
    assert started is True
    assert controller.state == A2SessionState.RUNNING
    assert controller.engine is not None

    health = controller.health()
    assert health["status"] == "HEALTHY"
    assert health["live_money"] == "DISABLED"
    assert health["execution_target"] == "PAPER"
    assert health["real_orders_placed"] == 0

    stopped = controller.stop()
    assert stopped is True
    assert controller.state == A2SessionState.STOPPED


def test_double_start_and_double_stop_safety() -> None:
    controller = A2PaperSessionController()
    assert controller.start(require_token=False) is True
    assert controller.start(require_token=False) is True  # Idempotent
    assert controller.state == A2SessionState.RUNNING

    assert controller.stop() is True
    assert controller.stop() is True  # Idempotent
    assert controller.state == A2SessionState.STOPPED


def test_missing_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATS_UPSTOX_ACCESS_TOKEN", raising=False)
    controller = A2PaperSessionController()

    started = controller.start(require_token=True)
    assert started is False
    assert controller.state == A2SessionState.FAILED
    assert "ACCESS_TOKEN_MISSING" in controller.status().reason_codes


def test_live_money_guard() -> None:
    config = A2PaperSessionConfig(execution_target="PAPER", live_money="ENABLED")
    controller = A2PaperSessionController(config=config)

    started = controller.start(require_token=False)
    assert started is False
    assert controller.state == A2SessionState.FAILED
    assert "LIVE_MONEY_PROHIBITED" in controller.status().reason_codes

    with pytest.raises(ValueError, match="live_money == 'DISABLED'"):
        create_a2_paper_app(controller)


def test_paper_broker_execution_only() -> None:
    controller = A2PaperSessionController()
    controller.start(require_token=False)
    now = SystemClock().now()

    candidate = build_opportunity_candidate(
        instrument_id="NIFTY_CE",
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )

    res = controller.evaluate_and_execute_candidate(
        candidate,
        underlying="NIFTY",
        direction=ExposureDirection.BULLISH,
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        maximum_loss=Decimal("5000"),
        expected_net_value=Decimal("50"),
        now=now,
    )

    assert res["allowed"] is True
    assert res["execution_target"] == "PAPER"
    assert "position_id" in res
    assert controller.status().paper_orders_submitted == 1
    assert controller.status().paper_fills_recorded == 1
    assert controller.status().open_paper_positions == 1
    assert controller.status().real_orders_placed == 0


def test_runtime_engine_injected_into_app_state() -> None:
    controller = A2PaperSessionController()
    controller.start(require_token=False)
    app = create_a2_paper_app(controller)

    assert app.state.trading_runtime_engine is not None
    assert app.state.a2_session_controller is controller

    client = TestClient(app)
    resp = client.get("/v1/runtime/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"]["is_halted"] is False
    assert data["broker_healthy"] is True


def test_api_runtime_command_lifecycle() -> None:
    controller = A2PaperSessionController()
    app = create_a2_paper_app(controller)
    client = TestClient(app)

    # Start session via API command
    start_resp = client.post("/v1/runtime/command", json={"command": "START_A2_PAPER_SESSION"})
    assert start_resp.status_code == 200
    assert start_resp.json()["accepted"] is True
    assert controller.state == A2SessionState.RUNNING

    # Stop session via API command
    stop_resp = client.post("/v1/runtime/command", json={"command": "STOP_A2_PAPER_SESSION"})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["accepted"] is True
    assert controller.state == A2SessionState.STOPPED


def test_stop_flattens_open_paper_positions() -> None:
    controller = A2PaperSessionController()
    controller.start(require_token=False)
    now = SystemClock().now()

    candidate = build_opportunity_candidate(
        instrument_id="NIFTY_CE",
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    controller.evaluate_and_execute_candidate(
        candidate,
        underlying="NIFTY",
        requested_capital=Decimal("50000"),
        requested_quantity=Decimal("50"),
        now=now,
    )
    assert len(controller.engine.state.open_positions) == 1

    # Stopping flattens open positions
    controller.stop()
    assert len(controller.engine.state.open_positions) == 0
    assert controller.status().open_paper_positions == 0


def test_multi_position_paper_flow() -> None:
    config = A2PaperSessionConfig(max_positions=2)
    controller = A2PaperSessionController(config=config)
    controller.start(require_token=False)
    now = SystemClock().now()

    # Position 1: NIFTY_CE
    cand1 = build_opportunity_candidate(
        instrument_id="NIFTY_CE",
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    res1 = controller.evaluate_and_execute_candidate(
        cand1, underlying="NIFTY", requested_quantity=Decimal("50"), now=now
    )
    assert res1["allowed"] is True

    # Position 2: BANKNIFTY_CE
    cand2 = build_opportunity_candidate(
        instrument_id="BANKNIFTY_CE",
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    res2 = controller.evaluate_and_execute_candidate(
        cand2, underlying="BANKNIFTY", requested_quantity=Decimal("30"), now=now
    )
    assert res2["allowed"] is True
    assert len(controller.engine.state.open_positions) == 2

    # Position 3 exceeds max_positions=2 -> Rejected safely
    cand3 = build_opportunity_candidate(
        instrument_id="NIFTY_PE",
        campaign_id=uuid4(),
        campaign_version=1,
        strategy_id=uuid4(),
        strategy_version=1,
        market_context_id=uuid4(),
        thesis_id=uuid4(),
        thesis_version=1,
        distribution_id=uuid4(),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    res3 = controller.evaluate_and_execute_candidate(
        cand3, underlying="NIFTY", requested_quantity=Decimal("50"), now=now
    )
    assert res3["allowed"] is False
    assert res3["reason"] == "MAX_CONCURRENT_POSITIONS_REACHED"


def test_process_tick_updates_marks_and_runtime() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)
    now = SystemClock().now()

    res = controller.process_tick("NIFTY", Decimal("24550.00"), at=now)
    assert res["accepted"] is True
    assert feed.latest_mark("NIFTY") == Decimal("24550.00")
    assert controller.status().events_processed == 1


def test_active_nse_session_fsm_and_can_enter(monkeypatch) -> None:
    from datetime import date, datetime, time, timezone

    from ats.market.calendar.models import SessionCalendar

    # Fixed active market time: 11:00 AM IST on trading date
    ist = timezone(timedelta(hours=5, minutes=30))
    test_date = date(2026, 8, 27)
    active_now = datetime(2026, 8, 27, 11, 0, 0, tzinfo=ist)

    # Freeze the wall clock so the session FSM is evaluated at the fixed
    # active time regardless of when the test is executed (after-hours safe).
    class _FixedClock:
        def now(self):
            return active_now

    monkeypatch.setattr("ats.contracts.common.SystemClock", _FixedClock)

    cal = SessionCalendar(
        calendar_id="NSE_TEST",
        calendar_version="1.0",
        timezone="Asia/Kolkata",
        trading_dates=(test_date,),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )

    controller = A2PaperSessionController(calendar=cal)
    controller.start(require_token=False)
    app = create_a2_paper_app(controller)
    client = TestClient(app)

    # Trigger tick at active market time
    controller.process_tick("NIFTY", Decimal("24500.00"), at=active_now)

    resp = client.get("/v1/runtime/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session"]["phase"] == "ENTRY_ALLOWED"
    assert data["session"]["can_enter"] is True
    assert data["session"]["is_halted"] is False
    assert data["feed_healthy"] is True
    assert data["broker_healthy"] is True
