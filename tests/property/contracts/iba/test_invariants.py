from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.types import ForecastStatus
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate, TradingCampaign
from ats.contracts.governance.types import (
    ActionKind,
    CampaignStatus,
    CandidateStatus,
    PositionThesisState,
    RiskDirection,
    StrategyExecutionMode,
)
from ats.contracts.intelligence.models import (
    EnsembleForecast,
    ExplanationEvidence,
    FormulaDefinition,
    PromotionDecision,
)
from ats.contracts.intelligence.types import (
    ExperimentStatus,
    ExperimentType,
    ExplanationAnswerability,
    ExplanationFact,
    FormulaNode,
    FormulaNodeKind,
    FormulaOperator,
    FormulaOutputKind,
    LeakageScanStatus,
    OutcomeProbability,
    PromotionOutcome,
)
from pydantic import ValidationError

from tests.unit.contracts.intelligence.fixtures import T0, make_contracts, uid


def rejected(name: str, **changes: object) -> None:
    value = make_contracts()[name]
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), **changes})


@pytest.mark.parametrize(
    "name", ["MarketContext", "RegimeEvidence", "PositionThesis", "ExplanationEvidence"]
)
def test_future_data_cutoff_rejected(name: str) -> None:
    rejected(name, data_cutoff=T0 + timedelta(seconds=1))


@pytest.mark.parametrize(
    ("name", "changes"),
    [
        ("AnalogueEvidence", {"query_window_end": T0 + timedelta(seconds=1)}),
        ("AnalogueEvidence", {"corpus_cutoff": T0 + timedelta(seconds=1)}),
        ("CalibratedOutcomeDistribution", {"calibration_window_end": T0 + timedelta(seconds=1)}),
        ("PerformanceAttribution", {"window_end": T0 + timedelta(seconds=1)}),
        ("PerformanceAttribution", {"data_cutoff": T0 + timedelta(seconds=1)}),
    ],
)
def test_leakage_ordering_rejected(name: str, changes: dict[str, object]) -> None:
    rejected(name, **changes)


def test_analogue_match_and_calibration_future_paths_rejected() -> None:
    analogue = make_contracts()["AnalogueEvidence"]
    match = analogue.matches[0].model_copy(update={"window_end": T0})  # type: ignore[attr-defined]
    rejected("AnalogueEvidence", matches=(match,))
    rejected("CalibratedOutcomeDistribution", data_cutoff=T0 + timedelta(seconds=1))


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), 1, "0.5"])
def test_regime_scores_are_strict_bounded_floats(value: object) -> None:
    rejected("RegimeEvidence", change_score=value)


def test_regime_support_and_reasons() -> None:
    rejected("RegimeEvidence", support_window_bars=0)
    rejected("RegimeEvidence", reason_codes=("same", "same"))


@pytest.mark.parametrize(
    ("changes"),
    [
        {"trades_started": 1, "trades_completed": 2},
        {"trades_started": 1, "trades_completed": 0, "open_positions": 2},
        {"capital_committed": Decimal("-1")},
        {"status": CampaignStatus.HALTED, "stop_reason_codes": ()},
    ],
)
def test_campaign_state_invariants(changes: dict[str, object]) -> None:
    rejected("CampaignState", **changes)


def test_position_thesis_expiry() -> None:
    rejected("PositionThesis", state=PositionThesisState.HEALTHY, expires_at=T0)
    rejected("PositionThesis", state=PositionThesisState.DEGRADING, expires_at=T0)


@pytest.mark.parametrize("operator", list(FormulaOperator))
def test_every_frozen_formula_operator_is_accepted(operator: FormulaOperator) -> None:
    literal = FormulaNode(
        node_kind=FormulaNodeKind.LITERAL,
        operator=None,
        arguments=(),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=1,
        literal_bool=None,
    )
    node = FormulaNode(
        node_kind=FormulaNodeKind.OPERATOR,
        operator=operator,
        arguments=(literal,),
        feature_code=None,
        lag_bars=None,
        literal_decimal=None,
        literal_float=None,
        literal_int=None,
        literal_bool=None,
    )
    assert node.operator is operator


@pytest.mark.parametrize(
    "changes",
    [
        {"node_kind": "FEATURE", "lag_bars": -1},
        {"node_kind": "FEATURE", "literal_int": 1},
        {"node_kind": "OPERATOR", "operator": FormulaOperator.ADD, "arguments": ()},
        {
            "node_kind": "OPERATOR",
            "operator": FormulaOperator.ADD,
            "feature_code": "x",
            "arguments": ({},),
        },
        {
            "node_kind": "LITERAL",
            "literal_int": 1,
            "literal_bool": True,
            "feature_code": None,
            "lag_bars": None,
        },
    ],
)
def test_formula_node_invalid_shapes(changes: dict[str, object]) -> None:
    base = make_contracts()["FormulaDefinition"].ast.model_dump()  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        FormulaNode.model_validate({**base, **changes})


def test_formula_rejects_unregistered_and_executable_fields() -> None:
    base = make_contracts()["FormulaDefinition"].ast.model_dump()  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        FormulaNode.model_validate(
            {**base, "node_kind": "OPERATOR", "operator": "PYTHON", "arguments": (base,)}
        )
    with pytest.raises(ValidationError):
        FormulaNode.model_validate({**base, "python_source": "x + 1"})


@pytest.mark.parametrize("field", ["ast_depth", "node_count", "max_lag_bars"])
def test_formula_metadata_mismatch(field: str) -> None:
    rejected("FormulaDefinition", **{field: 2})


def test_formula_features_and_output_rules() -> None:
    rejected("FormulaDefinition", required_features=("other",))
    rejected("FormulaDefinition", required_features=("close", "close"))
    value = make_contracts()["FormulaDefinition"]
    with pytest.raises(ValidationError):
        FormulaDefinition.model_validate(
            {
                **value.model_dump(),
                "purpose": "ENTRY_FILTER",
                "output_kind": FormulaOutputKind.DECIMAL,
            }
        )
    with pytest.raises(ValidationError):
        FormulaDefinition.model_validate(
            {
                **value.model_dump(),
                "purpose": "EXIT_FILTER",
                "output_kind": FormulaOutputKind.FINITE_FLOAT,
            }
        )
    with pytest.raises(ValidationError):
        FormulaDefinition.model_validate(
            {
                **value.model_dump(),
                "purpose": "PRICE_LEVEL",
                "output_kind": FormulaOutputKind.BOOLEAN,
            }
        )


def test_campaign_scope_sets_dates_and_activation() -> None:
    rejected("TradingCampaign", scope="A3")
    for field in ("instrument_universe", "allowed_strategies", "allowed_timeframes"):
        rejected("TradingCampaign", **{field: ()})
    rejected("TradingCampaign", max_trades=0)
    rejected("TradingCampaign", expires_at=T0)
    rejected("TradingCampaign", status=CampaignStatus.ACTIVE, activated_at=None)
    rejected("TradingCampaign", status=CampaignStatus.DRAFT, activated_at=T0)
    rejected("TradingCampaign", status=CampaignStatus.REJECTED, activated_at=T0)
    rejected("TradingCampaign", instrument_universe=("ABC", "ABC"))
    rejected("TradingCampaign", allowed_timeframes=("5m", "5m"))
    assert "required_trades" not in TradingCampaign.model_fields
    assert StrategyExecutionMode.ISOLATED_CHALLENGER_PAPER.value == "ISOLATED_CHALLENGER_PAPER"


@pytest.mark.parametrize(
    ("status", "missing"),
    [
        (CandidateStatus.RISK_EVALUATED, "risk_decision_id"),
        (CandidateStatus.ADVISED, "advisory_id"),
        (CandidateStatus.AUTHORIZED, "autonomy_token_id"),
        (CandidateStatus.CONSUMED, "autonomy_token_id"),
    ],
)
def test_candidate_authority_reference_matrix(status: CandidateStatus, missing: str) -> None:
    base = make_contracts()["OpportunityCandidate"].model_dump()  # type: ignore[attr-defined]
    base.update(
        status=status, risk_decision_id=uid(70), advisory_id=uid(71), autonomy_token_id=uid(72)
    )
    base[missing] = None
    with pytest.raises(ValidationError):
        OpportunityCandidate.model_validate(base)


def test_candidate_pre_authority_and_terminated_lineage_states() -> None:
    value = make_contracts()["OpportunityCandidate"]
    raw = value.model_dump()  # type: ignore[attr-defined]
    for status in (CandidateStatus.CREATED, CandidateStatus.ELIGIBLE):
        assert OpportunityCandidate.model_validate({**raw, "status": status})
    for status in (CandidateStatus.REJECTED, CandidateStatus.EXPIRED):
        assert OpportunityCandidate.model_validate(
            {**raw, "status": status, "risk_decision_id": uid(70), "advisory_id": uid(71)}
        )


@pytest.mark.parametrize(
    ("kind", "direction"),
    [
        (ActionKind.OPEN_POSITION, RiskDirection.REDUCE),
        (ActionKind.INCREASE_POSITION, RiskDirection.NEUTRAL),
        (ActionKind.REDUCE_POSITION, RiskDirection.INCREASE),
        (ActionKind.CLOSE_POSITION, RiskDirection.NEUTRAL),
        (ActionKind.EMERGENCY_FLATTEN, RiskDirection.INCREASE),
    ],
)
def test_governance_fixed_risk_direction(kind: ActionKind, direction: RiskDirection) -> None:
    rejected("GovernanceContext", action_kind=kind, risk_direction=direction)


def test_governance_reference_pairs_and_provenance() -> None:
    rejected("GovernanceContext", candidate_version=None)
    rejected("GovernanceContext", campaign_state_version=None)
    rejected("GovernanceContext", constraint_provenance=())
    rejected("GovernanceContext", source_refs=())
    constraints = make_contracts()["GovernanceContext"].resolved_constraints  # type: ignore[attr-defined]
    assert len(type(constraints).model_fields) == 15


def test_governance_semantically_deferred_directions_and_required_refs() -> None:
    value = make_contracts()["GovernanceContext"]
    raw = value.model_dump()  # type: ignore[attr-defined]
    position = {"position_thesis_id": uid(24), "position_thesis_version": 1}
    for direction in (RiskDirection.INCREASE, RiskDirection.REDUCE):
        assert GovernanceContext.model_validate(
            {
                **raw,
                **position,
                "action_kind": ActionKind.MODIFY_PROTECTIVE_EXIT,
                "risk_direction": direction,
            }
        )
    for direction in RiskDirection:
        assert GovernanceContext.model_validate(
            {**raw, "action_kind": ActionKind.CANCEL_ORDER, "risk_direction": direction}
        )
    rejected(
        "GovernanceContext",
        action_kind=ActionKind.OPEN_POSITION,
        risk_direction=RiskDirection.INCREASE,
        candidate_id=None,
        candidate_version=None,
    )
    rejected(
        "GovernanceContext",
        action_kind=ActionKind.REDUCE_POSITION,
        risk_direction=RiskDirection.REDUCE,
        position_thesis_id=None,
        position_thesis_version=None,
    )


def test_ensemble_sum_and_duplicates() -> None:
    value = make_contracts()["EnsembleForecast"]
    raw = value.model_dump()  # type: ignore[attr-defined]
    raw.update(
        status=ForecastStatus.READY,
        raw_outcomes=(OutcomeProbability(outcome_code="UP", probability=Decimal("1")),),
    )
    assert EnsembleForecast.model_validate(raw)
    bad = {
        **raw,
        "raw_outcomes": (OutcomeProbability(outcome_code="UP", probability=Decimal("0.9")),),
    }
    with pytest.raises(ValidationError):
        EnsembleForecast.model_validate(bad)
    with pytest.raises(ValidationError):
        EnsembleForecast.model_validate({**raw, "effective_member_count": 0})
    member = raw["members"][0]
    with pytest.raises(ValidationError):
        EnsembleForecast.model_validate(
            {**raw, "members": (member, member), "effective_member_count": 2}
        )
    outcome = raw["raw_outcomes"][0]
    with pytest.raises(ValidationError):
        EnsembleForecast.model_validate({**raw, "raw_outcomes": (outcome, outcome)})


def test_calibration_regime_and_probability_rules() -> None:
    rejected("CalibratedOutcomeDistribution", regime_conditioned=True, regime_evidence_id=None)
    rejected("CalibratedOutcomeDistribution", regime_conditioned=False, regime_evidence_id=uid(5))
    value = make_contracts()["CalibratedOutcomeDistribution"]
    outcome = value.outcomes[0]  # type: ignore[attr-defined]
    rejected("CalibratedOutcomeDistribution", outcomes=(outcome, outcome))
    bad = outcome.model_copy(update={"probability": Decimal("0.8")})
    rejected("CalibratedOutcomeDistribution", outcomes=(bad,))


@pytest.mark.parametrize(
    ("answerability", "facts", "missing"),
    [
        (ExplanationAnswerability.FULL, (), ()),
        (ExplanationAnswerability.FULL, (1,), ("x",)),
        (ExplanationAnswerability.PARTIAL, (), ("x",)),
        (ExplanationAnswerability.PARTIAL, (1,), ()),
        (ExplanationAnswerability.INSUFFICIENT, (), ()),
    ],
)
def test_explanation_answerability_matrix(
    answerability: ExplanationAnswerability, facts: tuple[object, ...], missing: tuple[str, ...]
) -> None:
    value = make_contracts()["ExplanationEvidence"]
    actual_facts = value.facts if facts else ()  # type: ignore[attr-defined]
    rejected(
        "ExplanationEvidence",
        answerability=answerability,
        facts=actual_facts,
        missing_information=missing,
    )


def test_explanation_question_only_and_no_authority_fields() -> None:
    rejected("ExplanationEvidence", intent="COMMAND")
    assert not ({"command", "action", "order"} & set(ExplanationEvidence.model_fields))
    with pytest.raises(ValidationError):
        ExplanationFact(fact_code="x", fact_value=1, evidence_refs=())


def test_promotion_safety_matrix() -> None:
    value = make_contracts()["PromotionDecision"]
    base = value.model_dump()  # type: ignore[attr-defined]
    promote = {
        **base,
        "decision": PromotionOutcome.PROMOTE,
        "required_gates_passed": True,
        "minimum_evidence_met": True,
        "effective_from": T0,
    }
    assert PromotionDecision.model_validate(promote)
    for changes in (
        {"required_gates_passed": False},
        {"minimum_evidence_met": False},
        {"effective_from": None},
    ):
        with pytest.raises(ValidationError):
            PromotionDecision.model_validate({**promote, **changes})
    rejected("PromotionDecision", decision=PromotionOutcome.REJECT, effective_from=T0)
    rejected("PromotionDecision", decision=PromotionOutcome.DEFER, effective_from=T0)
    rejected("PromotionDecision", risk_constraints_unchanged=False)
    with pytest.raises(ValidationError):
        PromotionDecision.model_validate(
            {**promote, "approval_mode": "HUMAN", "approved_by": None, "approved_at": None}
        )


def test_experiment_time_and_status_matrix() -> None:
    rejected("StrategyExperiment", train_start=T0 - timedelta(days=2), train_end=None)
    rejected("StrategyExperiment", train_start=T0, train_end=T0 + timedelta(days=1))
    rejected("StrategyExperiment", test_end=T0 + timedelta(days=1))
    rejected(
        "StrategyExperiment", experiment_type=ExperimentType.SHADOW_PAPER, shadow_campaign_id=None
    )
    rejected(
        "StrategyExperiment", experiment_type=ExperimentType.BACKTEST, shadow_campaign_id=uid(20)
    )
    rejected(
        "StrategyExperiment",
        status=ExperimentStatus.COMPLETED,
        started_at=T0,
        completed_at=T0,
        test_end=T0,
        scorecard_id=uid(44),
        leakage_scan_status=LeakageScanStatus.FAIL,
    )


def test_scorecard_undefined_metrics_and_finite_numeric_rules() -> None:
    rejected("StrategyScorecard", experiment_ids=())
    rejected("StrategyScorecard", experiment_ids=(uid(42), uid(42)))
    rejected("StrategyScorecard", evaluation_end=T0 - timedelta(days=2))
    rejected("StrategyScorecard", profit_factor=float("inf"))
    rejected("StrategyScorecard", expectancy_r=float("nan"))
    rejected("StrategyScorecard", trade_count=0, win_rate=Decimal("0.5"))


def test_performance_attribution_has_no_fake_additive_rule() -> None:
    value = make_contracts()["PerformanceAttribution"]
    assert (
        value.observed_pnl != value.components[0].contribution_money + value.unattributed_residual
    )  # type: ignore[attr-defined]


def test_financial_decimal_rejects_float_and_probability_bounds() -> None:
    rejected("InstrumentSpec", tick_size=0.05)
    rejected("OpportunityCandidate", calibrated_probability=Decimal("1.1"))
