"""Immutable portfolio-capital records owned by the R17 persistence boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.domain.types import (
    LossState,
    NonNegativeDecimal,
    PortfolioFraction,
    PositiveDecimal,
    PositiveInt,
)
from ats.contracts.intelligence.types import RegisteredCode


class CapitalReservationState(StrEnum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"


class PortfolioCapitalAccount(ATSBaseModel):
    portfolio_id: UUID
    version: PositiveInt
    total_capital: PositiveDecimal
    deployable_capital: PositiveDecimal
    reserved_capital: NonNegativeDecimal
    used_capital: NonNegativeDecimal
    available_capital: NonNegativeDecimal
    realized_pnl: FiniteDecimal
    unrealized_pnl: FiniteDecimal
    daily_loss: NonNegativeDecimal
    maximum_drawdown: PortfolioFraction
    loss_state: LossState
    updated_at: UTCDateTime

    @model_validator(mode="after")
    def validate_capital_identity(self) -> PortfolioCapitalAccount:
        if self.deployable_capital > self.total_capital:
            raise ValueError("deployable capital cannot exceed total capital")
        expected = self.deployable_capital - self.reserved_capital - self.used_capital
        if expected < 0 or self.available_capital != expected:
            raise ValueError("available capital must equal deployable minus reserved and used")
        return self


class CapitalReservationRequest(ATSBaseModel):
    reservation_id: UUID
    portfolio_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    instrument_id: RegisteredCode
    amount: PositiveDecimal
    requested_at: UTCDateTime


class CapitalReservation(ATSBaseModel):
    reservation_id: UUID
    portfolio_id: UUID
    campaign_id: UUID
    candidate_id: UUID
    instrument_id: RegisteredCode
    amount: PositiveDecimal
    state: CapitalReservationState
    created_at: UTCDateTime
    updated_at: UTCDateTime

    @model_validator(mode="after")
    def validate_timestamps(self) -> CapitalReservation:
        if self.updated_at < self.created_at:
            raise ValueError("reservation update cannot precede creation")
        return self


class CapitalReservationResult(ATSBaseModel):
    reservation: CapitalReservation
    account: PortfolioCapitalAccount


class CapitalRepository(Protocol):
    def create_account(self, account: PortfolioCapitalAccount) -> None: ...
    def get_account(self, portfolio_id: UUID) -> PortfolioCapitalAccount | None: ...
    def get_reservation(self, reservation_id: UUID) -> CapitalReservation | None: ...
    def reserve(self, request: CapitalReservationRequest) -> CapitalReservationResult: ...
    def commit(
        self, reservation_id: UUID, *, updated_at: UTCDateTime
    ) -> CapitalReservationResult: ...
    def release(
        self, reservation_id: UUID, *, updated_at: UTCDateTime
    ) -> CapitalReservationResult: ...


__all__ = [
    "CapitalRepository",
    "CapitalReservation",
    "CapitalReservationRequest",
    "CapitalReservationResult",
    "CapitalReservationState",
    "PortfolioCapitalAccount",
]
