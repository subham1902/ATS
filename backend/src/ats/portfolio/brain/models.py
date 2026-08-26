"""Portfolio-level allocation contracts over the canonical authority snapshot."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, NonNegativeDecimal, PositiveDecimal, Sha256
from ats.contracts.governance.models import OpportunityCandidate
from ats.portfolio.runtime import PortfolioAuthoritySnapshot
from ats.trading_runtime.hwm import HWMState
from ats.trading_runtime.modes import TradingMode


class AllocationOutcome(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_REDUCED = "ALLOW_REDUCED"
    DEFER = "DEFER"
    DENY = "DENY"


class ExposureDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class PositionExposure(ATSBaseModel):
    position_id: UUID
    underlying: NonEmptyStr
    direction: ExposureDirection
    strategy_id: UUID
    capital_at_risk: NonNegativeDecimal


class CandidateAllocationRequest(ATSBaseModel):
    candidate: OpportunityCandidate
    underlying: NonEmptyStr
    direction: ExposureDirection
    requested_capital: PositiveDecimal
    requested_quantity: PositiveDecimal
    maximum_loss: PositiveDecimal
    expected_net_value: FiniteDecimal
    spread_fraction: NonNegativeDecimal
    liquidity_score: Decimal
    quote_fresh: bool

    @model_validator(mode="after")
    def validate_liquidity(self) -> CandidateAllocationRequest:
        if not Decimal("0") <= self.liquidity_score <= Decimal("1"):
            raise ValueError("liquidity_score must be in [0, 1]")
        return self


class PortfolioBrainContext(ATSBaseModel):
    snapshot: PortfolioAuthoritySnapshot
    positions: tuple[PositionExposure, ...]
    hwm: HWMState
    user_mode: TradingMode
    effective_mode: TradingMode
    feed_healthy: bool
    execution_healthy: bool
    calibration_healthy: bool
    loss_streak: int
    remaining_session_risk: NonNegativeDecimal
    as_of: UTCDateTime
    input_hash: Sha256


class PortfolioAllocationDecision(ATSBaseModel):
    decision_id: UUID
    candidate_id: UUID
    candidate_hash: Sha256
    outcome: AllocationOutcome
    approved_capital: NonNegativeDecimal
    approved_quantity: NonNegativeDecimal
    expected_net_value: FiniteDecimal
    effective_mode: TradingMode
    correlation_penalty: Decimal
    concentration_penalty: Decimal
    drawdown_penalty: Decimal
    execution_penalty: Decimal
    liquidity_penalty: Decimal
    reason_codes: tuple[NonEmptyStr, ...]
    input_hash: Sha256
    valid_until: UTCDateTime
    payload_hash: Sha256


class PortfolioReviewAction(StrEnum):
    KEEP = "KEEP"
    REDUCE = "REDUCE"
    EXIT_RECOMMENDED = "EXIT_RECOMMENDED"
    BLOCK_NEW_DIRECTION = "BLOCK_NEW_DIRECTION"
    DEESCALATE_MODE = "DEESCALATE_MODE"


class PortfolioReview(ATSBaseModel):
    action: PortfolioReviewAction
    effective_mode: TradingMode
    reason_codes: tuple[NonEmptyStr, ...]


__all__ = [
    "AllocationOutcome",
    "CandidateAllocationRequest",
    "ExposureDirection",
    "PortfolioAllocationDecision",
    "PortfolioBrainContext",
    "PortfolioReview",
    "PortfolioReviewAction",
    "PositionExposure",
]
