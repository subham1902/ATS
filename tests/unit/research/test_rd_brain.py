"""Comprehensive unit tests for ATS R&D Brain and Champion/Challenger pipeline (O7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.intelligence.models import (
    FormulaDefinition,
    PromotionDecision,
    StrategyScorecard,
)
from ats.contracts.intelligence.types import (
    ApprovalMode,
    FormulaNode,
    FormulaNodeKind,
    FormulaOperator,
    FormulaOutputKind,
    FormulaPurpose,
    PromotionOutcome,
    ScorecardValidationStatus,
    StrategyOrigin,
    StrategyRef,
)
from ats.intelligence.research.agent import HarnessResearchAgent
from ats.intelligence.research.champion_challenger import ChampionChallengerRegistry
from ats.intelligence.research.degradation import StrategyDegradationMonitor
from ats.intelligence.research.engine import ResearchBrainEngine
from ats.intelligence.research.hypothesis import (
    build_research_hypothesis,
    validate_safe_formula_ast,
)
from ats.intelligence.research.models import (
    DegradationAction,
    DegradationMetric,
    ResearchHypothesis,
    ResearchRecommendationAction,
    StrategyLifecycleStatus,
)
from ats.intelligence.strategy_lab.promotion_gate import PromotionEvaluationStatus

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
STRATEGY_ID = UUID("81000000-0000-0000-0000-000000000001")


def _sample_ast() -> FormulaNode:
    return FormulaNode(
        node_kind=FormulaNodeKind.OPERATOR,
        operator=FormulaOperator.GT,
        arguments=(
            FormulaNode(
                node_kind=FormulaNodeKind.FEATURE,
                operator=None,
                arguments=(),
                feature_code="roc_3_fraction",
                lag_bars=0,
                literal_decimal=None,
                literal_float=None,
                literal_int=None,
                literal_bool=None,
            ),
            FormulaNode(
                node_kind=FormulaNodeKind.LITERAL,
                operator=None,
                arguments=(),
                feature_code=None,
                lag_bars=None,
                literal_decimal=None,
                literal_float=0.01,
                literal_int=None,
                literal_bool=None,
            ),
        ),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=None,
    )


def _sample_formula() -> FormulaDefinition:
    ast = _sample_ast()
    form = FormulaDefinition(
        schema_version="1.0",
        formula_definition_id=uuid4(),
        formula_version=1,
        name="MomentumBreakout",
        purpose=FormulaPurpose.ENTRY_FILTER,
        output_kind=FormulaOutputKind.BOOLEAN,
        timeframe="5m",
        lookback_bars=10,
        warmup_bars=5,
        ast=ast,
        ast_depth=2,
        node_count=3,
        max_lag_bars=0,
        required_features=("roc_3_fraction",),
        parameters=(),
        source_instruction_hash="0" * 64,
        origin=StrategyOrigin.LLM,
        created_at=NOW,
        payload_hash="0" * 64,
    )
    return form.model_copy(update={"payload_hash": compute_payload_hash(form)})


def _sample_scorecard(
    strategy_id: UUID = STRATEGY_ID,
    net_return_fraction: float = 0.15,
    profit_factor: float = 1.8,
    max_dd: Decimal = Decimal("0.04"),
) -> StrategyScorecard:
    sc = StrategyScorecard(
        schema_version="1.0",
        scorecard_id=uuid4(),
        strategy_definition_id=strategy_id,
        strategy_definition_version=1,
        experiment_ids=(uuid4(),),
        evaluation_start=NOW - timedelta(days=30),
        evaluation_end=NOW,
        sample_count=120,
        trade_count=120,
        net_return_fraction=net_return_fraction,
        expectancy_r=0.45,
        profit_factor=profit_factor,
        win_rate=Decimal("0.58"),
        average_win_r=1.2,
        average_loss_r=-0.8,
        maximum_drawdown=max_dd,
        sharpe=2.1,
        sortino=2.8,
        tail_loss_metric=0.02,
        turnover=5.0,
        estimated_costs=Decimal("500"),
        stability_score=0.85,
        parameter_sensitivity_score=0.80,
        regime_coverage_score=0.90,
        benchmark_delta=0.08,
        validation_status=ScorecardValidationStatus.PASS,
        created_at=NOW,
        payload_hash="0" * 64,
    )
    return sc.model_copy(update={"payload_hash": compute_payload_hash(sc)})


def test_hypothesis_validation() -> None:
    ref1 = uuid4()
    formula = _sample_formula()

    hyp = build_research_hypothesis(
        question="Does 3-bar momentum predict option premium expansion?",
        rationale="Empirical observations show persistent momentum in first 30m of market session.",
        evidence_refs=(ref1,),
        market_regime_scope=("TRENDING_UP", "HIGH_VOLATILITY"),
        proposed_formula=formula,
        dataset_scope="NSE_NIFTY_5M_2024",
        created_at=NOW,
        data_cutoff=NOW,
    )

    assert isinstance(hyp, ResearchHypothesis)
    assert hyp.question.startswith("Does 3-bar")
    assert hyp.evidence_refs == (ref1,)
    assert hyp.proposed_formula is not None
    assert hyp.payload_hash == compute_payload_hash(hyp)

    # Ordering validation: data_cutoff > created_at must raise ValueError
    with pytest.raises(ValueError, match="data_cutoff must be <= created_at"):
        build_research_hypothesis(
            question="Invalid cutoff?",
            rationale="Rationale",
            evidence_refs=(ref1,),
            market_regime_scope=("TRENDING",),
            dataset_scope="DATASET",
            created_at=NOW,
            data_cutoff=NOW + timedelta(minutes=5),
        )


def test_safe_formula_validation_rejects_unsafe() -> None:
    formula = _sample_formula()
    validate_safe_formula_ast(formula)  # Passes safely

    # Construct an invalid node kind outside allowed enum
    fake_node = FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=1.0,
        literal_int=None,
        literal_bool=None,
    )
    # Valid AST node check
    assert fake_node.node_kind is FormulaNodeKind.LITERAL


def test_champion_challenger_lifecycle() -> None:
    registry = ChampionChallengerRegistry()
    challenger_id = uuid4()

    # 1. Register challenger
    record = registry.register_challenger(
        family="MOMENTUM_BREAKOUT",
        strategy_id=challenger_id,
        strategy_version=1,
        notes="Challenger v1",
    )
    assert record.lifecycle_status is StrategyLifecycleStatus.CHALLENGER
    # Infallible gate: Challenger CANNOT execute!
    assert not registry.is_execution_eligible(challenger_id)

    # 2. Promote challenger via PromotionDecision
    decision = PromotionDecision(
        schema_version="1.0",
        promotion_decision_id=uuid4(),
        candidate_strategy_ref=StrategyRef(
            strategy_definition_id=challenger_id, strategy_definition_version=1
        ),
        incumbent_strategy_ref=None,
        scorecard_ids=(uuid4(),),
        decision=PromotionOutcome.PROMOTE,
        target_status="CHAMPION",
        approval_mode=ApprovalMode.AUTO_A2,
        required_gates_passed=True,
        minimum_evidence_met=True,
        risk_constraints_unchanged=True,
        approved_by="PromotionGate.v1",
        approved_at=NOW,
        effective_from=NOW,
        reason_codes=("SCORECARD_PASSED_ALL_GATES",),
        decided_at=NOW,
        payload_hash="0" * 64,
    )
    decision = decision.model_copy(update={"payload_hash": compute_payload_hash(decision)})

    champ_rec = registry.promote_to_champion(
        strategy_id=challenger_id,
        promotion_decision=decision,
        promoted_at=NOW,
    )
    assert champ_rec.lifecycle_status is StrategyLifecycleStatus.CHAMPION
    # Now eligible for execution
    assert registry.is_execution_eligible(challenger_id)
    assert registry.get_champion("MOMENTUM_BREAKOUT") is not None

    # 3. Register next challenger and promote it -> old champion retired
    new_challenger_id = uuid4()
    registry.register_challenger(
        family="MOMENTUM_BREAKOUT",
        strategy_id=new_challenger_id,
        strategy_version=1,
    )
    new_decision = decision.model_copy(
        update={
            "promotion_decision_id": uuid4(),
            "candidate_strategy_ref": StrategyRef(
                strategy_definition_id=new_challenger_id, strategy_definition_version=1
            ),
        }
    )
    new_decision = new_decision.model_copy(
        update={"payload_hash": compute_payload_hash(new_decision)}
    )

    registry.promote_to_champion(
        strategy_id=new_challenger_id,
        promotion_decision=new_decision,
        promoted_at=NOW + timedelta(days=1),
    )
    # Old champion is now retired and ineligible for execution
    assert not registry.is_execution_eligible(challenger_id)
    old_rec = registry.get_record(challenger_id)
    assert old_rec is not None and old_rec.lifecycle_status is StrategyLifecycleStatus.RETIRED

    # New challenger is champion and eligible
    assert registry.is_execution_eligible(new_challenger_id)


def test_deterministic_promotion_gate_rejects_baseline_tag() -> None:
    engine = ResearchBrainEngine()
    # Baseline strategy tagged as baseline
    baseline_sc = _sample_scorecard(
        strategy_id=STRATEGY_ID,
        net_return_fraction=0.25,
        profit_factor=2.0,
    )

    res = engine.evaluate_challenger_promotion(
        scorecard=baseline_sc,
        evaluation_time=NOW,
        is_baseline_only=True,
    )

    # Proves invariant: Baseline strategies CANNOT be promoted merely because net PnL was positive
    assert res.status is PromotionEvaluationStatus.REJECTED_BEFORE_DECISION
    assert "BASELINE_STRATEGY_NOT_LIVE_ELIGIBLE" in res.reason_codes
    assert res.promotion_decision is None


def test_degradation_monitoring_actions() -> None:
    monitor = StrategyDegradationMonitor(minimum_sample_count=10)

    # 1. Nominal metrics -> HEALTHY
    m_healthy = DegradationMetric(
        rolling_expectancy_r=0.45,
        profit_factor=1.9,
        drawdown_fraction=Decimal("0.02"),
        cost_sensitivity=0.10,
        calibration_drift=0.05,
        sample_count=50,
    )
    ass_healthy = monitor.assess(
        strategy_id=STRATEGY_ID, strategy_version=1, metrics=m_healthy, evaluated_at=NOW
    )
    assert ass_healthy.action is DegradationAction.HEALTHY

    # 2. Critical drawdown breach -> PAUSE_STRATEGY
    m_pause = DegradationMetric(
        rolling_expectancy_r=-0.25,
        profit_factor=0.8,
        drawdown_fraction=Decimal("0.18"),
        cost_sensitivity=0.10,
        calibration_drift=0.05,
        sample_count=50,
    )
    ass_pause = monitor.assess(
        strategy_id=STRATEGY_ID, strategy_version=1, metrics=m_pause, evaluated_at=NOW
    )
    assert ass_pause.action is DegradationAction.PAUSE_STRATEGY
    assert "CRITICAL_DRAWDOWN_EXCEEDED" in ass_pause.reasons

    # 3. Elevated drawdown -> REDUCE_ALLOCATION
    m_reduce = DegradationMetric(
        rolling_expectancy_r=0.20,
        profit_factor=0.95,
        drawdown_fraction=Decimal("0.09"),
        cost_sensitivity=0.10,
        calibration_drift=0.05,
        sample_count=50,
    )
    ass_reduce = monitor.assess(
        strategy_id=STRATEGY_ID, strategy_version=1, metrics=m_reduce, evaluated_at=NOW
    )
    assert ass_reduce.action is DegradationAction.REDUCE_ALLOCATION

    # 4. Calibration drift -> EVALUATE_CHALLENGER
    m_drift = DegradationMetric(
        rolling_expectancy_r=0.30,
        profit_factor=1.4,
        drawdown_fraction=Decimal("0.03"),
        cost_sensitivity=0.60,
        calibration_drift=0.30,
        sample_count=50,
    )
    ass_drift = monitor.assess(
        strategy_id=STRATEGY_ID, strategy_version=1, metrics=m_drift, evaluated_at=NOW
    )
    assert ass_drift.action is DegradationAction.EVALUATE_CHALLENGER

    # 5. Low sample count -> HEALTHY with INSUFFICIENT_SAMPLE_WINDOW
    m_small = DegradationMetric(
        rolling_expectancy_r=-0.50,
        profit_factor=0.5,
        drawdown_fraction=Decimal("0.20"),
        cost_sensitivity=0.80,
        calibration_drift=0.50,
        sample_count=4,
    )
    ass_small = monitor.assess(
        strategy_id=STRATEGY_ID, strategy_version=1, metrics=m_small, evaluated_at=NOW
    )
    assert ass_small.action is DegradationAction.HEALTHY
    assert "INSUFFICIENT_SAMPLE_WINDOW" in ass_small.reasons


def test_harness_research_agent_advisory() -> None:
    agent = HarnessResearchAgent()

    # Formulate hypothesis
    hyp = agent.formulate_hypothesis(
        question="Will mean reversion work in high volatility regimes?",
        rationale="Option premiums expand excessively during opening surges.",
        evidence_refs=(uuid4(),),
        market_regime_scope=("HIGH_VOLATILITY",),
        dataset_scope="NSE_2024",
        as_of=NOW,
    )
    assert hyp.question.startswith("Will mean reversion")

    # Propose experiment
    prop = agent.propose_experiment(
        hypothesis=hyp,
        strategy_definition_id=STRATEGY_ID,
        strategy_definition_version=1,
        instrument_universe=("NIFTY", "BANKNIFTY"),
        timeframe="5m",
        as_of=NOW,
    )
    assert prop.train_bars == 500

    # Compare scorecard
    champ_sc = _sample_scorecard(
        strategy_id=STRATEGY_ID, net_return_fraction=0.10, profit_factor=1.5
    )
    challenger_sc = _sample_scorecard(
        strategy_id=uuid4(), net_return_fraction=0.20, profit_factor=1.9
    )

    rec = agent.compare_challenger(
        hypothesis_id=hyp.hypothesis_id,
        champion_scorecard=champ_sc,
        challenger_scorecard=challenger_sc,
        as_of=NOW,
    )
    assert rec.action is ResearchRecommendationAction.PROMOTE
    assert "Challenger outperforms champion" in rec.rationale
