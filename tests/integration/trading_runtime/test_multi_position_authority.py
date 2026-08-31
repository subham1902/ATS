"""TEST_ONLY multi-position and session-flat — NON_MARKET_DATA fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest


def test_multi_position_shared_authority_no_oversub() -> None:
    from ats.portfolio.runtime import PortfolioRecoveryEvidence, SerializedPortfolioAuthority

    from tests.unit.portfolio.runtime.helpers import (
        NOW,
        PORTFOLIO_ID,
        FakeTransactionManager,
        command,
        policy,
    )

    tm = FakeTransactionManager()
    authority = SerializedPortfolioAuthority(transaction_manager=tm, policy=policy(maximum=3))
    authority.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    r1 = authority.reserve(command(1, market="NIFTY", amount="150000"))
    r2 = authority.reserve(command(2, market="BANKNIFTY", amount="150000"))
    _ = (r1, r2)
    with pytest.raises(Exception, match="partition capital"):
        authority.reserve(command(3, market="NIFTY", amount="200000"))
    snap = authority.snapshot()
    assert snap.active_reservation_count == 2
    assert snap.inflight_capital == Decimal("300000")
    from datetime import timedelta

    authority.release(r1.reservation.reservation_id, updated_at=NOW + timedelta(seconds=10))
    authority.reserve(command(3, market="NIFTY", amount="100000"))
    snap2 = authority.snapshot()
    assert snap2.active_reservation_count == 2


def test_unique_tokens_per_position() -> None:
    from datetime import timedelta

    from ats.kernel.autonomy import construct_autonomy_token, validate_token_eligibility
    from ats.kernel.types import AutonomyTokenPolicy, KernelOutcome

    from tests.unit.contracts.intelligence.fixtures import T0
    from tests.unit.kernel.fixtures import make_kernel_fixture, uid

    x1 = make_kernel_fixture()
    x2 = make_kernel_fixture()
    elig1 = validate_token_eligibility(
        policy=x1["policy"],
        campaign=x1["campaign"],
        campaign_state=x1["campaign_state"],
        market=x1["market"],
        thesis=x1["thesis"],
        distribution=x1["distribution"],
        candidate=x1["candidate"],
        strategy=x1["strategy"],
        context=x1["context"],
        risk_decision=x1["risk_decision"],
        advisory=x1["advisory"],
        packet=x1["packet"],
        binding=x1["binding"],
        constraints=x1["constraints"],
        campaign_facts=x1["campaign_facts"],
        capital_basis=x1["basis"],
        execution_safety=x1["safety"],
        evaluation_time=T0,
        maximum_freshness_ms=1000,
        current_system_state_version=1,
        model_family="model",
        model_version="1",
        calibrator_version="1",
    )
    elig2 = validate_token_eligibility(
        policy=x2["policy"],
        campaign=x2["campaign"],
        campaign_state=x2["campaign_state"],
        market=x2["market"],
        thesis=x2["thesis"],
        distribution=x2["distribution"],
        candidate=x2["candidate"],
        strategy=x2["strategy"],
        context=x2["context"],
        risk_decision=x2["risk_decision"],
        advisory=x2["advisory"],
        packet=x2["packet"],
        binding=x2["binding"],
        constraints=x2["constraints"],
        campaign_facts=x2["campaign_facts"],
        capital_basis=x2["basis"],
        execution_safety=x2["safety"],
        evaluation_time=T0,
        maximum_freshness_ms=1000,
        current_system_state_version=1,
        model_family="model",
        model_version="1",
        calibrator_version="1",
    )
    assert elig1.outcome is KernelOutcome.ALLOW
    assert elig2.outcome is KernelOutcome.ALLOW
    t1 = construct_autonomy_token(
        eligibility=elig1,
        token_id=uid(901),
        candidate=x1["candidate"],
        policy=x1["policy"],
        risk_decision=x1["risk_decision"],
        advisory=x1["advisory"],
        context=x1["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="n1",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )
    t2 = construct_autonomy_token(
        eligibility=elig2,
        token_id=uid(902),
        candidate=x2["candidate"],
        policy=x2["policy"],
        risk_decision=x2["risk_decision"],
        advisory=x2["advisory"],
        context=x2["context"],
        issued_at=T0,
        expires_at=T0 + timedelta(seconds=30),
        nonce="n2",
        token_policy=AutonomyTokenPolicy(max_ttl_ms=30000),
    )
    assert t1.token_id != t2.token_id
    assert t1.nonce != t2.nonce


def test_independent_positions_one_exits_one_remains() -> None:
    from datetime import date, time

    from ats.market.calendar.models import SessionCalendar
    from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
    from ats.trading_runtime.engine import RuntimeConfig, TradingRuntime

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
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(
        year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0
    )
    rt = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    rt.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), now)
    rt.handle_fill("BANKNIFTY:1", Decimal("200"), Decimal("15"), now)
    rt.handle_exit("NIFTY:1", now)
    assert "NIFTY:1" not in rt.state.open_positions
    assert "BANKNIFTY:1" in rt.state.open_positions


def test_session_flat_invariants() -> None:
    from datetime import date, time

    from ats.market.calendar.models import SessionCalendar
    from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
    from ats.trading_runtime.engine import (
        RuntimeConfig,
        RuntimeEvent,
        RuntimeEventKind,
        TradingRuntime,
    )

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
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    rt = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    open_time = datetime(2024, 6, 3, 5, 0, tzinfo=UTC)
    feed.set_mark("NIFTY", Decimal("100"), open_time)
    rt.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), open_time)
    assert len(rt.state.open_positions) == 1
    flatten_time = datetime(2024, 6, 3, 9, 58, tzinfo=UTC)
    feed.set_mark("NIFTY", Decimal("100"), flatten_time)
    result = rt.process_event(
        RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=flatten_time)
    )
    assert result["session_phase"] == "FLATTENING"
    assert "exits" in result
    for exit_req in result["exits"]:
        rt.handle_exit(exit_req["position_id"], flatten_time)
    assert len(rt.state.open_positions) == 0
    closed_time = datetime(2024, 6, 3, 10, 30, tzinfo=UTC)
    feed.set_mark("NIFTY", Decimal("100"), closed_time)
    closed_result = rt.process_event(
        RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=closed_time)
    )
    assert closed_result["session_phase"] == "CLOSED"
    assert len(rt.state.open_positions) == 0
