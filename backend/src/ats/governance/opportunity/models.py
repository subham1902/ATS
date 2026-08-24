"""Immutable R10 candidate-construction inputs and results."""

from __future__ import annotations

from enum import StrEnum

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, PositiveDecimal
from ats.contracts.governance.models import OpportunityCandidate
from ats.contracts.intelligence.types import RegisteredCode
from pydantic import PositiveInt, model_validator


class OpportunityConstructionStatus(StrEnum):
    ELIGIBLE_CANDIDATE = "ELIGIBLE_CANDIDATE"
    INELIGIBLE = "INELIGIBLE"


class OpportunityConstructionConfiguration(ATSBaseModel):
    governor_id: RegisteredCode
    governor_version: NonEmptyStr
    target_outcome_code: RegisteredCode
    maximum_ttl_ms: PositiveInt


class OpportunityEconomicsFacts(ATSBaseModel):
    maximum_loss: PositiveDecimal
    expected_reward: PositiveDecimal
    proposed_stop_price: PositiveDecimal
    proposed_target_price: PositiveDecimal

    @model_validator(mode="after")
    def validate_prices(self) -> OpportunityEconomicsFacts:
        if self.proposed_stop_price >= self.proposed_target_price:
            raise ValueError("proposed stop must be below target for a long option")
        return self


class OpportunityConstructionResult(ATSBaseModel):
    status: OpportunityConstructionStatus
    candidate: OpportunityCandidate | None
    reason_codes: tuple[RegisteredCode, ...]


__all__ = [
    "OpportunityConstructionConfiguration",
    "OpportunityConstructionResult",
    "OpportunityConstructionStatus",
    "OpportunityEconomicsFacts",
]
