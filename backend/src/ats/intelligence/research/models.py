"""Typed contracts for the R&D Brain and Champion/Challenger research pipeline."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, Sha256, ensure_unique
from ats.contracts.intelligence.models import (
    FormulaDefinition,
    StrategyDefinition,
    StrategyScorecard,
)
from ats.contracts.intelligence.types import RegisteredCode


class StrategyLifecycleStatus(StrEnum):
    CHAMPION = "CHAMPION"
    CHALLENGER = "CHALLENGER"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class DegradationAction(StrEnum):
    REVIEW = "REVIEW"
    REDUCE_ALLOCATION = "REDUCE_ALLOCATION"
    PAUSE_STRATEGY = "PAUSE_STRATEGY"
    EVALUATE_CHALLENGER = "EVALUATE_CHALLENGER"
    HEALTHY = "HEALTHY"


class ResearchRecommendationAction(StrEnum):
    PROMOTE = "PROMOTE"
    DEFER = "DEFER"
    REJECT = "REJECT"


class ResearchHypothesis(ATSBaseModel):
    schema_version: Literal["1.0"] = "1.0"
    hypothesis_id: UUID
    question: NonEmptyStr
    rationale: NonEmptyStr
    evidence_refs: tuple[UUID, ...]
    market_regime_scope: tuple[RegisteredCode, ...]
    proposed_formula: FormulaDefinition | None = None
    proposed_strategy: StrategyDefinition | None = None
    dataset_scope: NonEmptyStr
    created_at: UTCDateTime
    data_cutoff: UTCDateTime
    input_hash: Sha256
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_hypothesis(self) -> ResearchHypothesis:
        if self.data_cutoff > self.created_at:
            raise ValueError("data_cutoff must be <= created_at")
        ensure_unique(self.evidence_refs, "evidence_refs")
        ensure_unique(self.market_regime_scope, "market_regime_scope")
        if not self.market_regime_scope:
            raise ValueError("market_regime_scope must not be empty")
        return self


class ExperimentProposal(ATSBaseModel):
    proposal_id: UUID
    hypothesis_id: UUID
    strategy_definition_id: UUID
    strategy_definition_version: int
    instrument_universe: tuple[RegisteredCode, ...]
    timeframe: RegisteredCode
    dataset_scope: NonEmptyStr
    train_bars: int
    validation_bars: int
    test_bars: int
    purge_bars: int = 10
    embargo_bars: int = 10
    created_at: UTCDateTime


class ChampionRecord(ATSBaseModel):
    family: RegisteredCode
    strategy_id: UUID
    strategy_version: int
    lifecycle_status: StrategyLifecycleStatus
    scorecard: StrategyScorecard | None = None
    promoted_at: UTCDateTime | None = None
    retired_at: UTCDateTime | None = None
    notes: NonEmptyStr = "Active registered strategy"


class DegradationMetric(ATSBaseModel):
    rolling_expectancy_r: FiniteFloat
    profit_factor: FiniteFloat
    drawdown_fraction: FiniteDecimal
    cost_sensitivity: FiniteFloat
    calibration_drift: FiniteFloat
    sample_count: int


class DegradationAssessment(ATSBaseModel):
    strategy_id: UUID
    strategy_version: int
    action: DegradationAction
    reasons: tuple[NonEmptyStr, ...]
    metrics: DegradationMetric
    evaluated_at: UTCDateTime


class ResearchRecommendation(ATSBaseModel):
    recommendation_id: UUID
    hypothesis_id: UUID
    strategy_id: UUID
    action: ResearchRecommendationAction
    rationale: NonEmptyStr
    confidence_score: Decimal
    evidence_refs: tuple[UUID, ...]
    created_at: UTCDateTime


__all__ = [
    "ChampionRecord",
    "DegradationAction",
    "DegradationAssessment",
    "DegradationMetric",
    "ExperimentProposal",
    "ResearchHypothesis",
    "ResearchRecommendation",
    "ResearchRecommendationAction",
    "StrategyLifecycleStatus",
]
