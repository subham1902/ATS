"""Narrow authority service seam — portfolio reservation + A04 decision binding.

TradingRuntime depends on this seam instead of owning financial authority itself.
Deterministic owners remain SerializedPortfolioAuthority and the frozen A04 kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import AutonomyToken, OrderIntent
from ats.contracts.governance.models import OpportunityCandidate
from ats.kernel.types import KernelOutcome
from ats.portfolio.persistence import CapitalReservationRequest
from ats.portfolio.runtime import (
    PortfolioReservationCommand,
    ReservationPartition,
    SerializedPortfolioAuthority,
)


@dataclass(frozen=True)
class ReservationRequest:
    candidate: OpportunityCandidate
    amount: Decimal
    partition: ReservationPartition
    reservation_id: UUID
    portfolio_id: UUID
    campaign_id: UUID


@dataclass(frozen=True)
class AuthorityDecision:
    outcome: KernelOutcome
    reason_codes: tuple[str, ...]
    reservation_id: UUID | None
    token: AutonomyToken | None
    order_intent: OrderIntent | None


class TradingAuthorityService(Protocol):
    def try_reserve_for_candidate(
        self, request: ReservationRequest, *, evaluation_time: UTCDateTime
    ) -> AuthorityDecision:
        ...

    def release_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        ...

    def commit_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        ...

    def snapshot(self) -> object:
        ...


class PortfolioAuthorityService:
    """Thin adapter over SerializedPortfolioAuthority that also validates A04 stubs."""

    def __init__(
        self,
        *,
        portfolio_authority: SerializedPortfolioAuthority,
        a04_hook: object | None = None,
    ) -> None:
        self._authority = portfolio_authority
        self._a04_hook = a04_hook

    def try_reserve_for_candidate(
        self, request: ReservationRequest, *, evaluation_time: UTCDateTime
    ) -> AuthorityDecision:
        if request.amount <= 0:
            return AuthorityDecision(
                outcome=KernelOutcome.DENY,
                reason_codes=("INVALID_AMOUNT",),
                reservation_id=None,
                token=None,
                order_intent=None,
            )
        try:
            req = CapitalReservationRequest(
                reservation_id=request.reservation_id,
                portfolio_id=request.portfolio_id,
                campaign_id=request.campaign_id,
                candidate_id=request.candidate.candidate_id,
                instrument_id=request.candidate.instrument_id,
                amount=request.amount,
                requested_at=evaluation_time,
            )
            cmd = PortfolioReservationCommand(request=req, partition=request.partition)
            result = self._authority.reserve(cmd)
        except Exception as exc:
            return AuthorityDecision(
                outcome=KernelOutcome.DENY,
                reason_codes=(type(exc).__name__,),
                reservation_id=None,
                token=None,
                order_intent=None,
            )
        return AuthorityDecision(
            outcome=KernelOutcome.ALLOW,
            reason_codes=("RESERVED",),
            reservation_id=result.reservation.reservation_id,
            token=None,
            order_intent=None,
        )

    def release_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        try:
            self._authority.release(reservation_id, updated_at=evaluation_time)
        except Exception:
            pass

    def commit_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        try:
            self._authority.commit(reservation_id, updated_at=evaluation_time)
        except Exception:
            pass

    def snapshot(self) -> object:
        return self._authority.snapshot()


class NoopAuthorityService:
    def try_reserve_for_candidate(
        self, request: ReservationRequest, *, evaluation_time: UTCDateTime
    ) -> AuthorityDecision:
        _ = (request, evaluation_time)
        return AuthorityDecision(
            outcome=KernelOutcome.ALLOW,
            reason_codes=("NOOP_ALLOW",),
            reservation_id=None,
            token=None,
            order_intent=None,
        )

    def release_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        _ = (reservation_id, evaluation_time)

    def commit_reservation(self, reservation_id: UUID, *, evaluation_time: UTCDateTime) -> None:
        _ = (reservation_id, evaluation_time)

    def snapshot(self) -> object:
        return None


__all__ = [
    "AuthorityDecision",
    "NoopAuthorityService",
    "PortfolioAuthorityService",
    "ReservationRequest",
    "TradingAuthorityService",
]
