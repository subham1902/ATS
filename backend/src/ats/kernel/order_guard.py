"""Pure Stage 2 exact-order and safe-exit guards; no submission or persistence."""

from __future__ import annotations

from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import AutonomyToken, ExitIntent, OrderIntent, Position
from ats.contracts.governance.models import (
    CampaignState,
    GovernanceContext,
    OpportunityCandidate,
)
from ats.contracts.governance.types import CampaignStatus, EffectiveConstraintSet, RiskDirection

from .action_risk import validate_declared_action_risk
from .autonomy import validate_token_for_use
from .constraints import resolve_authority_value
from .governance import validate_system_state
from .types import (
    ALLOW,
    ExecutionSafetyFacts,
    ExitEvaluationFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    OrderEvaluationFacts,
    OrderGuardPolicy,
    RiskCapitalBasis,
)


def constraints_no_broader(
    current: EffectiveConstraintSet,
    issued: EffectiveConstraintSet,
    *,
    capital_basis: RiskCapitalBasis | None,
) -> bool:
    try:
        maximums_ok = (
            resolve_authority_value(current.maximum_loss_per_trade, basis=capital_basis)
            <= resolve_authority_value(issued.maximum_loss_per_trade, basis=capital_basis)
            and resolve_authority_value(
                current.maximum_campaign_loss,
                basis=capital_basis,
                campaign_basis=True,
            )
            <= resolve_authority_value(
                issued.maximum_campaign_loss,
                basis=capital_basis,
                campaign_basis=True,
            )
            and resolve_authority_value(current.maximum_budget_per_trade, basis=capital_basis)
            <= resolve_authority_value(issued.maximum_budget_per_trade, basis=capital_basis)
            and current.drawdown_limit <= issued.drawdown_limit
            and current.max_trades <= issued.max_trades
            and current.max_concurrent_positions <= issued.max_concurrent_positions
            and current.capital_budget <= issued.capital_budget
        )
    except ValueError:
        return False
    minimums_ok = (
        current.minimum_calibrated_probability >= issued.minimum_calibrated_probability
        and current.minimum_calibration_support >= issued.minimum_calibration_support
        and current.minimum_expected_edge_r >= issued.minimum_expected_edge_r
        and current.minimum_reward_risk >= issued.minimum_reward_risk
    )
    allowlists_ok = (
        set(current.allowed_instruments) <= set(issued.allowed_instruments)
        and set(current.allowed_timeframes) <= set(issued.allowed_timeframes)
        and set(current.allowed_strategies) <= set(issued.allowed_strategies)
    )
    mode_ok = (
        current.strategy_execution_mode == issued.strategy_execution_mode
        or current.strategy_execution_mode.value == "CHAMPION_ONLY"
    )
    return maximums_ok and minimums_ok and allowlists_ok and mode_ok


def validate_order_intent(
    intent: OrderIntent,
    *,
    token: AutonomyToken,
    candidate: OpportunityCandidate,
    context: GovernanceContext,
    campaign_state: CampaignState,
    issued_constraints: EffectiveConstraintSet,
    current_constraints: EffectiveConstraintSet,
    capital_basis: RiskCapitalBasis | None,
    order_facts: OrderEvaluationFacts,
    order_policy: OrderGuardPolicy,
    execution_safety: ExecutionSafetyFacts,
    evaluation_time: UTCDateTime,
    current_system_state_version: int,
) -> KernelResult:
    token_result = validate_token_for_use(
        token,
        evaluation_time=evaluation_time,
        candidate_id=candidate.candidate_id,
        policy_id=intent.policy_id,
        policy_version=intent.policy_version,
        risk_decision_id=intent.risk_decision_id,
        advisory_id=intent.supervisor_advisory_id,
        current_system_state_version=current_system_state_version,
    )
    if token_result.outcome is not KernelOutcome.ALLOW:
        return token_result
    reasons: list[GateCode] = []
    if (
        intent.autonomy_token_id != token.token_id
        or intent.instrument_id != candidate.instrument_id
        or intent.side is not candidate.side
        or intent.policy_id != context.policy_id
        or intent.policy_version != context.policy_version
        or intent.risk_decision_id != token.risk_decision_id
        or intent.supervisor_advisory_id != token.advisory_id
        or candidate.risk_decision_id != token.risk_decision_id
        or candidate.advisory_id != token.advisory_id
        or intent.forecast_id != candidate.distribution_id
        or candidate.expires_at <= evaluation_time
        or context.system_state_version != current_system_state_version
        or context.candidate_id != candidate.candidate_id
        or context.candidate_version != candidate.candidate_version
        or context.campaign_state_id != campaign_state.campaign_state_id
        or context.campaign_state_version != campaign_state.state_version
        or campaign_state.status is not CampaignStatus.ACTIVE
        or candidate.instrument_id not in current_constraints.allowed_instruments
        or not any(
            ref.strategy_definition_id == candidate.strategy_definition_id
            and ref.strategy_definition_version == candidate.strategy_definition_version
            for ref in current_constraints.allowed_strategies
        )
    ):
        reasons.append(GateCode.ORDER_BINDING)
    if intent.order_type not in order_policy.allowed_order_types:
        reasons.append(GateCode.ORDER_TYPE)
    if order_facts.estimated_notional != (
        intent.quantity * order_facts.reference_price * order_facts.contract_multiplier
    ):
        reasons.append(GateCode.NOTIONAL_MISMATCH)
    if order_facts.estimated_expected_reward != intent.expected_reward:
        reasons.append(GateCode.ECONOMICS_INVALID)
    if not constraints_no_broader(
        current_constraints, issued_constraints, capital_basis=capital_basis
    ):
        reasons.append(GateCode.ORDER_BINDING)
    if validate_system_state(context, execution_safety).outcome is not KernelOutcome.ALLOW:
        reasons.append(GateCode.SYSTEM_STATE_DENY)
    try:
        maximum_loss = resolve_authority_value(
            current_constraints.maximum_loss_per_trade, basis=capital_basis
        )
        maximum_budget = resolve_authority_value(
            current_constraints.maximum_budget_per_trade, basis=capital_basis
        )
        maximum_campaign_loss = resolve_authority_value(
            current_constraints.maximum_campaign_loss,
            basis=capital_basis,
            campaign_basis=True,
        )
    except ValueError:
        return KernelResult(
            outcome=KernelOutcome.UNKNOWN,
            reason_codes=(GateCode.UNRESOLVED_BASIS,),
        )
    if (
        intent.maximum_permitted_loss > maximum_loss
        or order_facts.estimated_maximum_loss > intent.maximum_permitted_loss
    ):
        reasons.append(GateCode.LOSS_LIMIT)
    if (
        order_facts.estimated_notional > maximum_budget
        or campaign_state.capital_committed + order_facts.estimated_notional
        > current_constraints.capital_budget
    ):
        reasons.append(GateCode.BUDGET_LIMIT)
    current_loss = max(Decimal(0), -(campaign_state.realized_pnl + campaign_state.unrealized_pnl))
    if current_loss + order_facts.estimated_maximum_loss > maximum_campaign_loss:
        reasons.append(GateCode.LOSS_LIMIT)
    if campaign_state.maximum_drawdown_observed >= current_constraints.drawdown_limit:
        reasons.append(GateCode.LOSS_LIMIT)
    net_reward = (
        order_facts.estimated_expected_reward
        - order_facts.estimated_fees
        - order_facts.estimated_slippage
    )
    if (
        net_reward <= 0
        or net_reward / order_facts.estimated_maximum_loss < current_constraints.minimum_reward_risk
    ):
        reasons.append(GateCode.ECONOMICS_INVALID)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return ALLOW


def validate_exit_intent(
    intent: ExitIntent,
    *,
    token: AutonomyToken,
    candidate: OpportunityCandidate,
    position: Position,
    context: GovernanceContext,
    exit_facts: ExitEvaluationFacts,
    execution_safety: ExecutionSafetyFacts,
    evaluation_time: UTCDateTime,
    current_system_state_version: int,
) -> KernelResult:
    token_result = validate_token_for_use(
        token,
        evaluation_time=evaluation_time,
        candidate_id=candidate.candidate_id,
        policy_id=token.policy_id,
        policy_version=token.policy_version,
        risk_decision_id=intent.risk_decision_id,
        advisory_id=token.advisory_id,
        current_system_state_version=current_system_state_version,
    )
    if token_result.outcome is not KernelOutcome.ALLOW:
        return token_result
    if (
        intent.autonomy_token_id != token.token_id
        or intent.position_id != position.position_id
        or intent.position_version != position.version
        or intent.quantity > exit_facts.reducible_quantity
        or intent.quantity > abs(position.net_quantity)
        or context.risk_direction is not RiskDirection.REDUCE
        or validate_declared_action_risk(context).outcome is not KernelOutcome.ALLOW
    ):
        return KernelResult(
            outcome=KernelOutcome.DENY,
            reason_codes=(GateCode.POSITION_BINDING,),
        )
    return validate_system_state(context, execution_safety)


__all__ = ["constraints_no_broader", "validate_exit_intent", "validate_order_intent"]
