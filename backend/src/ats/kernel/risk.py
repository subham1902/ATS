"""Deterministic producer for the frozen A02 RiskDecision contract."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import RiskDecision, RiskFacts, StrategyPolicy
from ats.contracts.domain.types import DataQualityState, LossState, RiskOutcome
from ats.contracts.governance.types import EffectiveConstraintSet, RiskDirection

from .constraints import resolve_authority_value
from .types import GateCode, RiskCapitalBasis


def produce_risk_decision(
    facts: RiskFacts,
    policy: StrategyPolicy,
    constraints: EffectiveConstraintSet,
    *,
    risk_decision_id: UUID,
    risk_direction: RiskDirection,
    capital_basis: RiskCapitalBasis | None,
    decided_at: UTCDateTime,
) -> RiskDecision:
    reasons: list[str] = []
    outcome = RiskOutcome.ALLOW
    if facts.policy_id != policy.policy_id or facts.policy_version != policy.policy_version:
        outcome = RiskOutcome.DENY
        reasons.append(GateCode.CANDIDATE_BINDING.value)
    try:
        maximum_loss = resolve_authority_value(
            constraints.maximum_loss_per_trade, basis=capital_basis
        )
    except ValueError:
        maximum_loss = Decimal(0)
        outcome = RiskOutcome.UNKNOWN
        reasons.append(GateCode.UNRESOLVED_BASIS.value)
    if risk_direction is RiskDirection.INCREASE:
        if facts.data_quality_state in (DataQualityState.UNKNOWN, DataQualityState.INVALID):
            outcome = RiskOutcome.UNKNOWN
            reasons.append(GateCode.DATA_QUALITY.value)
        elif facts.data_quality_state is DataQualityState.DEGRADED:
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.DATA_QUALITY.value)
        if facts.loss_state is LossState.HALTED:
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.RISK_DENY.value)
        if facts.drawdown_fraction >= constraints.drawdown_limit:
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.LOSS_LIMIT.value)
        if maximum_loss and facts.proposed_maximum_loss > maximum_loss:
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.LOSS_LIMIT.value)
        if facts.available_cash < facts.proposed_maximum_loss:
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.BUDGET_LIMIT.value)
        if facts.expected_reward <= Decimal(0):
            outcome = RiskOutcome.DENY
            reasons.append(GateCode.ECONOMICS_INVALID.value)
    if outcome is RiskOutcome.ALLOW:
        reasons = []
    decision = RiskDecision(
        schema_version="1.0",
        risk_decision_id=risk_decision_id,
        decision=outcome,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        snapshot_sequence=facts.snapshot_sequence,
        risk_facts_id=facts.risk_facts_id,
        applicable_rule_ids=(
            "maximum_loss_per_trade",
            "drawdown_limit",
            "available_cash",
        ),
        measured_values={
            "proposed_maximum_loss": facts.proposed_maximum_loss,
            "drawdown_fraction": Decimal(facts.drawdown_fraction),
            "available_cash": facts.available_cash,
            "expected_reward": facts.expected_reward,
        },
        limits={
            "maximum_loss_per_trade": maximum_loss,
            "drawdown_limit": Decimal(constraints.drawdown_limit),
        },
        loss_state=facts.loss_state,
        reason_codes=tuple(dict.fromkeys(reasons)),
        decided_at=decided_at,
        payload_hash="0" * 64,
    )
    return decision.model_copy(update={"payload_hash": compute_payload_hash(decision)})


__all__ = ["produce_risk_decision"]
