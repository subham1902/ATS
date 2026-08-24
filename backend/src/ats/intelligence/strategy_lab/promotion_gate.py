"""Deterministic research-promotion evaluation.

The frozen ``PromotionDecision`` can only represent evidence for which risk
constraints are unchanged. Failed prerequisites therefore remain an
internal evaluation result and never get normalized into a dishonest frozen
decision.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.enums import ATSStringEnum
from ats.contracts.intelligence.models import PromotionDecision, StrategyScorecard
from ats.contracts.intelligence.types import (
    ApprovalMode,
    PromotionOutcome,
    RegisteredCode,
    ScorecardValidationStatus,
    StrategyRef,
)


class PromotionEvaluationStatus(ATSStringEnum):
    """Closed outcomes before the frozen promotion-decision boundary."""

    PROMOTABLE_DECISION = "PROMOTABLE_DECISION"
    REJECTED_BEFORE_DECISION = "REJECTED_BEFORE_DECISION"
    DEFERRED_BEFORE_DECISION = "DEFERRED_BEFORE_DECISION"


class PromotionEvaluationResult(ATSBaseModel):
    """Truthful package-level result of deterministic promotion evaluation."""

    status: PromotionEvaluationStatus
    promotion_decision: PromotionDecision | None
    risk_constraints_unchanged: bool
    reason_codes: tuple[RegisteredCode, ...]

    @model_validator(mode="after")
    def validate_boundary(self) -> PromotionEvaluationResult:
        if self.status is PromotionEvaluationStatus.PROMOTABLE_DECISION:
            if self.promotion_decision is None or not self.risk_constraints_unchanged:
                raise ValueError("promotable evaluation requires truthful frozen decision evidence")
        elif self.promotion_decision is not None:
            raise ValueError("pre-decision rejection/defer cannot contain PromotionDecision")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be unique")
        return self


def _reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(code for group in groups for code in group))


def _pre_decision(
    *,
    status: PromotionEvaluationStatus,
    risk_constraints_unchanged: bool,
    supplied_reasons: tuple[str, ...],
    gate_reasons: tuple[str, ...],
) -> PromotionEvaluationResult:
    return PromotionEvaluationResult(
        status=status,
        promotion_decision=None,
        risk_constraints_unchanged=risk_constraints_unchanged,
        reason_codes=_reasons(supplied_reasons, gate_reasons),
    )


def evaluate_promotion(
    *,
    promotion_decision_id: UUID,
    candidate_strategy_ref: tuple[UUID, int],
    incumbent_strategy_ref: tuple[UUID, int] | None,
    scorecard: StrategyScorecard,
    required_gates_passed: bool,
    minimum_evidence_met: bool,
    risk_constraints_unchanged: bool,
    approval_mode: ApprovalMode,
    decided_at: UTCDateTime,
    effective_from: UTCDateTime | None,
    approved_by: str | None,
    approved_at: UTCDateTime | None,
    reason_codes: tuple[str, ...] = (),
) -> PromotionEvaluationResult:
    """Evaluate promotion without fabricating facts forbidden by the contract."""

    if not risk_constraints_unchanged:
        return _pre_decision(
            status=PromotionEvaluationStatus.REJECTED_BEFORE_DECISION,
            risk_constraints_unchanged=False,
            supplied_reasons=reason_codes,
            gate_reasons=("RISK_CONSTRAINTS_CHANGED",),
        )
    if (
        not minimum_evidence_met
        or scorecard.validation_status is not ScorecardValidationStatus.PASS
    ):
        reasons: tuple[str, ...] = ()
        if not minimum_evidence_met:
            reasons += ("MINIMUM_EVIDENCE_NOT_MET",)
        if scorecard.validation_status is not ScorecardValidationStatus.PASS:
            reasons += ("SCORECARD_NOT_PASS",)
        return _pre_decision(
            status=PromotionEvaluationStatus.DEFERRED_BEFORE_DECISION,
            risk_constraints_unchanged=True,
            supplied_reasons=reason_codes,
            gate_reasons=reasons,
        )

    rejection_reasons: tuple[str, ...] = ()
    if not required_gates_passed:
        rejection_reasons += ("REQUIRED_GATES_NOT_PASSED",)
    if effective_from is None or effective_from < decided_at:
        rejection_reasons += ("INVALID_EFFECTIVE_TIME",)
    if approval_mode is ApprovalMode.HUMAN and (approved_by is None or approved_at is None):
        rejection_reasons += ("HUMAN_APPROVAL_INCOMPLETE",)
    if rejection_reasons:
        return _pre_decision(
            status=PromotionEvaluationStatus.REJECTED_BEFORE_DECISION,
            risk_constraints_unchanged=True,
            supplied_reasons=reason_codes,
            gate_reasons=rejection_reasons,
        )

    candidate_ref = StrategyRef(
        strategy_definition_id=candidate_strategy_ref[0],
        strategy_definition_version=candidate_strategy_ref[1],
    )
    incumbent_ref = None
    if incumbent_strategy_ref is not None:
        incumbent_ref = StrategyRef(
            strategy_definition_id=incumbent_strategy_ref[0],
            strategy_definition_version=incumbent_strategy_ref[1],
        )
    assert effective_from is not None
    decision = PromotionDecision(
        schema_version="1.0",
        promotion_decision_id=promotion_decision_id,
        candidate_strategy_ref=candidate_ref,
        incumbent_strategy_ref=incumbent_ref,
        scorecard_ids=(scorecard.scorecard_id,),
        decision=PromotionOutcome.PROMOTE,
        target_status="CHAMPION",
        approval_mode=approval_mode,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approved_by=approved_by,
        approved_at=approved_at,
        effective_from=effective_from,
        reason_codes=_reasons(reason_codes),
        decided_at=decided_at,
        payload_hash="0" * 64,
    )
    decision = decision.model_copy(update={"payload_hash": compute_payload_hash(decision)})
    return PromotionEvaluationResult(
        status=PromotionEvaluationStatus.PROMOTABLE_DECISION,
        promotion_decision=decision,
        risk_constraints_unchanged=True,
        reason_codes=_reasons(reason_codes),
    )


__all__ = ["PromotionEvaluationResult", "PromotionEvaluationStatus", "evaluate_promotion"]
