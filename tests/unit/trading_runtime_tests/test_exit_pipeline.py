from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from ats.market.calendar.models import SessionCalendar
from ats.portfolio.runtime import PortfolioRecoveryEvidence, SerializedPortfolioAuthority
from ats.trading_runtime.authority_service import PortfolioAuthorityService
from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
from ats.trading_runtime.engine import RuntimeConfig, TradingRuntime

from tests.unit.portfolio.runtime.helpers import (
    NOW,
    PORTFOLIO_ID,
    FakeTransactionManager,
    policy,
)


def _runtime(*, real_authority: bool = False) -> TradingRuntime:
    calendar = SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )
    authority = None
    if real_authority:
        actor = SerializedPortfolioAuthority(
            transaction_manager=FakeTransactionManager(), policy=policy()
        )
        actor.recover(
            PortfolioRecoveryEvidence(
                portfolio_id=PORTFOLIO_ID,
                reconciled_at=NOW,
                active_commands=(),
                reconciliation_complete=True,
            )
        )
        authority = PortfolioAuthorityService(portfolio_authority=actor)
    runtime = TradingRuntime(
        config=RuntimeConfig(calendar=calendar),
        market_feed=InMemoryMarketFeed(),
        broker=PaperBrokerAdapter(),
        authority=authority,
    )
    runtime.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), NOW)
    return runtime


def test_exit_request_is_idempotent_and_does_not_close_before_fill() -> None:
    runtime = _runtime()
    first = runtime.request_exit("NIFTY:1", NOW, source="DASHBOARD")
    second = runtime.request_exit("NIFTY:1", NOW, source="DASHBOARD")
    assert first["accepted"] and not first["idempotent"]
    assert second["accepted"] and second["idempotent"]
    assert "NIFTY:1" in runtime.state.open_positions
    assert len(runtime.state.pending_exits) == 1
    runtime.handle_exit_fill("NIFTY:1", NOW)
    assert "NIFTY:1" not in runtime.state.open_positions
    assert runtime.state.pending_exits == {}


def test_flatten_is_per_position_idempotent() -> None:
    runtime = _runtime()
    runtime.handle_fill("BANKNIFTY:1", Decimal("200"), Decimal("15"), NOW)
    assert len(runtime.request_flatten(NOW, source="DASHBOARD")) == 2
    repeated = runtime.request_flatten(NOW, source="DASHBOARD")
    assert all(item["idempotent"] for item in repeated)
    assert len(runtime.state.open_positions) == 2
    assert len(runtime.state.pending_exits) == 2


def test_authority_runtime_fails_closed_without_frozen_exit_evidence() -> None:
    runtime = _runtime(real_authority=True)
    result = runtime.request_exit("NIFTY:1", NOW, source="DASHBOARD")
    assert result["accepted"]
    assert not result["authorized"]
    assert "EXIT_EVIDENCE_REQUIRED" in result["reasons"]
    assert "NIFTY:1" in runtime.state.open_positions
