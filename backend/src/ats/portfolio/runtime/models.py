"""Strict commands, recovery evidence, limits, and snapshots for portfolio authority."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import (
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
)
from ats.contracts.intelligence.types import RegisteredCode
from ats.portfolio.persistence import (
    CapitalReservation,
    CapitalReservationRequest,
    PortfolioCapitalAccount,
)


class ReservationPartition(ATSBaseModel):
    market: RegisteredCode
    strategy: RegisteredCode


class PortfolioReservationCommand(ATSBaseModel):
    request: CapitalReservationRequest
    partition: ReservationPartition


class PartitionCapitalLimit(ATSBaseModel):
    partition_key: RegisteredCode
    maximum_capital: PositiveDecimal


class PortfolioAuthorityPolicy(ATSBaseModel):
    maximum_active_reservations: PositiveInt
    market_limits: tuple[PartitionCapitalLimit, ...]
    strategy_limits: tuple[PartitionCapitalLimit, ...]

    @model_validator(mode="after")
    def validate_limits(self) -> PortfolioAuthorityPolicy:
        for name, values in (
            ("market", self.market_limits),
            ("strategy", self.strategy_limits),
        ):
            keys = tuple(item.partition_key for item in values)
            if len(set(keys)) != len(keys):
                raise ValueError(f"duplicate {name} partition limit")
        return self


class PortfolioRecoveryEvidence(ATSBaseModel):
    portfolio_id: UUID
    reconciled_at: UTCDateTime
    active_commands: tuple[PortfolioReservationCommand, ...]
    reconciliation_complete: Literal[True]

    @model_validator(mode="after")
    def validate_commands(self) -> PortfolioRecoveryEvidence:
        ids = tuple(item.request.reservation_id for item in self.active_commands)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate recovered reservation")
        if any(item.request.portfolio_id != self.portfolio_id for item in self.active_commands):
            raise ValueError("recovered reservation belongs to another portfolio")
        return self


class PartitionCapitalUsage(ATSBaseModel):
    partition: ReservationPartition
    reserved_capital: NonNegativeDecimal
    used_capital: NonNegativeDecimal
    active_reservation_count: NonNegativeInt


class PortfolioAuthoritySnapshot(ATSBaseModel):
    account: PortfolioCapitalAccount
    active_reservations: tuple[CapitalReservation, ...]
    partition_usage: tuple[PartitionCapitalUsage, ...]
    inflight_capital: NonNegativeDecimal
    open_risk_capital: NonNegativeDecimal
    active_reservation_count: NonNegativeInt


class UnknownSubmissionHold(ATSBaseModel):
    reservation: CapitalReservation
    retry_permitted: Literal[False]
    reason_code: Literal["SUBMISSION_UNKNOWN_RESERVATION_HELD"]


class PortfolioPolicyDeniedError(RuntimeError):
    pass


__all__ = [
    "PartitionCapitalLimit",
    "PartitionCapitalUsage",
    "PortfolioAuthorityPolicy",
    "PortfolioAuthoritySnapshot",
    "PortfolioPolicyDeniedError",
    "PortfolioRecoveryEvidence",
    "PortfolioReservationCommand",
    "ReservationPartition",
    "UnknownSubmissionHold",
]
