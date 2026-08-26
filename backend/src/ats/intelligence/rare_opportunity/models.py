"""Evidence-only contracts for bounded rare-opportunity intelligence."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import NonNegativeDecimal, PositiveDecimal, Sha256
from ats.market.derivatives.active_window import MarketStateFreshness


class OpportunityClass(StrEnum):
    STANDARD = "STANDARD"
    HIGH_CONVICTION = "HIGH_CONVICTION"
    CONVEX = "CONVEX"
    RARE_EVENT = "RARE_EVENT"


class AnalogueSupport(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class PatternState(ATSBaseModel):
    state_id: UUID
    as_of: UTCDateTime
    data_cutoff: UTCDateTime
    regime: str
    returns_1s: FiniteFloat
    returns_5s: FiniteFloat
    returns_15s: FiniteFloat
    returns_1m: FiniteFloat
    returns_5m: FiniteFloat
    acceleration: FiniteFloat
    realized_volatility: FiniteFloat
    range_compression: FiniteFloat
    breakout_magnitude: FiniteFloat
    spread_fraction: FiniteFloat
    volume_rate: FiniteFloat
    oi_change: FiniteFloat | None
    iv_change: FiniteFloat | None
    premium_acceleration: FiniteFloat
    liquidity_score: FiniteFloat

    @model_validator(mode="after")
    def validate_times_and_bounds(self) -> PatternState:
        if self.data_cutoff > self.as_of:
            raise ValueError("pattern data_cutoff exceeds as_of")
        if not 0.0 <= self.liquidity_score <= 1.0:
            raise ValueError("liquidity_score must be in [0, 1]")
        if self.spread_fraction < 0.0:
            raise ValueError("spread_fraction must be non-negative")
        return self


class HistoricalAnalogue(ATSBaseModel):
    analogue_id: UUID
    state_time: UTCDateTime
    available_to_strategy_time: UTCDateTime
    regime: str
    vector: tuple[FiniteFloat, ...]
    favorable_excursion: FiniteFloat
    adverse_excursion: FiniteFloat
    forward_return: FiniteFloat
    forward_volatility: FiniteFloat

    @model_validator(mode="after")
    def validate_information_time(self) -> HistoricalAnalogue:
        if self.available_to_strategy_time < self.state_time:
            raise ValueError("analogue outcome availability precedes state")
        return self


class AnalogueDistribution(ATSBaseModel):
    support: AnalogueSupport
    analogue_count: int
    mean_similarity: FiniteFloat | None
    favorable_excursions: tuple[FiniteFloat, ...]
    adverse_excursions: tuple[FiniteFloat, ...]
    forward_returns: tuple[FiniteFloat, ...]
    forward_volatilities: tuple[FiniteFloat, ...]
    reason_codes: tuple[str, ...]


class OptionConvexityInput(ATSBaseModel):
    instrument_key: str
    premium: PositiveDecimal
    delta: FiniteFloat
    gamma: FiniteFloat
    theta_per_day: FiniteFloat
    iv: FiniteFloat
    spread_cost: NonNegativeDecimal
    slippage_cost: NonNegativeDecimal
    fee_cost: NonNegativeDecimal
    liquidity_score: FiniteFloat
    time_to_expiry_days: PositiveDecimal
    median_underlying_move: FiniteFloat
    tail_underlying_move: FiniteFloat
    execution_uncertainty: NonNegativeDecimal
    calibration_uncertainty: NonNegativeDecimal
    freshness: MarketStateFreshness
    reference_valid: bool

    @model_validator(mode="after")
    def validate_market_values(self) -> OptionConvexityInput:
        if not 0.0 <= self.liquidity_score <= 1.0:
            raise ValueError("liquidity_score must be in [0, 1]")
        if not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be in [-1, 1]")
        return self


class RareOpportunityPolicy(ATSBaseModel):
    minimum_analogue_support: PositiveInt = 20
    nearest_analogue_count: PositiveInt = 50
    maximum_spread_fraction: Decimal = Decimal("0.05")
    minimum_liquidity: Decimal = Decimal("0.60")
    minimum_expected_net_value: Decimal = Decimal("0")
    convex_asymmetry_ratio: Decimal = Decimal("2")
    rare_asymmetry_ratio: Decimal = Decimal("4")
    high_anomaly_score: Decimal = Decimal("2")
    rare_anomaly_score: Decimal = Decimal("3")
    convexity_budget_fraction: Decimal = Decimal("0.05")

    @model_validator(mode="after")
    def validate_policy(self) -> RareOpportunityPolicy:
        for name in (
            "maximum_spread_fraction",
            "minimum_liquidity",
            "convexity_budget_fraction",
        ):
            value = getattr(self, name)
            if not Decimal(0) <= value <= Decimal(1):
                raise ValueError(f"{name} must be in [0, 1]")
        if self.rare_asymmetry_ratio < self.convex_asymmetry_ratio:
            raise ValueError("rare asymmetry threshold must not be lower than convex")
        return self


class RareOpportunityAssessment(ATSBaseModel):
    assessment_id: UUID
    instrument_key: str
    opportunity_class: OpportunityClass
    eligible: bool
    anomaly_score: FiniteFloat
    analogue_count: int
    credible_downside: NonNegativeDecimal
    median_upside: NonNegativeDecimal
    tail_upside: NonNegativeDecimal
    expected_net_value: Decimal
    payoff_asymmetry_ratio: NonNegativeDecimal
    convexity_budget_fraction: NonNegativeDecimal
    reason_codes: tuple[str, ...]
    input_hash: Sha256
    payload_hash: Sha256


__all__ = [
    "AnalogueDistribution",
    "AnalogueSupport",
    "HistoricalAnalogue",
    "OpportunityClass",
    "OptionConvexityInput",
    "PatternState",
    "RareOpportunityAssessment",
    "RareOpportunityPolicy",
]
