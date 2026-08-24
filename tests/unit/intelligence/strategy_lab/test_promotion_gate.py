from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ats.contracts.intelligence.types import ApprovalMode
from ats.intelligence.strategy_lab.promotion_gate import evaluate_promotion
from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.intelligence.strategy_lab.types import BacktestResult


def _pass_scorecard():
    now = datetime(2024, 1, 10, tzinfo=UTC)
    # Need a PASS scorecard with trades
    from decimal import Decimal

    from ats.intelligence.strategy_lab.types import ResearchFill, ResearchTrade

    fe = ResearchFill(
        fill_id=uuid4(),
        signal_id=uuid4(),
        instrument_id="NSE_EQ-TCS",
        side="BUY",
        price=Decimal("100"),
        quantity=Decimal("10"),
        bar_timestamp=now,
        bar_sequence=1,
        cost=Decimal("0"),
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
        cost=Decimal("0"),
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
    )
    return build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=res,
        created_at=now,
    )


def test_promote_requires_gates() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    # Fail gates
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=False,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.decision.value != "PROMOTE"


def test_human_requires_approval() -> None:
    now = datetime(2024, 1, 10, tzinfo=UTC)
    sc = _pass_scorecard()
    # HUMAN without approval should not PROMOTE
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
    assert dec.decision.value != "PROMOTE"


def test_auto_a2_promote() -> None:
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
    assert dec.decision.value == "PROMOTE"
    assert dec.risk_constraints_unchanged is True
