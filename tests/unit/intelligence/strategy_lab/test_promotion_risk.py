"""R14-F02: Promotion risk_constraints_unchanged + enum/finite safety tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ats.contracts.intelligence.types import ApprovalMode, ScorecardValidationStatus
from ats.intelligence.strategy_lab.promotion_gate import (
    PromotionEvaluationStatus,
    evaluate_promotion,
)
from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.intelligence.strategy_lab.types import (
    BacktestResult,
    ResearchFill,
    ResearchTrade,
)


def _pass_scorecard():
    now = datetime(2024, 1, 10, tzinfo=UTC)
    fe = ResearchFill(
        fill_id=uuid4(),
        signal_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        side="BUY",
        price=Decimal("100"),
        quantity=Decimal("10"),
        bar_timestamp=now,
        bar_sequence=1,
        cost=Decimal("1"),
    )
    fx = ResearchFill(
        fill_id=uuid4(),
        signal_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        side="SELL",
        price=Decimal("102"),
        quantity=Decimal("10"),
        bar_timestamp=now,
        bar_sequence=2,
        cost=Decimal("1"),
    )
    tr = ResearchTrade(
        trade_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        entry_fill=fe,
        exit_fill=fx,
        entry_time=now,
        exit_time=now,
        pnl_fraction=Decimal("0.02"),
        pnl_r=Decimal("1"),
        gross_pnl_fraction=Decimal("0.02"),
        gross_pnl_r=Decimal("1"),
    )
    res = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=(tr, tr),
        fills=(fe, fx),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
        cost_model_version="v1",
        cost_model_authoritative=True,
    )
    return build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=res,
        created_at=now,
        cost_model_version="v1",
    )


def test_risk_constraints_true_can_promote() -> None:
    """risk_constraints_unchanged=True + all gates PASS → can PROMOTE."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.PROMOTABLE_DECISION
    assert dec.promotion_decision is not None
    assert dec.promotion_decision.decision.value == "PROMOTE"
    assert dec.risk_constraints_unchanged is True


def test_risk_constraints_false_cannot_promote() -> None:
    """False risk evidence is rejected before the frozen decision boundary."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=False,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.REJECTED_BEFORE_DECISION
    assert dec.promotion_decision is None
    assert dec.risk_constraints_unchanged is False
    assert "RISK_CONSTRAINTS_CHANGED" in dec.reason_codes


def test_risk_constraints_false_decision_is_reject() -> None:
    """No frozen PromotionDecision is fabricated for false risk evidence."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=False,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.REJECTED_BEFORE_DECISION
    assert dec.promotion_decision is None


def test_enum_identity_not_string_comparison() -> None:
    """Uses ScorecardValidationStatus enum identity, not .value == 'PASS'."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    assert sc.validation_status is ScorecardValidationStatus.PASS
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.PROMOTABLE_DECISION
    assert dec.promotion_decision is not None


def test_non_pass_scorecard_cannot_promote() -> None:
    """Non-PASS scorecard cannot promote."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    result = BacktestResult(
        result_id=uuid4(),
        experiment_id=uuid4(),
        trades=(),
        fills=(),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
    )
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=result,
        created_at=now,
    )
    assert sc.validation_status is ScorecardValidationStatus.INSUFFICIENT_EVIDENCE
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.DEFERRED_BEFORE_DECISION
    assert dec.promotion_decision is None


def test_human_approval_behavior_unchanged() -> None:
    """HUMAN without approval cannot promote."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.HUMAN,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.REJECTED_BEFORE_DECISION
    assert dec.promotion_decision is None


def test_auto_a2_research_control_only() -> None:
    """AUTO_A2 promotion is research-control, not trading authority."""
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.PROMOTABLE_DECISION
    assert dec.promotion_decision is not None
    assert dec.promotion_decision.target_status == "CHAMPION"
    assert dec.promotion_decision.approval_mode == ApprovalMode.AUTO_A2
