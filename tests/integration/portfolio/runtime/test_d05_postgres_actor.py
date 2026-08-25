from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
    PortfolioPolicyDeniedError,
    PortfolioRecoveryEvidence,
    PortfolioReservationCommand,
    ReservationPartition,
    SerializedPortfolioAuthority,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("74000000-0000-0000-0000-000000000001")
CAMPAIGN_ID = UUID("74000000-0000-0000-0000-000000000002")


def command(index: int, market: str) -> PortfolioReservationCommand:
    return PortfolioReservationCommand(
        request=CapitalReservationRequest(
            reservation_id=UUID(f"75000000-0000-0000-0000-{index:012d}"),
            portfolio_id=PORTFOLIO_ID,
            campaign_id=CAMPAIGN_ID,
            candidate_id=UUID(f"76000000-0000-0000-0000-{index:012d}"),
            instrument_id=f"{market}-OPTION",
            amount=Decimal("200000"),
            requested_at=NOW + timedelta(seconds=index),
        ),
        partition=ReservationPartition(market=market, strategy="STEEL_THREAD"),
    )


def test_serialized_owner_preserves_r17_atomic_capital_truth(
    postgres_dsn: str, pg_connection
) -> None:
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
    authority = SerializedPortfolioAuthority(
        transaction_manager=PostgresTransactionManager(lambda: connect_postgres(postgres_dsn)),
        policy=PortfolioAuthorityPolicy(
            maximum_active_reservations=2,
            market_limits=(
                PartitionCapitalLimit(partition_key="NIFTY", maximum_capital=Decimal("250000")),
                PartitionCapitalLimit(partition_key="BANKNIFTY", maximum_capital=Decimal("250000")),
            ),
            strategy_limits=(
                PartitionCapitalLimit(
                    partition_key="STEEL_THREAD", maximum_capital=Decimal("400000")
                ),
            ),
        ),
    )
    authority.recover(
        PortfolioRecoveryEvidence(
            portfolio_id=PORTFOLIO_ID,
            reconciled_at=NOW,
            active_commands=(),
            reconciliation_complete=True,
        )
    )
    first_two = (command(1, "NIFTY"), command(2, "BANKNIFTY"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(authority.reserve, first_two))
    assert len(results) == 2
    with pytest.raises(PortfolioPolicyDeniedError):
        authority.reserve(command(3, "BANKNIFTY"))
    snapshot = authority.snapshot()
    assert snapshot.account.reserved_capital == Decimal("400000")
    assert snapshot.account.available_capital == Decimal("100000")
    first_id = results[0].reservation.reservation_id
    authority.commit(first_id, updated_at=NOW + timedelta(minutes=1))
    authority.release(first_id, updated_at=NOW + timedelta(minutes=2))
    final = authority.snapshot()
    assert final.account.reserved_capital == Decimal("200000")
    assert final.account.used_capital == 0
    assert final.account.available_capital == Decimal("300000")
