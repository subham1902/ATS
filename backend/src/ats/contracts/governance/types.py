"""Strict supporting types for IBA-C01 governance contracts."""

from __future__ import annotations

from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, Probability
from ats.contracts.domain.types import (
    InstrumentId,
    JsonValue,
    MoneyOrPortfolioFraction,
    PortfolioFraction,
    PositiveDecimal,
    PositiveInt,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.intelligence.types import PositiveFiniteFloat, RegisteredCode, StrategyRef


class CampaignStatus(ATSStringEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class StrategyExecutionMode(ATSStringEnum):
    CHAMPION_ONLY = "CHAMPION_ONLY"
    ISOLATED_CHALLENGER_PAPER = "ISOLATED_CHALLENGER_PAPER"


class CandidateStatus(ATSStringEnum):
    CREATED = "CREATED"
    ELIGIBLE = "ELIGIBLE"
    RISK_EVALUATED = "RISK_EVALUATED"
    ADVISED = "ADVISED"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class PositionThesisState(ATSStringEnum):
    HEALTHY = "HEALTHY"
    DEGRADING = "DEGRADING"
    INVALIDATED = "INVALIDATED"
    UNKNOWN = "UNKNOWN"
    CLOSED = "CLOSED"


class PositionRecommendation(ATSStringEnum):
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    TRAIL = "TRAIL"
    TAKE_PARTIAL = "TAKE_PARTIAL"
    UNKNOWN = "UNKNOWN"


class ActionKind(ATSStringEnum):
    OPEN_POSITION = "OPEN_POSITION"
    INCREASE_POSITION = "INCREASE_POSITION"
    REDUCE_POSITION = "REDUCE_POSITION"
    CLOSE_POSITION = "CLOSE_POSITION"
    MODIFY_PROTECTIVE_EXIT = "MODIFY_PROTECTIVE_EXIT"
    CANCEL_ORDER = "CANCEL_ORDER"
    EMERGENCY_FLATTEN = "EMERGENCY_FLATTEN"


class RiskDirection(ATSStringEnum):
    INCREASE = "INCREASE"
    REDUCE = "REDUCE"
    NEUTRAL = "NEUTRAL"


class SystemState(ATSStringEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    RECONCILING = "RECONCILING"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"


class ConstraintSource(ATSStringEnum):
    SYSTEM = "SYSTEM"
    POLICY = "POLICY"
    CAMPAIGN = "CAMPAIGN"


class ConstraintCode(ATSStringEnum):
    MAXIMUM_LOSS_PER_TRADE = "MAXIMUM_LOSS_PER_TRADE"
    MAXIMUM_CAMPAIGN_LOSS = "MAXIMUM_CAMPAIGN_LOSS"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    MAX_TRADES = "MAX_TRADES"
    MAX_CONCURRENT_POSITIONS = "MAX_CONCURRENT_POSITIONS"
    CAPITAL_BUDGET = "CAPITAL_BUDGET"
    MAXIMUM_BUDGET_PER_TRADE = "MAXIMUM_BUDGET_PER_TRADE"
    MINIMUM_CALIBRATED_PROBABILITY = "MINIMUM_CALIBRATED_PROBABILITY"
    MINIMUM_CALIBRATION_SUPPORT = "MINIMUM_CALIBRATION_SUPPORT"
    MINIMUM_EXPECTED_EDGE_R = "MINIMUM_EXPECTED_EDGE_R"
    MINIMUM_REWARD_RISK = "MINIMUM_REWARD_RISK"
    ALLOWED_INSTRUMENTS = "ALLOWED_INSTRUMENTS"
    ALLOWED_TIMEFRAMES = "ALLOWED_TIMEFRAMES"
    ALLOWED_STRATEGIES = "ALLOWED_STRATEGIES"
    STRATEGY_EXECUTION_MODE = "STRATEGY_EXECUTION_MODE"


class EffectiveConstraintSet(ATSBaseModel):
    maximum_loss_per_trade: MoneyOrPortfolioFraction
    maximum_campaign_loss: MoneyOrPortfolioFraction
    drawdown_limit: PortfolioFraction
    max_trades: PositiveInt
    max_concurrent_positions: PositiveInt
    capital_budget: PositiveDecimal
    maximum_budget_per_trade: MoneyOrPortfolioFraction
    minimum_calibrated_probability: Probability
    minimum_calibration_support: PositiveInt
    minimum_expected_edge_r: PositiveFiniteFloat
    minimum_reward_risk: PositiveDecimal
    allowed_instruments: tuple[InstrumentId, ...]
    allowed_timeframes: tuple[RegisteredCode, ...]
    allowed_strategies: tuple[StrategyRef, ...]
    strategy_execution_mode: StrategyExecutionMode

    @model_validator(mode="after")
    def validate_allowlists(self) -> EffectiveConstraintSet:
        for name in ("allowed_instruments", "allowed_timeframes", "allowed_strategies"):
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must be non-empty")
            ensure_unique(values, name)
        return self


class ConstraintProvenance(ATSBaseModel):
    constraint_code: ConstraintCode
    winning_source: ConstraintSource
    source_refs: tuple[UUID, ...]
    selected_value: JsonValue


__all__ = [name for name in globals() if not name.startswith("_")]
