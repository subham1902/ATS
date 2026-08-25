from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from ats.portfolio.persistence import CapitalReservationState
from ats.portfolio.runtime import (
    PortfolioPolicyDeniedError,
    PortfolioRecoveryEvidence,
    SerializedPortfolioAuthority,
)

from .helpers import NOW, PORTFOLIO_ID, FakeTransactionManager, command, policy


def actor(*, maximum: int = 2):
    transactions = FakeTransactionManager()
    authority = SerializedPortfolioAuthority(
        transaction_manager=transactions, policy=policy(maximum=maximum)
    )
    authority.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    return authority, transactions


def test_recovery_is_required_before_financial_authority() -> None:
    authority = SerializedPortfolioAuthority(
        transaction_manager=FakeTransactionManager(), policy=policy()
    )
    with pytest.raises(RuntimeError, match="recovery"):
        authority.reserve(command(1, market="NIFTY"))


def test_concurrent_nifty_banknifty_and_third_request_are_serialized() -> None:
    authority, _ = actor(maximum=2)
    first_two = (
        command(1, market="NIFTY"),
        command(2, market="BANKNIFTY"),
    )

    def attempt(index: int) -> str:
        try:
            authority.reserve(first_two[index])
            return "RESERVED"
        except PortfolioPolicyDeniedError:
            return "DENIED"

    with ThreadPoolExecutor(max_workers=3) as executor:
        outcomes = tuple(executor.map(attempt, range(2)))
    assert outcomes.count("RESERVED") == 2
    with pytest.raises(PortfolioPolicyDeniedError, match="active reservation"):
        authority.reserve(command(3, market="BANKNIFTY", amount="100000"))
    snapshot = authority.snapshot()
    assert snapshot.inflight_capital == Decimal("400000")
    assert snapshot.account.available_capital == Decimal("100000")


def test_market_and_strategy_partitions_fail_closed() -> None:
    authority, _ = actor(maximum=4)
    authority.reserve(command(1, market="NIFTY", amount="200000"))
    with pytest.raises(PortfolioPolicyDeniedError, match="partition capital"):
        authority.reserve(command(2, market="NIFTY", amount="200000"))
    authority.reserve(command(3, market="BANKNIFTY", amount="200000"))
    with pytest.raises(PortfolioPolicyDeniedError, match="partition capital"):
        authority.reserve(command(4, market="BANKNIFTY", amount="100000"))


def test_unknown_submission_keeps_durable_reservation_and_forbids_retry() -> None:
    authority, _ = actor()
    reserved = authority.reserve(command(1, market="NIFTY", amount="100000"))
    held = authority.hold_unknown_submission(reserved.reservation.reservation_id)
    assert held.reservation.state is CapitalReservationState.RESERVED
    assert held.retry_permitted is False
    assert authority.snapshot().inflight_capital == Decimal("100000")


def test_commit_then_release_updates_used_capital_exactly_once() -> None:
    authority, _ = actor()
    reserved = authority.reserve(command(1, market="NIFTY", amount="100000"))
    reservation_id = reserved.reservation.reservation_id
    authority.commit(reservation_id, updated_at=NOW + timedelta(minutes=1))
    committed = authority.snapshot()
    assert committed.inflight_capital == 0
    assert committed.open_risk_capital == Decimal("100000")
    authority.release(reservation_id, updated_at=NOW + timedelta(minutes=2))
    final = authority.snapshot()
    assert final.account.available_capital == Decimal("500000")
    assert final.active_reservation_count == 0
    with pytest.raises(RuntimeError, match="not tracked"):
        authority.release(reservation_id, updated_at=NOW + timedelta(minutes=3))


def test_recovery_validates_durable_binding() -> None:
    transactions = FakeTransactionManager()
    first = command(1, market="NIFTY", amount="100000")
    transactions.capital.reserve(first.request)
    wrong = first.model_copy(
        update={"request": first.request.model_copy(update={"amount": Decimal("99999")})}
    )
    authority = SerializedPortfolioAuthority(transaction_manager=transactions, policy=policy())
    with pytest.raises(RuntimeError, match="does not bind"):
        authority.recover(
            PortfolioRecoveryEvidence(
                portfolio_id=PORTFOLIO_ID,
                reconciled_at=NOW,
                active_commands=(wrong,),
                reconciliation_complete=True,
            )
        )
