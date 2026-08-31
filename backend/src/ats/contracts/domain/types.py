"""Strict supporting value types for the frozen A02 domain contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    Field,
    Strict,
    StringConstraints,
    model_validator,
)
from pydantic import (
    JsonValue as PydanticJsonValue,
)

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, Probability
from ats.contracts.enums import ATSStringEnum
from ats.contracts.ids import OpaqueId

NonEmptyStr = Annotated[str, StringConstraints(strict=True, min_length=1)]
InstrumentId = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z0-9][A-Z0-9._-]*$")]
Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
SemVer = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
            r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
            r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        ),
    ),
]
PositiveInt = Annotated[int, Strict(), Field(gt=0)]
NonNegativeInt = Annotated[int, Strict(), Field(ge=0)]
PositiveDecimal = Annotated[FiniteDecimal, Field(gt=Decimal(0))]
NonNegativeDecimal = Annotated[FiniteDecimal, Field(ge=Decimal(0))]
PortfolioFraction = Annotated[FiniteDecimal, Field(ge=Decimal(0), le=Decimal(1))]
UnitIntervalFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
SchemaV1 = Literal["1.0"]
Money = FiniteDecimal
QualityFlag = NonEmptyStr


def _validate_json_safe(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON float value must be finite")
        return value
    if isinstance(value, list):
        for item in value:
            _validate_json_safe(item)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON mapping keys must be strings")
            _validate_json_safe(item)
        return value
    raise ValueError("value is not JSON-safe")


JsonValue = Annotated[PydanticJsonValue, BeforeValidator(_validate_json_safe)]


class DataQualityState(ATSStringEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


class SessionState(ATSStringEnum):
    PREOPEN = "PREOPEN"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HALTED = "HALTED"


class ForecastStatus(ATSStringEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"


class EligibilityStatus(ATSStringEnum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class AutonomyLevel(ATSStringEnum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"


class PolicyStatus(ATSStringEnum):
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class LossState(ATSStringEnum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    COOLDOWN = "COOLDOWN"
    HALTED = "HALTED"


class RiskOutcome(ATSStringEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class AdvisoryOutcome(ATSStringEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"


class Side(ATSStringEnum):
    BUY = "BUY"
    SELL = "SELL"


class PaperOrderType(ATSStringEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LIMIT = "STOP_LIMIT"


class PaperOrderStatus(ATSStringEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class PositionStatus(ATSStringEnum):
    OPEN = "OPEN"
    REDUCED = "REDUCED"
    CLOSED = "CLOSED"


class ExitReason(ATSStringEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    TRAILING = "TRAILING"
    TIME = "TIME"
    RISK = "RISK"
    HALT = "HALT"


class AuditResult(ATSStringEnum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class PredicateOperator(ATSStringEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"


class SizingMode(ATSStringEnum):
    FIXED_QUANTITY = "FIXED_QUANTITY"
    PORTFOLIO_FRACTION = "PORTFOLIO_FRACTION"
    RISK_FRACTION = "RISK_FRACTION"


class ValueKind(ATSStringEnum):
    MONEY = "MONEY"
    PORTFOLIO_FRACTION = "PORTFOLIO_FRACTION"


class ProbabilityInterval(ATSBaseModel):
    low: Probability
    high: Probability

    @model_validator(mode="after")
    def validate_order(self) -> ProbabilityInterval:
        if self.high < self.low:
            raise ValueError("probability interval high must be >= low")
        return self


class UncertaintyEvidence(ATSBaseModel):
    method: NonEmptyStr
    score: FiniteFloat | None = None
    interval: ProbabilityInterval | None = None


class BaselineResult(ATSBaseModel):
    baseline_id: NonEmptyStr
    baseline_version: SemVer
    probability: Probability | None = None
    metrics: dict[str, FiniteFloat] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_metric_keys(self) -> BaselineResult:
        if any(not key for key in self.metrics):
            raise ValueError("baseline metric keys must be non-empty")
        return self


class ValidationIssue(ATSBaseModel):
    code: NonEmptyStr
    message: NonEmptyStr
    path: tuple[NonEmptyStr, ...] = ()


class DataRequirement(ATSBaseModel):
    requirement_id: NonEmptyStr
    description: NonEmptyStr
    required: bool = True


class Predicate(ATSBaseModel):
    field: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z][A-Za-z0-9_.]*$")]
    operator: PredicateOperator
    value: JsonValue

    @model_validator(mode="after")
    def validate_value(self) -> Predicate:
        if contains_executable_marker(self.value):
            raise ValueError("predicate value contains an executable marker")
        return self


class SizingRules(ATSBaseModel):
    mode: SizingMode
    value: PositiveDecimal
    maximum_quantity: PositiveDecimal | None = None


class MoneyOrPortfolioFraction(ATSBaseModel):
    kind: ValueKind
    value: PositiveDecimal

    @model_validator(mode="after")
    def validate_fraction(self) -> MoneyOrPortfolioFraction:
        if self.kind is ValueKind.PORTFOLIO_FRACTION and self.value > Decimal(1):
            raise ValueError("portfolio fraction must be <= 1")
        return self


class StopRule(ATSBaseModel):
    rule_id: NonEmptyStr
    trigger: Predicate
    hard_stop: bool


class TargetRule(ATSBaseModel):
    rule_id: NonEmptyStr
    trigger: Predicate


class TrailingRule(ATSBaseModel):
    rule_id: NonEmptyStr
    distance: MoneyOrPortfolioFraction


class TimeExitRule(ATSBaseModel):
    maximum_bars: PositiveInt


class PortfolioConstraints(ATSBaseModel):
    maximum_open_positions: PositiveInt
    maximum_gross_exposure: NonNegativeDecimal
    maximum_position_fraction: PortfolioFraction


class LossStatePolicy(ATSBaseModel):
    states: tuple[LossState, ...]

    @model_validator(mode="after")
    def validate_states(self) -> LossStatePolicy:
        required = (
            LossState.NORMAL,
            LossState.CAUTION,
            LossState.COOLDOWN,
            LossState.HALTED,
        )
        if self.states != required:
            raise ValueError("loss states must be NORMAL, CAUTION, COOLDOWN, HALTED")
        return self


class CooldownRule(ATSBaseModel):
    after_consecutive_losses: PositiveInt
    duration_bars: PositiveInt


class PolicyChangeProposal(ATSBaseModel):
    proposal_id: OpaqueId
    summary: NonEmptyStr
    changes: dict[str, JsonValue]
    executable: Literal[False] = False

    @model_validator(mode="after")
    def validate_change_keys(self) -> PolicyChangeProposal:
        if not self.changes or any(not key for key in self.changes):
            raise ValueError("policy proposal changes must have non-empty keys")
        if contains_executable_marker(self.changes):
            raise ValueError("policy proposal contains an executable marker")
        return self


def ensure_unique(values: tuple[object, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be deduplicated")


def ensure_non_empty_mapping_keys(values: Mapping[str, object], field_name: str) -> None:
    if any(not key for key in values):
        raise ValueError(f"{field_name} keys must be non-empty")


_EXECUTABLE_MARKERS = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|\blambda\b|python_source|module:function|shell_command)",
    re.IGNORECASE,
)


def contains_executable_marker(value: JsonValue) -> bool:
    if isinstance(value, str):
        return _EXECUTABLE_MARKERS.search(value) is not None
    if isinstance(value, list):
        return any(contains_executable_marker(item) for item in value)
    if isinstance(value, dict):
        return any(
            _EXECUTABLE_MARKERS.search(key) is not None or contains_executable_marker(item)
            for key, item in value.items()
        )
    return False


__all__ = [name for name in globals() if not name.startswith("_")]
