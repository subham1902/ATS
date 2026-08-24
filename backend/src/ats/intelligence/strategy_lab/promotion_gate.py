"""PromotionGate — deterministic PromotionDecision production."""

from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import PromotionDecision, StrategyScorecard
from ats.contracts.intelligence.types import ApprovalMode, PromotionOutcome


def _payload_hash(pid: UUID) -> str:
    return sha256(str(pid).encode()).hexdigest()


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
) -> PromotionDecision:
    """Deterministic gate.

    PROMOTE requires: gates passed, evidence met, risk unchanged, PASS scorecard, effective_from.
    HUMAN requires approval fields.
    """
    from ats.contracts.intelligence.types import StrategyRef

    cand_ref = StrategyRef(
        strategy_definition_id=candidate_strategy_ref[0],
        strategy_definition_version=candidate_strategy_ref[1],
    )
    inc_ref = None
    if incumbent_strategy_ref is not None:
        inc_ref = StrategyRef(
            strategy_definition_id=incumbent_strategy_ref[0],
            strategy_definition_version=incumbent_strategy_ref[1],
        )

    # Determine outcome deterministically
    if (
        required_gates_passed
        and minimum_evidence_met
        and risk_constraints_unchanged
        and scorecard.validation_status.value == "PASS"
        and effective_from is not None
        and effective_from >= decided_at
        and (
            approval_mode is not ApprovalMode.HUMAN
            or (approved_by is not None and approved_at is not None)
        )
    ):
        outcome = PromotionOutcome.PROMOTE
    elif not minimum_evidence_met or scorecard.validation_status.value != "PASS":
        outcome = PromotionOutcome.DEFER
    else:
        outcome = PromotionOutcome.REJECT

    # Enforce contract invariants for decision type
    if outcome is PromotionOutcome.PROMOTE:
        # must have effective_from
        assert effective_from is not None
    else:
        effective_from = None

    return PromotionDecision(
        schema_version="1.0",
        promotion_decision_id=promotion_decision_id,
        candidate_strategy_ref=cand_ref,
        incumbent_strategy_ref=inc_ref,
        scorecard_ids=(scorecard.scorecard_id,),
        decision=outcome,
        target_status="CHAMPION",
        approval_mode=approval_mode,
        required_gates_passed=required_gates_passed,
        minimum_evidence_met=minimum_evidence_met,
        risk_constraints_unchanged=True,  # frozen literal True per contract
        approved_by=approved_by,
        approved_at=approved_at,
        effective_from=effective_from,
        reason_codes=reason_codes,
        decided_at=decided_at,
        payload_hash=_payload_hash(promotion_decision_id),
    )


__all__ = ["evaluate_promotion"]
