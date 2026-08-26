"""Harness R&D Agent adapter for research hypothesis formulation and challenger comparisons."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import StrategyScorecard

from .hypothesis import build_research_hypothesis
from .models import (
    ExperimentProposal,
    ResearchHypothesis,
    ResearchRecommendation,
    ResearchRecommendationAction,
)


class HarnessResearchAgent:
    """Zero-authority research advisor interfacing with Harness/LLM inference."""

    def __init__(self, sidecar: Any | None = None) -> None:
        self._sidecar = sidecar

    def formulate_hypothesis(
        self,
        *,
        question: str,
        rationale: str,
        evidence_refs: tuple[UUID, ...],
        market_regime_scope: tuple[str, ...],
        dataset_scope: str,
        as_of: UTCDateTime,
    ) -> ResearchHypothesis:
        """Formulate a strict typed hypothesis, with or without active LLM sidecar."""
        return build_research_hypothesis(
            question=question,
            rationale=rationale,
            evidence_refs=evidence_refs,
            market_regime_scope=market_regime_scope,
            dataset_scope=dataset_scope,
            created_at=as_of,
            data_cutoff=as_of,
        )

    def propose_experiment(
        self,
        *,
        hypothesis: ResearchHypothesis,
        strategy_definition_id: UUID,
        strategy_definition_version: int,
        instrument_universe: tuple[str, ...],
        timeframe: str,
        as_of: UTCDateTime,
    ) -> ExperimentProposal:
        """Construct a bounded experiment proposal for Strategy Lab execution."""
        return ExperimentProposal(
            proposal_id=uuid4(),
            hypothesis_id=hypothesis.hypothesis_id,
            strategy_definition_id=strategy_definition_id,
            strategy_definition_version=strategy_definition_version,
            instrument_universe=instrument_universe,
            timeframe=timeframe,
            dataset_scope=hypothesis.dataset_scope,
            train_bars=500,
            validation_bars=200,
            test_bars=200,
            created_at=as_of,
        )

    def compare_challenger(
        self,
        *,
        hypothesis_id: UUID,
        champion_scorecard: StrategyScorecard | None,
        challenger_scorecard: StrategyScorecard,
        as_of: UTCDateTime,
    ) -> ResearchRecommendation:
        """Compare scorecard metrics and provide an advisory recommendation.

        Note: Deterministic PromotionGate remains the final authority.
        """
        # Baseline check
        challenger_pnl = challenger_scorecard.net_return_fraction
        challenger_pf = challenger_scorecard.profit_factor or 0.0

        if champion_scorecard is None:
            if challenger_pnl > 0 and challenger_pf > 1.2:
                action = ResearchRecommendationAction.PROMOTE
                rationale = (
                    "Challenger exhibits strong initial baseline metrics with no prior champion"
                )
                conf = Decimal("0.80")
            else:
                action = ResearchRecommendationAction.REJECT
                rationale = "Challenger fails basic profitability and profit factor thresholds"
                conf = Decimal("0.90")
        else:
            champ_pnl = champion_scorecard.net_return_fraction
            champ_pf = champion_scorecard.profit_factor or 0.0
            if challenger_pnl > champ_pnl and challenger_pf > champ_pf:
                action = ResearchRecommendationAction.PROMOTE
                rationale = (
                    f"Challenger outperforms champion (PF {challenger_pf:.2f} vs {champ_pf:.2f})"
                )
                conf = Decimal("0.85")
            elif challenger_pnl > 0:
                action = ResearchRecommendationAction.DEFER
                rationale = "Challenger is profitable but does not surpass incumbent champion"
                conf = Decimal("0.70")
            else:
                action = ResearchRecommendationAction.REJECT
                rationale = "Challenger is unprofitable or degraded compared to champion"
                conf = Decimal("0.95")

        return ResearchRecommendation(
            recommendation_id=uuid4(),
            hypothesis_id=hypothesis_id,
            strategy_id=challenger_scorecard.strategy_definition_id,
            action=action,
            rationale=rationale,
            confidence_score=conf,
            evidence_refs=(challenger_scorecard.scorecard_id,),
            created_at=as_of,
        )


__all__ = ["HarnessResearchAgent"]
