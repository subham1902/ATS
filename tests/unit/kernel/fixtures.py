"""Deterministic, fully bound A04 authority-path fixture."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import (
    DecisionPacket,
    OrderIntent,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    AutonomyLevel,
    DataQualityState,
    LossState,
    PaperOrderType,
    PolicyStatus,
    RiskOutcome,
)
from ats.contracts.governance.types import CampaignStatus, CandidateStatus
from ats.contracts.intelligence.types import StrategyRef, StrategyStatus
from ats.kernel.autonomy import binding_to_bounded_json, build_decision_binding
from ats.kernel.constraints import compose_constraints
from ats.kernel.risk import produce_risk_decision
from ats.kernel.types import (
    CampaignEvaluationFacts,
    ExecutionSafetyFacts,
    OrderEvaluationFacts,
    OrderGuardPolicy,
    RiskCapitalBasis,
    SystemConstraintSet,
)

from tests.unit.contracts.domain.fixtures import make_contracts as make_a02
from tests.unit.contracts.intelligence.fixtures import T0, uid
from tests.unit.contracts.intelligence.fixtures import make_contracts as make_iba


def _validated(value: object, **changes: object):  # type: ignore[no-untyped-def]
    cls = type(value)
    raw = {**value.model_dump(), **changes}  # type: ignore[attr-defined]
    if "payload_hash" in cls.model_fields:
        raw["payload_hash"] = "0" * 64
    result = cls.model_validate(raw)
    if "payload_hash" in cls.model_fields:
        result = result.model_copy(update={"payload_hash": compute_payload_hash(result)})
    return result


def make_kernel_fixture() -> dict[str, object]:
    iba = make_iba()
    a02 = make_a02()
    strategy = _validated(iba["StrategyDefinition"], status=StrategyStatus.CHAMPION)
    campaign = _validated(
        iba["TradingCampaign"],
        status=CampaignStatus.ACTIVE,
        activated_at=T0,
    )
    campaign_state = _validated(
        iba["CampaignState"],
        status=CampaignStatus.ACTIVE,
    )
    policy = _validated(
        a02["StrategyPolicy"],
        policy_id=campaign.policy_id,
        lifecycle_status=PolicyStatus.ACTIVE,
        autonomy_level=AutonomyLevel.A2,
        universe=("ABC",),
        event_definition_id=str(iba["OpportunityCandidate"].event_definition_id),
        forecast_horizon_bars=3,
        confidence_threshold=Decimal("0.6"),
        valid_from=T0 - timedelta(hours=1),
        valid_until=T0 + timedelta(days=1),
        activated_at=T0,
    )
    market = _validated(iba["MarketContext"])
    thesis = _validated(iba["MarketThesis"])
    distribution = _validated(iba["CalibratedOutcomeDistribution"])
    risk_facts = _validated(
        a02["RiskFacts"],
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        data_quality_state=DataQualityState.GOOD,
        loss_state=LossState.NORMAL,
        proposed_maximum_loss=Decimal("100"),
        expected_reward=Decimal("200"),
        available_cash=Decimal("10000"),
        measured_at=T0,
    )
    basis = RiskCapitalBasis(
        portfolio_equity=Decimal("10000"), campaign_equity_basis=Decimal("10000")
    )
    system = SystemConstraintSet(
        constraint_set_id=uid(80),
        constraint_set_version=1,
        maximum_loss_per_trade=campaign.maximum_loss_per_trade,
        maximum_campaign_loss=campaign.maximum_campaign_loss,
        drawdown_limit=Decimal("0.2"),
        max_trades=20,
        max_concurrent_positions=5,
        capital_budget=Decimal("20000"),
        maximum_budget_per_trade=campaign.maximum_budget_per_trade,
        minimum_calibrated_probability=Decimal("0.5"),
        minimum_calibration_support=10,
        minimum_expected_edge_r=0.1,
        minimum_reward_risk=Decimal("1.5"),
        allowed_instruments=("ABC", "XYZ"),
        allowed_timeframes=("5m", "15m"),
        allowed_strategies=(
            StrategyRef(
                strategy_definition_id=strategy.strategy_definition_id,
                strategy_definition_version=strategy.strategy_definition_version,
            ),
        ),
        strategy_execution_mode=campaign.strategy_execution_mode,
    )
    composition = compose_constraints(system, policy, campaign, capital_basis=basis)
    risk_decision = produce_risk_decision(
        risk_facts,
        policy,
        composition.effective,
        risk_decision_id=uid(85),
        risk_direction=iba["GovernanceContext"].risk_direction,
        capital_basis=basis,
        decided_at=T0,
    )
    assert risk_decision.decision is RiskOutcome.ALLOW
    advisory_id = uid(82)
    candidate = _validated(
        iba["OpportunityCandidate"],
        status=CandidateStatus.ADVISED,
        risk_decision_id=risk_decision.risk_decision_id,
        advisory_id=advisory_id,
        autonomy_token_id=None,
    )
    context = _validated(
        iba["GovernanceContext"],
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.candidate_version,
        strategy_definition_id=strategy.strategy_definition_id,
        strategy_definition_version=strategy.strategy_definition_version,
        resolved_constraints=composition.effective,
        constraint_provenance=composition.provenance,
    )
    binding = build_decision_binding(candidate, context, campaign, thesis, distribution, strategy)
    packet = DecisionPacket(
        schema_version="1.0",
        packet_id=uid(81),
        candidate_id=candidate.candidate_id,
        snapshot_id=market.snapshot_id,
        forecast_id=distribution.ensemble_forecast_id,
        confidence_id=distribution.distribution_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        risk_decision_id=risk_decision.risk_decision_id,
        bounded_evidence=binding_to_bounded_json(binding),
        created_at=T0,
        payload_hash="0" * 64,
    )
    packet = packet.model_copy(update={"payload_hash": compute_payload_hash(packet)})
    advisory = SupervisorAdvisory(
        schema_version="1.0",
        advisory_id=advisory_id,
        packet_id=packet.packet_id,
        recommendation=AdvisoryOutcome.APPROVE,
        evidence_refs=(packet.packet_id,),
        reason_codes=("SUPPORTED",),
        uncertainty_flags=(),
        model_id="supervisor",
        model_version="1",
        latency_ms=1,
        created_at=T0,
        payload_hash="0" * 64,
    )
    advisory = advisory.model_copy(update={"payload_hash": compute_payload_hash(advisory)})
    safety = ExecutionSafetyFacts(
        position_state_known=True,
        execution_state_known=True,
        position_ownership_known=True,
        ambiguous_exit_pending=False,
        reconciliation_mismatch=False,
    )
    campaign_facts = CampaignEvaluationFacts(
        stop_condition_triggered=False,
        campaign_loss_limit_reached=False,
        capital_limit_reached=False,
    )
    order = OrderIntent(
        schema_version="1.0",
        intent_id=uid(83),
        instrument_id=candidate.instrument_id,
        side=candidate.side,
        quantity=Decimal("1"),
        order_type=PaperOrderType.MARKET,
        entry_conditions=candidate.entry_conditions,
        limit_price=None,
        stop_price=None,
        target_price=candidate.proposed_target_price,
        maximum_permitted_loss=Decimal("100"),
        expected_reward=Decimal("200"),
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        forecast_id=candidate.distribution_id,
        risk_decision_id=risk_decision.risk_decision_id,
        supervisor_advisory_id=advisory.advisory_id,
        autonomy_token_id=uid(84),
        idempotency_key="order-1",
        created_at=T0,
        payload_hash="0" * 64,
    )
    order = order.model_copy(update={"payload_hash": compute_payload_hash(order)})
    order_facts = OrderEvaluationFacts(
        reference_price=Decimal("100"),
        contract_multiplier=Decimal("1"),
        estimated_fees=Decimal("0"),
        estimated_slippage=Decimal("0"),
        estimated_notional=Decimal("100"),
        estimated_maximum_loss=Decimal("100"),
        estimated_expected_reward=Decimal("200"),
    )
    return {
        "policy": policy,
        "campaign": campaign,
        "campaign_state": campaign_state,
        "market": market,
        "thesis": thesis,
        "distribution": distribution,
        "candidate": candidate,
        "strategy": strategy,
        "context": context,
        "risk_facts": risk_facts,
        "risk_decision": risk_decision,
        "packet": packet,
        "binding": binding,
        "advisory": advisory,
        "system": system,
        "constraints": composition.effective,
        "provenance": composition.provenance,
        "basis": basis,
        "safety": safety,
        "campaign_facts": campaign_facts,
        "order": order,
        "order_facts": order_facts,
        "order_policy": OrderGuardPolicy(allowed_order_types=(PaperOrderType.MARKET,)),
    }


__all__ = ["T0", "_validated", "make_kernel_fixture", "uid"]
