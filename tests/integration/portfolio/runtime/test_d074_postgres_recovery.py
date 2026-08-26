"""D07.4 real-PostgreSQL capital invariants (TEST_ONLY, NON_MARKET_DATA)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.types import LossState
from ats.persistence import PostgresTransaction, connect_postgres
from ats.persistence.postgres import PostgresTransactionManager
from ats.portfolio.persistence import CapitalReservationRequest, PortfolioCapitalAccount
from ats.portfolio.runtime import (
    PartitionCapitalLimit,
    PortfolioAuthorityPolicy,
    PortfolioRecoveryEvidence,
    PortfolioReservationCommand,
    ReservationPartition,
    SerializedPortfolioAuthority,
)

NOW = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("77000000-0000-0000-0000-000000000001")


def _command(
    index: int, *, market: str = "NIFTY", amount: str = "100000"
) -> PortfolioReservationCommand:
    return PortfolioReservationCommand(
        request=CapitalReservationRequest(
            reservation_id=UUID(f"77100000-0000-0000-0000-{index:012d}"),
            portfolio_id=PORTFOLIO_ID,
            campaign_id=UUID(f"77200000-0000-0000-0000-{index:012d}"),
            candidate_id=UUID(f"77300000-0000-0000-0000-{index:012d}"),
            instrument_id=f"{market}-OPTION-{index}",
            amount=Decimal(amount),
            requested_at=NOW + timedelta(seconds=index),
        ),
        partition=ReservationPartition(market=market, strategy="D074"),
    )


def _policy() -> PortfolioAuthorityPolicy:
    return PortfolioAuthorityPolicy(
        maximum_active_reservations=4,
        market_limits=(
            PartitionCapitalLimit(partition_key="NIFTY", maximum_capital=Decimal("300000")),
            PartitionCapitalLimit(partition_key="BANKNIFTY", maximum_capital=Decimal("300000")),
        ),
        strategy_limits=(
            PartitionCapitalLimit(partition_key="D074", maximum_capital=Decimal("500000")),
        ),
    )


def _manager(dsn: str) -> PostgresTransactionManager:
    return PostgresTransactionManager(lambda: connect_postgres(dsn))


def _create_account(pg_connection) -> None:
    account = PortfolioCapitalAccount(
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
    with PostgresTransaction(pg_connection, close_connection=False) as transaction:
        transaction.capital.create_account(account)


def test_unknown_submission_survives_restart_without_freeing_capital(
    postgres_dsn: str, pg_connection
) -> None:
    _create_account(pg_connection)
    command = _command(1)
    first = SerializedPortfolioAuthority(
        transaction_manager=_manager(postgres_dsn), policy=_policy()
    )
    first.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    result = first.reserve(command)
    hold = first.hold_unknown_submission(result.reservation.reservation_id)
    assert not hold.retry_permitted
    assert first.snapshot().account.available_capital == Decimal("400000")

    restarted = SerializedPortfolioAuthority(
        transaction_manager=_manager(postgres_dsn), policy=_policy()
    )
    recovered = restarted.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW + timedelta(minutes=1),
            active_commands=(command,),
            reconciliation_complete=True,
        )
    )
    assert recovered.inflight_capital == Decimal("100000")
    assert recovered.account.available_capital == Decimal("400000")
    restarted.commit(result.reservation.reservation_id, updated_at=NOW + timedelta(minutes=2))
    committed = restarted.snapshot()
    assert committed.inflight_capital == 0
    assert committed.open_risk_capital == Decimal("100000")
    assert committed.account.available_capital == Decimal("400000")


def test_first_partial_fill_conservatively_commits_full_reserved_risk(
    postgres_dsn: str, pg_connection
) -> None:
    _create_account(pg_connection)
    authority = SerializedPortfolioAuthority(
        transaction_manager=_manager(postgres_dsn), policy=_policy()
    )
    authority.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    reservation = authority.reserve(_command(1, amount="120000")).reservation
    authority.commit(reservation.reservation_id, updated_at=NOW + timedelta(seconds=10))
    snapshot = authority.snapshot()
    assert snapshot.inflight_capital == 0
    assert snapshot.open_risk_capital == Decimal("120000")
    assert snapshot.account.reserved_capital == 0
    assert snapshot.account.used_capital == Decimal("120000")
    assert snapshot.account.available_capital == Decimal("380000")


def test_recovery_rejects_stale_or_incomplete_evidence(postgres_dsn: str, pg_connection) -> None:
    _create_account(pg_connection)
    authority = SerializedPortfolioAuthority(
        transaction_manager=_manager(postgres_dsn), policy=_policy()
    )
    authority.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    command = _command(1)
    authority.reserve(command)
    restarted = SerializedPortfolioAuthority(
        transaction_manager=_manager(postgres_dsn), policy=_policy()
    )
    wrong = _command(2)
    with pytest.raises(RuntimeError, match="does not match durable reservation"):
        restarted.recover(
            PortfolioRecoveryEvidence(
                portfolio_id=PORTFOLIO_ID,
                reconciled_at=NOW,
                active_commands=(wrong,),
                reconciliation_complete=True,
            )
        )
