"""Immutable deterministic paper-execution inputs and results."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.models import Fill, PaperOrder
from ats.contracts.domain.types import (
    DataQualityState,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
)
from ats.contracts.intelligence.types import RegisteredCode


class PaperSubmissionScenario(StrEnum):
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REJECT = "REJECT"
    TIMEOUT_UNKNOWN = "TIMEOUT_UNKNOWN"


class PaperSubmissionState(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ObservedSubmissionState(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class ReconciliationOutcome(StrEnum):
    CONFIRMED_PRESENT = "CONFIRMED_PRESENT"
    CONFIRMED_ABSENT = "CONFIRMED_ABSENT"
    STILL_UNKNOWN = "STILL_UNKNOWN"


class PaperExecutionPolicy(ATSBaseModel):
    broker_model_version: NonEmptyStr
    cost_model_version: NonEmptyStr
    maximum_quote_age_ms: PositiveInt
    slippage_ticks: NonNegativeInt
    fee_fraction: NonNegativeDecimal
    tax_fraction: NonNegativeDecimal


class PaperMarketFacts(ATSBaseModel):
    instrument_id: RegisteredCode
    bid: PositiveDecimal | None
    ask: PositiveDecimal | None
    bid_quantity: NonNegativeInt | None
    ask_quantity: NonNegativeInt | None
    quote_time: UTCDateTime
    quality_state: DataQualityState
    scenario: PaperSubmissionScenario
    rejection_reason: NonEmptyStr | None

    @model_validator(mode="after")
    def validate_scenario(self) -> PaperMarketFacts:
        if self.scenario is PaperSubmissionScenario.REJECT and self.rejection_reason is None:
            raise ValueError("rejected scenario requires a reason")
        if (
            self.scenario is not PaperSubmissionScenario.REJECT
            and self.rejection_reason is not None
        ):
            raise ValueError("rejection reason is valid only for rejected scenario")
        return self


class PaperExecutionResult(ATSBaseModel):
    submission_state: PaperSubmissionState
    order: PaperOrder | None
    fills: tuple[Fill, ...]
    reason_codes: tuple[RegisteredCode, ...]


class SubmissionObservation(ATSBaseModel):
    state: ObservedSubmissionState
    order: PaperOrder | None
    observed_at: UTCDateTime

    @model_validator(mode="after")
    def validate_presence(self) -> SubmissionObservation:
        if (self.state is ObservedSubmissionState.PRESENT) != (self.order is not None):
            raise ValueError("PRESENT must contain the observed order and other states must not")
        return self


class PaperReconciliationResult(ATSBaseModel):
    outcome: ReconciliationOutcome
    order: PaperOrder | None
    retry_permitted: Literal[False]
    reason_codes: tuple[RegisteredCode, ...]


__all__ = [
    "ObservedSubmissionState",
    "PaperExecutionPolicy",
    "PaperExecutionResult",
    "PaperMarketFacts",
    "PaperReconciliationResult",
    "PaperSubmissionScenario",
    "PaperSubmissionState",
    "ReconciliationOutcome",
    "SubmissionObservation",
]
