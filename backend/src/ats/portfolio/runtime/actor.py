"""Single-process serialized owner backed by R17's cross-process transactions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal
from threading import Lock
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.persistence import TransactionManager
from ats.portfolio.persistence import (
    CapitalReservation,
    CapitalReservationResult,
    CapitalReservationState,
    PortfolioCapitalAccount,
)

from .models import (
    PartitionCapitalLimit,
    PartitionCapitalUsage,
    PortfolioAuthorityPolicy,
    PortfolioAuthoritySnapshot,
    PortfolioPolicyDeniedError,
    PortfolioRecoveryEvidence,
    PortfolioReservationCommand,
    ReservationPartition,
    UnknownSubmissionHold,
)


class SerializedPortfolioAuthority:
    """Serializes new-risk commands while every money transition remains durable in R17."""

    def __init__(
        self,
        *,
        transaction_manager: TransactionManager,
        policy: PortfolioAuthorityPolicy,
    ) -> None:
        self._transactions = transaction_manager
        self._policy = policy
        self._lock = Lock()
        self._portfolio_id: UUID | None = None
        self._commands: dict[UUID, PortfolioReservationCommand] = {}
        self._recovered = False

    def recover(self, evidence: PortfolioRecoveryEvidence) -> PortfolioAuthoritySnapshot:
        with self._lock:
            if self._recovered:
                raise RuntimeError("portfolio authority recovery already completed")
            with self._transactions.transaction() as transaction:
                account = transaction.capital.get_account(evidence.portfolio_id)
                if account is None:
                    raise RuntimeError("durable portfolio account does not exist")
                reservations: list[CapitalReservation] = []
                for command in evidence.active_commands:
                    reservation = transaction.capital.get_reservation(
                        command.request.reservation_id
                    )
                    if reservation is None or reservation.state is CapitalReservationState.RELEASED:
                        raise RuntimeError("recovery evidence does not match durable reservation")
                    if reservation.portfolio_id != evidence.portfolio_id:
                        raise RuntimeError("durable reservation belongs to another portfolio")
                    request = command.request
                    if (
                        reservation.campaign_id != request.campaign_id
                        or reservation.candidate_id != request.candidate_id
                        or reservation.instrument_id != request.instrument_id
                        or reservation.amount != request.amount
                    ):
                        raise RuntimeError("recovery command does not bind durable reservation")
                    reservations.append(reservation)
            self._portfolio_id = evidence.portfolio_id
            self._commands = {
                item.request.reservation_id: item for item in evidence.active_commands
            }
            self._recovered = True
            assert account is not None
            return self._snapshot(account, tuple(reservations))

    def reserve(self, command: PortfolioReservationCommand) -> CapitalReservationResult:
        with self._lock:
            self._require_ready(command.request.portfolio_id)
            active = self._load_active_reservations()
            self._validate_policy(command, active)
            with self._transactions.transaction() as transaction:
                result = transaction.capital.reserve(command.request)
            self._commands[command.request.reservation_id] = command
            return result

    def commit(self, reservation_id: UUID, *, updated_at: UTCDateTime) -> CapitalReservationResult:
        with self._lock:
            self._require_tracked(reservation_id)
            with self._transactions.transaction() as transaction:
                result = transaction.capital.commit(reservation_id, updated_at=updated_at)
            return result

    def release(self, reservation_id: UUID, *, updated_at: UTCDateTime) -> CapitalReservationResult:
        with self._lock:
            self._require_tracked(reservation_id)
            with self._transactions.transaction() as transaction:
                result = transaction.capital.release(reservation_id, updated_at=updated_at)
            del self._commands[reservation_id]
            return result

    def hold_unknown_submission(self, reservation_id: UUID) -> UnknownSubmissionHold:
        with self._lock:
            self._require_tracked(reservation_id)
            with self._transactions.transaction() as transaction:
                reservation = transaction.capital.get_reservation(reservation_id)
            if reservation is None or reservation.state is not CapitalReservationState.RESERVED:
                raise RuntimeError("unknown submission has no durable capital hold")
            return UnknownSubmissionHold(
                reservation=reservation,
                retry_permitted=False,
                reason_code="SUBMISSION_UNKNOWN_RESERVATION_HELD",
            )

    def snapshot(self) -> PortfolioAuthoritySnapshot:
        with self._lock:
            if self._portfolio_id is None or not self._recovered:
                raise RuntimeError("portfolio authority recovery is required")
            with self._transactions.transaction() as transaction:
                account = transaction.capital.get_account(self._portfolio_id)
                if account is None:
                    raise RuntimeError("durable portfolio account does not exist")
                reservations = tuple(
                    reservation
                    for reservation_id in sorted(self._commands, key=str)
                    if (reservation := transaction.capital.get_reservation(reservation_id))
                    is not None
                    and reservation.state is not CapitalReservationState.RELEASED
                )
            if len(reservations) != len(self._commands):
                raise RuntimeError("runtime reservation view diverged from durable truth")
            assert account is not None
            return self._snapshot(account, reservations)

    def _load_active_reservations(self) -> tuple[CapitalReservation, ...]:
        if self._portfolio_id is None:
            raise RuntimeError("portfolio authority recovery is required")
        with self._transactions.transaction() as transaction:
            reservations = tuple(
                reservation
                for reservation_id in sorted(self._commands, key=str)
                if (reservation := transaction.capital.get_reservation(reservation_id)) is not None
                and reservation.state is not CapitalReservationState.RELEASED
            )
        if len(reservations) != len(self._commands):
            raise RuntimeError("runtime reservation view diverged from durable truth")
        return reservations

    def _validate_policy(
        self,
        command: PortfolioReservationCommand,
        active: tuple[CapitalReservation, ...],
    ) -> None:
        if len(active) >= self._policy.maximum_active_reservations:
            raise PortfolioPolicyDeniedError("active reservation limit reached")
        requested = command.request.amount
        self._validate_partition_limit(
            requested=requested,
            key=command.partition.market,
            limits=self._policy.market_limits,
            active=active,
            selector=lambda item: item.market,
        )
        self._validate_partition_limit(
            requested=requested,
            key=command.partition.strategy,
            limits=self._policy.strategy_limits,
            active=active,
            selector=lambda item: item.strategy,
        )

    def _validate_partition_limit(
        self,
        *,
        requested: Decimal,
        key: str,
        limits: tuple[PartitionCapitalLimit, ...],
        active: tuple[CapitalReservation, ...],
        selector: Callable[[ReservationPartition], str],
    ) -> None:
        limit = next((item.maximum_capital for item in limits if item.partition_key == key), None)
        if limit is None:
            raise PortfolioPolicyDeniedError("partition has no configured capital limit")
        used = sum(
            (
                reservation.amount
                for reservation in active
                if selector(self._commands[reservation.reservation_id].partition) == key
            ),
            start=Decimal("0"),
        )
        if used + requested > limit:
            raise PortfolioPolicyDeniedError("partition capital limit exceeded")

    def _snapshot(
        self,
        account: PortfolioCapitalAccount,
        reservations: tuple[CapitalReservation, ...],
    ) -> PortfolioAuthoritySnapshot:
        grouped: dict[ReservationPartition, list[CapitalReservation]] = defaultdict(list)
        for reservation in reservations:
            grouped[self._commands[reservation.reservation_id].partition].append(reservation)
        usage = tuple(
            PartitionCapitalUsage(
                partition=partition,
                reserved_capital=sum(
                    (
                        item.amount
                        for item in values
                        if item.state is CapitalReservationState.RESERVED
                    ),
                    start=Decimal("0"),
                ),
                used_capital=sum(
                    (
                        item.amount
                        for item in values
                        if item.state is CapitalReservationState.COMMITTED
                    ),
                    start=Decimal("0"),
                ),
                active_reservation_count=len(values),
            )
            for partition, values in sorted(
                grouped.items(), key=lambda item: (item[0].market, item[0].strategy)
            )
        )
        inflight = sum(
            (
                item.amount
                for item in reservations
                if item.state is CapitalReservationState.RESERVED
            ),
            start=Decimal("0"),
        )
        open_risk = sum(
            (
                item.amount
                for item in reservations
                if item.state is CapitalReservationState.COMMITTED
            ),
            start=Decimal("0"),
        )
        return PortfolioAuthoritySnapshot(
            account=account,
            active_reservations=reservations,
            partition_usage=usage,
            inflight_capital=inflight,
            open_risk_capital=open_risk,
            active_reservation_count=len(reservations),
        )

    def _require_ready(self, portfolio_id: UUID) -> None:
        if not self._recovered or self._portfolio_id != portfolio_id:
            raise RuntimeError("portfolio authority recovery is required")

    def _require_tracked(self, reservation_id: UUID) -> None:
        if not self._recovered or reservation_id not in self._commands:
            raise RuntimeError("reservation is not tracked by recovered authority")


__all__ = ["SerializedPortfolioAuthority"]
