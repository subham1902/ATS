from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.domain.types import LossState
from ats.portfolio.persistence import (
    CapitalReservation,
    CapitalReservationRequest,
    CapitalReservationResult,
    CapitalReservationState,
    PortfolioCapitalAccount,
)
from ats.portfolio.runtime import (
    PartitionCapitalLimit,
    PortfolioAuthorityPolicy,
    PortfolioReservationCommand,
    ReservationPartition,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
PORTFOLIO_ID = UUID("71000000-0000-0000-0000-000000000001")
CAMPAIGN_ID = UUID("71000000-0000-0000-0000-000000000002")


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


def command(
    index: int,
    *,
    market: str,
    strategy: str = "STEEL_THREAD",
    amount: str = "200000",
) -> PortfolioReservationCommand:
    return PortfolioReservationCommand(
        request=CapitalReservationRequest(
            reservation_id=UUID(f"72000000-0000-0000-0000-{index:012d}"),
            portfolio_id=PORTFOLIO_ID,
            campaign_id=CAMPAIGN_ID,
            candidate_id=UUID(f"73000000-0000-0000-0000-{index:012d}"),
            instrument_id=f"{market}-OPTION",
            amount=Decimal(amount),
            requested_at=NOW + timedelta(seconds=index),
        ),
        partition=ReservationPartition(market=market, strategy=strategy),
    )


def policy(*, maximum: int = 2) -> PortfolioAuthorityPolicy:
    return PortfolioAuthorityPolicy(
        maximum_active_reservations=maximum,
        market_limits=(
            PartitionCapitalLimit(partition_key="NIFTY", maximum_capital=Decimal("300000")),
            PartitionCapitalLimit(partition_key="BANKNIFTY", maximum_capital=Decimal("300000")),
        ),
        strategy_limits=(
            PartitionCapitalLimit(partition_key="STEEL_THREAD", maximum_capital=Decimal("400000")),
        ),
    )


class FakeCapitalRepository:
    def __init__(self) -> None:
        self.account = account()
        self.reservations: dict[UUID, CapitalReservation] = {}

    def get_account(self, portfolio_id: UUID) -> PortfolioCapitalAccount | None:
        return self.account if portfolio_id == self.account.portfolio_id else None

    def get_reservation(self, reservation_id: UUID) -> CapitalReservation | None:
        return self.reservations.get(reservation_id)

    def reserve(self, request: CapitalReservationRequest) -> CapitalReservationResult:
        if request.amount > self.account.available_capital:
            raise RuntimeError("insufficient capital")
        if request.reservation_id in self.reservations:
            raise RuntimeError("duplicate reservation")
        reservation = CapitalReservation(
            reservation_id=request.reservation_id,
            portfolio_id=request.portfolio_id,
            campaign_id=request.campaign_id,
            candidate_id=request.candidate_id,
            instrument_id=request.instrument_id,
            amount=request.amount,
            state=CapitalReservationState.RESERVED,
            created_at=request.requested_at,
            updated_at=request.requested_at,
        )
        self.reservations[request.reservation_id] = reservation
        self.account = self.account.model_copy(
            update={
                "version": self.account.version + 1,
                "reserved_capital": self.account.reserved_capital + request.amount,
                "available_capital": self.account.available_capital - request.amount,
                "updated_at": request.requested_at,
            }
        )
        return CapitalReservationResult(reservation=reservation, account=self.account)

    def commit(self, reservation_id: UUID, *, updated_at) -> CapitalReservationResult:
        reservation = self.reservations[reservation_id]
        if reservation.state is not CapitalReservationState.RESERVED:
            raise RuntimeError("invalid commit")
        reservation = reservation.model_copy(
            update={"state": CapitalReservationState.COMMITTED, "updated_at": updated_at}
        )
        self.reservations[reservation_id] = reservation
        self.account = self.account.model_copy(
            update={
                "version": self.account.version + 1,
                "reserved_capital": self.account.reserved_capital - reservation.amount,
                "used_capital": self.account.used_capital + reservation.amount,
                "updated_at": updated_at,
            }
        )
        return CapitalReservationResult(reservation=reservation, account=self.account)

    def release(self, reservation_id: UUID, *, updated_at) -> CapitalReservationResult:
        reservation = self.reservations[reservation_id]
        if reservation.state is CapitalReservationState.RELEASED:
            raise RuntimeError("double release")
        previous = reservation.state
        reservation = reservation.model_copy(
            update={"state": CapitalReservationState.RELEASED, "updated_at": updated_at}
        )
        self.reservations[reservation_id] = reservation
        update = {
            "version": self.account.version + 1,
            "updated_at": updated_at,
            "available_capital": self.account.available_capital + reservation.amount,
        }
        if previous is CapitalReservationState.RESERVED:
            update["reserved_capital"] = self.account.reserved_capital - reservation.amount
        else:
            update["used_capital"] = self.account.used_capital - reservation.amount
        self.account = self.account.model_copy(update=update)
        return CapitalReservationResult(reservation=reservation, account=self.account)


class FakeTransaction:
    def __init__(self, capital: FakeCapitalRepository) -> None:
        self.capital = capital

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeTransactionManager:
    def __init__(self) -> None:
        self.capital = FakeCapitalRepository()

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self.capital)
