"""Strict data-only supporting types for IBA-C01 contracts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, Probability, UTCDateTime
from ats.contracts.domain.types import (
    ForecastStatus,
    InstrumentId,
    JsonValue,
    NonEmptyStr,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    Predicate,
    ProbabilityInterval,
    UnitIntervalFloat,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum


def _bounded_text(value: str) -> str:
    if "\x00" in value or not value.strip():
        raise ValueError("text must contain non-whitespace characters and no NUL")
    return value


RegisteredCode = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
    ),
]
BoundedText = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=4096),
    AfterValidator(_bounded_text),
]
PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0.0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]


class AssetClass(ATSStringEnum):
    CASH_EQUITY = "CASH_EQUITY"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    FUTURE = "FUTURE"
    INDEX = "INDEX"
    OTHER = "OTHER"


class Shortability(ATSStringEnum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class LiquidityState(ATSStringEnum):
    NORMAL = "NORMAL"
    THIN = "THIN"
    STRESSED = "STRESSED"
    UNKNOWN = "UNKNOWN"


class VolatilityState(ATSStringEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    UNKNOWN = "UNKNOWN"


class RegimeDirection(ATSStringEnum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class RegimeStructure(ATSStringEnum):
    TREND = "TREND"
    RANGE = "RANGE"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class ThesisStance(ATSStringEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class MarketThesisStatus(ATSStringEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class AnalystVerdict(ATSStringEnum):
    SUPPORTS = "SUPPORTS"
    CAUTIONS = "CAUTIONS"
    REJECTS = "REJECTS"
    UNKNOWN = "UNKNOWN"


class StrategyStatus(ATSStringEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    CHALLENGER = "CHALLENGER"
    CHAMPION = "CHAMPION"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class StrategyOrigin(ATSStringEnum):
    HUMAN = "HUMAN"
    LLM = "LLM"
    PARAMETER_SEARCH = "PARAMETER_SEARCH"
    SYMBOLIC_REGRESSION = "SYMBOLIC_REGRESSION"
    MUTATION = "MUTATION"


class FormulaPurpose(ATSStringEnum):
    FEATURE = "FEATURE"
    ENTRY_FILTER = "ENTRY_FILTER"
    EXIT_FILTER = "EXIT_FILTER"
    SCORE = "SCORE"
    PRICE_LEVEL = "PRICE_LEVEL"


class FormulaOutputKind(ATSStringEnum):
    BOOLEAN = "BOOLEAN"
    FINITE_FLOAT = "FINITE_FLOAT"
    DECIMAL = "DECIMAL"


class ExperimentType(ATSStringEnum):
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    REGIME_STRESS = "REGIME_STRESS"
    COST_STRESS = "COST_STRESS"
    PARAMETER_STABILITY = "PARAMETER_STABILITY"
    SHADOW_PAPER = "SHADOW_PAPER"


class ExperimentStatus(ATSStringEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"
    CANCELLED = "CANCELLED"


class LeakageScanStatus(ATSStringEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ScorecardValidationStatus(ATSStringEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class PromotionOutcome(ATSStringEnum):
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    DEFER = "DEFER"


class ApprovalMode(ATSStringEnum):
    AUTO_A2 = "AUTO_A2"
    HUMAN = "HUMAN"


class AttributionScope(ATSStringEnum):
    TRADE = "TRADE"
    CAMPAIGN = "CAMPAIGN"
    STRATEGY = "STRATEGY"
    SESSION = "SESSION"
    PORTFOLIO = "PORTFOLIO"


class AttributionCategory(ATSStringEnum):
    OPPORTUNITY_QUALITY = "OPPORTUNITY_QUALITY"
    FORECAST_ERROR = "FORECAST_ERROR"
    CALIBRATION_ERROR = "CALIBRATION_ERROR"
    REGIME_MISMATCH = "REGIME_MISMATCH"
    ENTRY_TIMING = "ENTRY_TIMING"
    EXIT_TIMING = "EXIT_TIMING"
    POSITION_SIZING = "POSITION_SIZING"
    SLIPPAGE = "SLIPPAGE"
    FEES = "FEES"
    RISK_REJECTION = "RISK_REJECTION"
    MISSED_OPPORTUNITY = "MISSED_OPPORTUNITY"
    INACTIVITY = "INACTIVITY"
    MARKET_OPPORTUNITY = "MARKET_OPPORTUNITY"
    OTHER = "OTHER"


class ExplanationAnswerability(ATSStringEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class PriceLevelKind(ATSStringEnum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"
    REFERENCE = "REFERENCE"


class RegimeAxis(ATSStringEnum):
    DIRECTION = "DIRECTION"
    STRUCTURE = "STRUCTURE"
    VOLATILITY = "VOLATILITY"
    LIQUIDITY = "LIQUIDITY"


class ParameterValueKind(ATSStringEnum):
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    CODE = "CODE"


class FormulaOperator(ATSStringEnum):
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    EQ = "EQ"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    SMA = "SMA"
    EMA = "EMA"
    ATR = "ATR"
    ROC = "ROC"
    RSI = "RSI"
    VWAP = "VWAP"
    ZSCORE = "ZSCORE"
    SLOPE = "SLOPE"
    PERCENTILE = "PERCENTILE"
    ROLLING_STD = "ROLLING_STD"
    ROLLING_CORR = "ROLLING_CORR"


class FormulaNodeKind(ATSStringEnum):
    LITERAL = "LITERAL"
    FEATURE = "FEATURE"
    OPERATOR = "OPERATOR"


class VersionedRef(ATSBaseModel):
    id: UUID
    version: PositiveInt


class StrategyRef(ATSBaseModel):
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt


class PriceLevel(ATSBaseModel):
    kind: PriceLevelKind
    price: PositiveDecimal
    source_ref: UUID


class OutcomeProbability(ATSBaseModel):
    outcome_code: RegisteredCode
    probability: Probability


class OutcomeInterval(ATSBaseModel):
    outcome_code: RegisteredCode
    interval: ProbabilityInterval


class RegimeConstraint(ATSBaseModel):
    axis: RegimeAxis
    allowed_values: tuple[RegisteredCode, ...]

    @model_validator(mode="after")
    def validate_values(self) -> RegimeConstraint:
        if not self.allowed_values:
            raise ValueError("allowed_values must be non-empty")
        ensure_unique(self.allowed_values, "allowed_values")
        return self


class ModelRequirement(ATSBaseModel):
    model_family: RegisteredCode
    allowed_versions: tuple[NonEmptyStr, ...]
    required: bool

    @model_validator(mode="after")
    def validate_versions(self) -> ModelRequirement:
        ensure_unique(self.allowed_versions, "allowed_versions")
        return self


class GuidelineProposal(ATSBaseModel):
    guideline_code: RegisteredCode
    conditions: tuple[Predicate, ...]
    rationale: BoundedText


class StrategyParameter(ATSBaseModel):
    parameter_code: RegisteredCode
    value_kind: ParameterValueKind
    integer_value: int | None
    decimal_value: FiniteDecimal | None
    float_value: FiniteFloat | None
    boolean_value: bool | None
    code_value: RegisteredCode | None

    @model_validator(mode="after")
    def validate_value(self) -> StrategyParameter:
        fields = {
            ParameterValueKind.INTEGER: self.integer_value,
            ParameterValueKind.DECIMAL: self.decimal_value,
            ParameterValueKind.FLOAT: self.float_value,
            ParameterValueKind.BOOLEAN: self.boolean_value,
            ParameterValueKind.CODE: self.code_value,
        }
        if (
            sum(value is not None for value in fields.values()) != 1
            or fields[self.value_kind] is None
        ):
            raise ValueError("exactly the value matching value_kind must be supplied")
        return self


class FormulaNode(ATSBaseModel):
    node_kind: FormulaNodeKind
    operator: FormulaOperator | None
    arguments: tuple[FormulaNode, ...]
    feature_code: RegisteredCode | None
    lag_bars: NonNegativeInt | None
    literal_decimal: FiniteDecimal | None
    literal_float: FiniteFloat | None
    literal_int: int | None
    literal_bool: bool | None

    @model_validator(mode="after")
    def validate_shape(self) -> FormulaNode:
        literals = (self.literal_decimal, self.literal_float, self.literal_int, self.literal_bool)
        if self.node_kind is FormulaNodeKind.LITERAL:
            if (
                self.operator is not None
                or self.arguments
                or self.feature_code is not None
                or self.lag_bars is not None
                or sum(v is not None for v in literals) != 1
            ):
                raise ValueError("invalid LITERAL node")
        elif self.node_kind is FormulaNodeKind.FEATURE:
            if (
                self.operator is not None
                or self.arguments
                or self.feature_code is None
                or self.lag_bars is None
                or any(v is not None for v in literals)
            ):
                raise ValueError("invalid FEATURE node")
        elif (
            self.operator is None
            or not self.arguments
            or self.feature_code is not None
            or self.lag_bars is not None
            or any(v is not None for v in literals)
        ):
            raise ValueError("invalid OPERATOR node")
        return self


class AnalogueMatch(ATSBaseModel):
    analogue_id: UUID
    instrument_id: InstrumentId
    window_start: UTCDateTime
    window_end: UTCDateTime
    similarity_score: UnitIntervalFloat
    raw_distance: FiniteFloat | None
    regime_similarity: UnitIntervalFloat | None
    forward_outcome_code: RegisteredCode
    forward_return_fraction: FiniteFloat
    maximum_favourable_excursion_fraction: FiniteFloat
    maximum_adverse_excursion_fraction: FiniteFloat

    @model_validator(mode="after")
    def validate_window(self) -> AnalogueMatch:
        if self.window_end < self.window_start:
            raise ValueError("window_end must be >= window_start")
        return self


class AnalogueOutcomeStat(ATSBaseModel):
    outcome_code: RegisteredCode
    count: NonNegativeInt
    empirical_probability: Probability
    median_forward_return_fraction: FiniteFloat
    median_mfe_fraction: FiniteFloat
    median_mae_fraction: FiniteFloat


class EnsembleMember(ATSBaseModel):
    forecast_id: UUID
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    weight: UnitIntervalFloat
    status: ForecastStatus


class CalibratedOutcome(ATSBaseModel):
    outcome_code: RegisteredCode
    probability: Probability
    interval: ProbabilityInterval

    @model_validator(mode="after")
    def validate_interval(self) -> CalibratedOutcome:
        if not self.interval.low <= self.probability <= self.interval.high:
            raise ValueError("interval must contain probability")
        return self


class AttributionComponent(ATSBaseModel):
    category: AttributionCategory
    contribution_money: FiniteDecimal
    contribution_r: FiniteFloat
    confidence_score: UnitIntervalFloat
    evidence_refs: tuple[UUID, ...]

    @model_validator(mode="after")
    def validate_refs(self) -> AttributionComponent:
        if not self.evidence_refs:
            raise ValueError("evidence_refs must be non-empty")
        ensure_unique(self.evidence_refs, "evidence_refs")
        return self


class ExplanationFact(ATSBaseModel):
    fact_code: RegisteredCode
    fact_value: JsonValue
    evidence_refs: tuple[UUID, ...]

    @model_validator(mode="after")
    def validate_refs(self) -> ExplanationFact:
        if not self.evidence_refs:
            raise ValueError("evidence_refs must be non-empty")
        ensure_unique(self.evidence_refs, "evidence_refs")
        return self


__all__ = [name for name in globals() if not name.startswith("_")]
