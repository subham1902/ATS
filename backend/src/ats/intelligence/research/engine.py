"""R&D Brain orchestrator for research experiments and champion-challenger pipeline."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import (
    FormulaDefinition,
    PromotionDecision,
    StrategyDefinition,
    StrategyScorecard,
)
from ats.contracts.intelligence.types import ApprovalMode

from ..strategy_lab.promotion_gate import (
    PromotionEvaluationResult,
    PromotionEvaluationStatus,
    evaluate_promotion,
)
from .agent import HarnessResearchAgent
from .champion_challenger import ChampionChallengerRegistry
from .degradation import StrategyDegradationMonitor
from .hypothesis import build_research_hypothesis
from .models import (
    ChampionRecord,
    DegradationAssessment,
    DegradationMetric,
    ResearchHypothesis,
)


class ResearchBrainEngine:
    """Zero-financial-authority research engine.

    Orchestrates:
    - Hypothesis generation
    - Strategy experiment execution on Historical Truth
    - Out-of-sample scorecard synthesis
    - Deterministic promotion gating
    - Champion / Challenger lifecycle tracking
    - Ongoing degradation assessment
    """

    def __init__(
        self,
        *,
        registry: ChampionChallengerRegistry | None = None,
        degradation_monitor: StrategyDegradationMonitor | None = None,
        research_agent: HarnessResearchAgent | None = None,
    ) -> None:
        self.registry = registry or ChampionChallengerRegistry()
        self.degradation_monitor = degradation_monitor or StrategyDegradationMonitor()
        self.research_agent = research_agent or HarnessResearchAgent()

    def create_hypothesis(
        self,
        *,
        question: str,
        rationale: str,
        evidence_refs: tuple[UUID, ...],
        market_regime_scope: tuple[str, ...],
        dataset_scope: str,
        as_of: UTCDateTime,
        proposed_formula: FormulaDefinition | None = None,
        proposed_strategy: StrategyDefinition | None = None,
    ) -> ResearchHypothesis:
        """Formulate a strict, tamper-evident research hypothesis."""
        return build_research_hypothesis(
            question=question,
            rationale=rationale,
            evidence_refs=evidence_refs,
            market_regime_scope=market_regime_scope,
            dataset_scope=dataset_scope,
            created_at=as_of,
            data_cutoff=as_of,
            proposed_formula=proposed_formula,
            proposed_strategy=proposed_strategy,
        )

    def evaluate_challenger_promotion(
        self,
        *,
        scorecard: StrategyScorecard,
        incumbent_scorecard: StrategyScorecard | None = None,
        evaluation_time: UTCDateTime,
        is_baseline_only: bool = False,
    ) -> PromotionEvaluationResult:
        """Deterministically evaluate whether a challenger qualifies for promotion."""
        if is_baseline_only:
            # Explicit rule: Do not promote baseline merely because PnL is positive
            return PromotionEvaluationResult(
                status=PromotionEvaluationStatus.REJECTED_BEFORE_DECISION,
                promotion_decision=None,
                risk_constraints_unchanged=True,
                reason_codes=("BASELINE_STRATEGY_NOT_LIVE_ELIGIBLE",),
            )

        candidate_ref = (
            scorecard.strategy_definition_id,
            scorecard.strategy_definition_version,
        )
        incumbent_ref = (
            (
                incumbent_scorecard.strategy_definition_id,
                incumbent_scorecard.strategy_definition_version,
            )
            if incumbent_scorecard
            else None
        )

        from uuid import uuid4

        # Deterministic criteria: net return > 0, profit factor >= 1.2, max drawdown <= 0.10
        gates_passed = (
            scorecard.net_return_fraction > 0.0
            and (scorecard.profit_factor or 0.0) >= 1.2
            and scorecard.maximum_drawdown <= Decimal("0.10")
        )
        min_evidence = scorecard.trade_count >= 30 and scorecard.sample_count >= 30

        return evaluate_promotion(
            promotion_decision_id=uuid4(),
            candidate_strategy_ref=candidate_ref,
            incumbent_strategy_ref=incumbent_ref,
            scorecard=scorecard,
            required_gates_passed=gates_passed,
            minimum_evidence_met=min_evidence,
            risk_constraints_unchanged=True,
            approval_mode=ApprovalMode.AUTO_A2,
            decided_at=evaluation_time,
            effective_from=evaluation_time,
            approved_by="ResearchBrainEngine.v1",
            approved_at=evaluation_time,
            reason_codes=(),
        )

    def apply_promotion_decision(
        self,
        *,
        strategy_id: UUID,
        promotion_decision: PromotionDecision,
        promoted_at: UTCDateTime,
    ) -> ChampionRecord:
        """Apply approved promotion decision to the Champion registry."""
        return self.registry.promote_to_champion(
            strategy_id=strategy_id,
            promotion_decision=promotion_decision,
            promoted_at=promoted_at,
        )

    def assess_strategy_health(
        self,
        *,
        strategy_id: UUID,
        strategy_version: int,
        metrics: DegradationMetric,
        evaluated_at: UTCDateTime,
    ) -> DegradationAssessment:
        """Monitor ongoing performance and flag degradation triggers."""
        return self.degradation_monitor.assess(
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            metrics=metrics,
            evaluated_at=evaluated_at,
        )


__all__ = ["ResearchBrainEngine"]
