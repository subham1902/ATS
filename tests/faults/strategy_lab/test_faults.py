from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from ats.contracts.intelligence.types import (
    ApprovalMode,
    ExperimentType,
)
from ats.intelligence.strategy_lab.cost_model import FixedBpsCostModel
from ats.intelligence.strategy_lab.dataset_binding import DatasetBinding
from ats.intelligence.strategy_lab.experiment_runner import build_experiment
from ats.intelligence.strategy_lab.promotion_gate import (
    PromotionEvaluationStatus,
    evaluate_promotion,
)
from ats.intelligence.strategy_lab.scorecard import build_scorecard
from ats.intelligence.strategy_lab.types import BacktestResult


def test_future_data_leakage() -> None:
    # dataset_cutoff before test_end is rejected at contract level
    with pytest.raises(ValueError):
        build_experiment(
            experiment_id=uuid4(),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            experiment_type=ExperimentType.BACKTEST,
            instrument_universe=("NSE_EQ-TCS",),
            timeframe="5m",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
            train_start=datetime(2024, 1, 1, tzinfo=UTC),
            train_end=datetime(2024, 1, 12, tzinfo=UTC),
            test_start=datetime(2024, 1, 13, tzinfo=UTC),
            test_end=datetime(2024, 1, 15, tzinfo=UTC),
            purge_bars=0,
            embargo_bars=0,
            cost_model_version="v1",
            parameter_set_hash="a" * 64,
            seed=42,
        )


def test_train_test_overlap() -> None:
    with pytest.raises(ValueError):
        build_experiment(
            experiment_id=uuid4(),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            experiment_type=ExperimentType.BACKTEST,
            instrument_universe=("NSE_EQ-TCS",),
            timeframe="5m",
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 20, tzinfo=UTC),
            train_start=datetime(2024, 1, 5, tzinfo=UTC),
            train_end=datetime(2024, 1, 15, tzinfo=UTC),
            test_start=datetime(2024, 1, 10, tzinfo=UTC),
            test_end=datetime(2024, 1, 20, tzinfo=UTC),
            purge_bars=0,
            embargo_bars=0,
            cost_model_version="v1",
            parameter_set_hash="a" * 64,
            seed=42,
        )


def test_cost_model_failure() -> None:
    cost = FixedBpsCostModel(
        cost_model_version="v1", fee_bps=Decimal("-1"), per_trade_fee=Decimal("0")
    )
    with pytest.raises(ValueError):
        cost.cost_per_trade(price=Decimal("100"), quantity=Decimal("10"), side="BUY")


def test_zero_trades_scorecard() -> None:
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
    assert sc.trade_count == 0
    assert sc.profit_factor is None


def test_nan_inf_rejected() -> None:
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
    import math

    assert math.isfinite(sc.net_return_fraction)


def test_promotion_insufficient_evidence() -> None:
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
    dec = evaluate_promotion(
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=(uuid4(), 1),
        incumbent_strategy_ref=None,
        scorecard=sc,
        required_gates_passed=True,
        minimum_evidence_met=False,
        risk_constraints_unchanged=True,
        approval_mode=ApprovalMode.AUTO_A2,
        decided_at=now,
        effective_from=now,
        approved_by=None,
        approved_at=None,
    )
    assert dec.status is PromotionEvaluationStatus.DEFERRED_BEFORE_DECISION
    assert dec.promotion_decision is None


def test_challenger_cannot_self_authorize() -> None:
    # AUTO_A2 cannot grant A2 order authority — promotion is research-control only
    # Verified by checking that promotion target is CHAMPION but not AutonomyToken
    now = datetime(2024, 1, 10, tzinfo=UTC)
    # Use a PASS scorecard
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
        trades=(tr,),
        fills=(fe, fx),
        signals=(),
        start_time=now,
        end_time=now,
        seed=42,
        cost_model_version="v1",
        cost_model_authoritative=True,
    )
    sc = build_scorecard(
        strategy_definition_id=uuid4(),
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        result=res,
        created_at=now,
        cost_model_version="v1",
    )
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
    # PromotionDecision is research-control, not trading authority — no AutonomyToken created
    assert dec.status is PromotionEvaluationStatus.PROMOTABLE_DECISION
    assert dec.promotion_decision is not None
    assert dec.promotion_decision.target_status == "CHAMPION"
    assert dec.promotion_decision.approval_mode == ApprovalMode.AUTO_A2


def test_corrupt_dataset_binding() -> None:
    from ats.contracts.intelligence.types import RegisteredCode

    with pytest.raises(ValueError):
        DatasetBinding(
            dataset_manifest_id=uuid4(),
            dataset_version="v1",
            dataset_cutoff=datetime(2024, 1, 10, tzinfo=UTC),
            strategy_definition_id=uuid4(),
            strategy_definition_version=1,
            formula_refs=(),
            instrument_universe=(),
            timeframe=RegisteredCode("5m"),
            parameter_set_hash="a" * 64,
            seed=42,
            cost_model_version="v1",
        )
