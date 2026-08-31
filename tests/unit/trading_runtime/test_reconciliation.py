"""RECONCILIATION — session-end P&L report correctness and safety.

Covers: profitable/losing sessions, zero-trade session, fees/taxes included,
partial fills, remaining-position failure, zero-loss profit-factor edge case.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.trading_runtime.reconciliation import (
    build_session_reconciliation,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def test_profitable_session() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("105000"),
        fees=Decimal("100"),
        taxes=Decimal("200"),
        slippage=Decimal("50"),
        total_trades=5,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("500"),
        started_at=NOW,
        closed_at=NOW,
        gross_realized_pnl=Decimal("5350"),
        winners=4,
        losers=1,
        largest_winner=Decimal("2000"),
        largest_loser=Decimal("650"),
    )
    assert r.status == "CLOSED"
    assert r.closed_successfully is True
    assert r.net_realized_pnl == Decimal("5000")  # 5350 - 100 - 200 - 50
    assert r.win_rate == Decimal("80")
    assert r.profit_factor is not None and r.profit_factor > 0


def test_losing_session() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("98000"),
        fees=Decimal("50"),
        taxes=Decimal("100"),
        slippage=Decimal("25"),
        total_trades=3,
        rejected_orders=1,
        risk_rejected_candidates=2,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("2000"),
        started_at=NOW,
        closed_at=NOW,
        gross_realized_pnl=Decimal("-1825"),
        winners=0,
        losers=3,
        largest_winner=Decimal("0"),
        largest_loser=Decimal("700"),
    )
    assert r.status == "CLOSED"
    assert r.net_realized_pnl == Decimal("-2000")


def test_zero_trade_session() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("100000"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        slippage=Decimal("0"),
        total_trades=0,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("0"),
        started_at=NOW,
        closed_at=NOW,
    )
    assert r.status == "CLOSED"
    assert r.win_rate is None  # no NaN/Inf
    assert r.profit_factor is None


def test_fees_and_taxes_included_in_net() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("101000"),
        fees=Decimal("10"),
        taxes=Decimal("20"),
        slippage=Decimal("5"),
        total_trades=2,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("100"),
        started_at=NOW,
        closed_at=NOW,
        gross_realized_pnl=Decimal("1000"),
    )
    assert r.net_realized_pnl == Decimal("965")  # 1000 - 10 - 20 - 5


def test_remaining_position_prevents_closed() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("100000"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        slippage=Decimal("0"),
        total_trades=1,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=1,
        max_drawdown=Decimal("0"),
        started_at=NOW,
        closed_at=NOW,
    )
    assert r.status == "NOT_CLOSED"
    assert r.closed_successfully is False
    assert r.balanced is True


def test_balanced_invariant() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("100000"),
        fees=Decimal("10"),
        taxes=Decimal("20"),
        slippage=Decimal("5"),
        total_trades=1,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("0"),
        started_at=NOW,
        closed_at=NOW,
        realized_pnl=Decimal("35"),  # 35 = 10+20+5 so closing == opening
    )
    assert r.balanced is True


def test_zero_loss_profit_factor_edge_case() -> None:
    # zero losses but some winners -> profit factor must not be NaN/Inf/div-zero
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("101000"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        slippage=Decimal("0"),
        total_trades=2,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("0"),
        started_at=NOW,
        closed_at=NOW,
        gross_realized_pnl=Decimal("1000"),
        winners=2,
        losers=0,
        largest_winner=Decimal("500"),
        largest_loser=Decimal("0"),
    )
    assert r.profit_factor is not None
    assert r.profit_factor > 0


def test_report_is_immutable_frozen() -> None:
    r = build_session_reconciliation(
        opening_capital=Decimal("100000"),
        current_equity=Decimal("100000"),
        fees=Decimal("0"),
        taxes=Decimal("0"),
        slippage=Decimal("0"),
        total_trades=0,
        rejected_orders=0,
        risk_rejected_candidates=0,
        emergency_exits=0,
        remaining_positions=0,
        max_drawdown=Decimal("0"),
        started_at=NOW,
        closed_at=NOW,
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        r.opening_capital = Decimal("1")  # type: ignore[misc]
