"""Immutable inputs and bounded results for R07 thesis synthesis."""

from __future__ import annotations

from enum import StrEnum

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, Probability
from ats.contracts.domain.types import NonEmptyStr, Predicate
from ats.contracts.intelligence.models import MarketThesis
from ats.contracts.intelligence.types import PriceLevel, RegisteredCode


class ThesisSynthesisStatus(StrEnum):
    ACTIVE_THESIS = "ACTIVE_THESIS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ThesisSynthesisConfiguration(ATSBaseModel):
    synthesizer_id: RegisteredCode
    synthesizer_version: NonEmptyStr
    bullish_outcome_code: RegisteredCode
    bearish_outcome_code: RegisteredCode
    activation_probability: Probability
    validity_ms: PositiveInt

    @model_validator(mode="after")
    def validate_semantics(self) -> ThesisSynthesisConfiguration:
        if self.bullish_outcome_code == self.bearish_outcome_code:
            raise ValueError("bullish and bearish outcome codes must differ")
        if self.activation_probability <= 0.5:
            raise ValueError("activation probability must be greater than one half")
        return self


class ThesisSynthesisFacts(ATSBaseModel):
    support_levels: tuple[PriceLevel, ...]
    resistance_levels: tuple[PriceLevel, ...]
    opportunity_conditions: tuple[Predicate, ...]
    invalidation_conditions: tuple[Predicate, ...]


class ThesisSynthesisResult(ATSBaseModel):
    status: ThesisSynthesisStatus
    thesis: MarketThesis | None
    reason_codes: tuple[RegisteredCode, ...]


__all__ = [
    "ThesisSynthesisConfiguration",
    "ThesisSynthesisFacts",
    "ThesisSynthesisResult",
    "ThesisSynthesisStatus",
]
