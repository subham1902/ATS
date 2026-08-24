"""Strict observation inputs for the R11 advisory boundary."""

from __future__ import annotations

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.models import Position
from ats.contracts.domain.types import DataQualityState, PositiveDecimal
from ats.contracts.governance.models import (
    OpportunityCandidate,
    PositionThesis,
    TradingCampaign,
)
from ats.contracts.intelligence.models import CalibratedOutcomeDistribution, MarketThesis
from pydantic import model_validator


class PositionObservation(ATSBaseModel):
    """Caller-supplied, deterministic facts; no market or broker lookup occurs here."""

    position: Position
    originating_candidate: OpportunityCandidate
    entry_thesis: MarketThesis
    current_thesis: MarketThesis
    distribution: CalibratedOutcomeDistribution
    campaign: TradingCampaign
    data_cutoff: UTCDateTime
    evaluation_time: UTCDateTime
    data_quality_state: DataQualityState
    maximum_favourable_excursion_r: FiniteFloat
    maximum_adverse_excursion_r: FiniteFloat
    initial_risk_per_unit: PositiveDecimal
    invalidation_triggered: bool
    risk_reduction_required: bool
    session_exit_required: bool

    @model_validator(mode="after")
    def validate_temporal_facts(self) -> PositionObservation:
        if self.data_cutoff > self.evaluation_time:
            raise ValueError("data_cutoff must be <= evaluation_time")
        return self


class PositionEvaluationResult(ATSBaseModel):
    thesis: PositionThesis
    reason_codes: tuple[str, ...]


__all__ = ["PositionEvaluationResult", "PositionObservation"]
