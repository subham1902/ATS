from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.types import LossState
from ats.persistence import (
    CapitalReservationStateError,
    DuplicateCapitalReservationError,
    InsufficientCapitalError,
    PostgresTransaction,
)
from ats.portfolio.persistence import (
    CapitalReservationRequest,
    CapitalReservationState,
    PortfolioCapitalAccount,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("60000000-0000-0000-0000-000000000001")
CAMPAIGN_ID = UUID("60000000-0000-0000-0000-000000000002")


def account() -> PortfolioCapitalAccount:
    return PortfolioCapitalAccount(
        portfolio_id=PORTFOLIO_ID,
        version=1,
        total_capital=Decimal("500000"),
        deployable_capital=Decimal("500000"),
        reserved_capital=Decimal("0"),
        used_capital=Decimal("0"),
        available_capital=Decimal("500000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        daily_loss=Decimal("0"),
        maximum_drawdown=Decimal("0"),
        loss_state=LossState.NORMAL,
        updated_at=NOW,
    )


def request(index: int, amount: str = "200000") -> CapitalReservationRequest:
    return CapitalReservationRequest(
        reservation_id=UUID(f"61000000-0000-0000-0000-{index:012d}"),
        portfolio_id=PORTFOLIO_ID,
        campaign_id=CAMPAIGN_ID,
        candidate_id=UUID(f"62000000-0000-0000-0000-{index:012d}"),
        instrument_id="NIFTY-CE",
        amount=Decimal(amount),
        requested_at=NOW + timedelta(seconds=index),
    )


def initialize(pg_connection) -> None:
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.create_account(account())


def test_two_reservations_succeed_and_third_fails_current_balance(pg_connection) -> None:
    initialize(pg_connection)
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        first = transaction.capital.reserve(request(1))
    assert first.account.available_capital == Decimal("300000")
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        second = transaction.capital.reserve(request(2))
    assert second.account.available_capital == Decimal("100000")
    with pytest.raises(InsufficientCapitalError):
        with PostgresTransaction(pg_connection, close_connection=False) as transaction:
            transaction.capital.reserve(request(3))
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        current = transaction.capital.get_account(PORTFOLIO_ID)
    assert current is not None
    assert current.reserved_capital == Decimal("400000")
    assert current.available_capital == Decimal("100000")


def test_commit_moves_reserved_to_used_without_changing_available(pg_connection) -> None:
    initialize(pg_connection)
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        reserved = transaction.capital.reserve(request(1, "100000"))
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        committed = transaction.capital.commit(
            reserved.reservation.reservation_id, updated_at=NOW + timedelta(minutes=1)
        )
    assert committed.reservation.state is CapitalReservationState.COMMITTED
    assert committed.account.reserved_capital == 0
    assert committed.account.used_capital == Decimal("100000")
    assert committed.account.available_capital == Decimal("400000")


def test_release_returns_reserved_or_used_capital(pg_connection) -> None:
    initialize(pg_connection)
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        first = transaction.capital.reserve(request(1, "100000"))
        second = transaction.capital.reserve(request(2, "200000"))
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.commit(first.reservation.reservation_id, updated_at=NOW + timedelta(1))
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.release(first.reservation.reservation_id, updated_at=NOW + timedelta(2))
        final = transaction.capital.release(
            second.reservation.reservation_id, updated_at=NOW + timedelta(2)
        )
    assert final.account.reserved_capital == 0
    assert final.account.used_capital == 0
    assert final.account.available_capital == Decimal("500000")


def test_duplicate_candidate_reservation_is_rejected(pg_connection) -> None:
    initialize(pg_connection)
    duplicate = request(2).model_copy(update={"candidate_id": request(1).candidate_id})
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.reserve(request(1))
    with pytest.raises(DuplicateCapitalReservationError):
        with PostgresTransaction(pg_connection, close_connection=False) as transaction:
            transaction.capital.reserve(duplicate)


def test_transaction_rollback_restores_capital(pg_connection) -> None:
    initialize(pg_connection)
    with pytest.raises(RuntimeError):
        with PostgresTransaction(pg_connection, close_connection=False) as transaction:
            transaction.capital.reserve(request(1))
            raise RuntimeError("force rollback")
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        current = transaction.capital.get_account(PORTFOLIO_ID)
        reservation = transaction.capital.get_reservation(request(1).reservation_id)
    assert current is not None and current.available_capital == Decimal("500000")
    assert reservation is None


def test_invalid_double_release_fails_closed(pg_connection) -> None:
    initialize(pg_connection)
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        reserved = transaction.capital.reserve(request(1))
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.release(
            reserved.reservation.reservation_id, updated_at=NOW + timedelta(minutes=1)
        )
    with pytest.raises(CapitalReservationStateError):
        with PostgresTransaction(pg_connection, close_connection=False) as transaction:
            transaction.capital.release(
                reserved.reservation.reservation_id, updated_at=NOW + timedelta(minutes=1)
            )


def test_halted_loss_state_blocks_new_reservation(pg_connection) -> None:
    halted = account().model_copy(update={"loss_state": LossState.HALTED})
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.create_account(halted)
    with pytest.raises(CapitalReservationStateError, match="loss state"):
        with PostgresTransaction(pg_connection, close_connection=False) as transaction:
            transaction.capital.reserve(request(1))


def test_out_of_order_request_keeps_account_timestamp_monotonic(pg_connection) -> None:
    initialize(pg_connection)
    stale = request(1).model_copy(update={"requested_at": NOW - timedelta(seconds=1)})
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        result = transaction.capital.reserve(stale)
    assert result.account.updated_at == NOW
    assert result.account.available_capital == Decimal("300000")
