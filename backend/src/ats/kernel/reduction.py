"""Additive A04 eligibility for position-bound, risk-reducing actions.

Entry eligibility remains candidate-bound in ``autonomy.validate_token_eligibility``.
This path deliberately has no OpportunityCandidate input.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import (
    AutonomyToken,
    Position,
    RiskDecision,
    StrategyPolicy,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import PositionStatus
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate
from ats.contracts.governance.types import ActionKind, EffectiveConstraintSet, RiskDirection

from .autonomy import construct_autonomy_token
from .governance import validate_system_state
from .order_guard import constraints_no_broader
from .types import (
    ExecutionSafetyFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    RiskCapitalBasis,
    AutonomyTokenPolicy,
)


def validate_reduction_eligibility(
    *,
    position: Position,
    context: GovernanceContext,
    policy: StrategyPolicy,
    entry_constraints: EffectiveConstraintSet,
    current_constraints: EffectiveConstraintSet,
    capital_basis: RiskCapitalBasis | None,
    requested_quantity: Decimal,
    execution_safety: ExecutionSafetyFacts,
    current_system_state_version: int,
    unresolved_reduction_exists: bool,
    evaluation_time: UTCDateTime,
) -> KernelResult:
    """Fail closed unless a current context safely reduces one durable position."""
    _ = evaluation_time
    reasons: list[GateCode] = []
    if position.status is not PositionStatus.OPEN or position.net_quantity == 0:
        reasons.append(GateCode.POSITION_BINDING)
    if context.action_subject_id != position.position_id:
        reasons.append(GateCode.POSITION_BINDING)
    if context.action_kind not in (ActionKind.REDUCE_POSITION, ActionKind.CLOSE_POSITION):
        reasons.append(GateCode.ACTION_RISK_MISMATCH)
    if context.risk_direction is not RiskDirection.REDUCE:
        reasons.append(GateCode.ACTION_RISK_MISMATCH)
    if context.policy_id != position.policy_id or context.policy_version != position.policy_version:
        reasons.append(GateCode.POSITION_BINDING)
    if context.policy_id != policy.policy_id or context.policy_version != policy.policy_version:
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    if context.system_state_version != current_system_state_version:
        reasons.append(GateCode.TOKEN_STALE_STATE)
    if requested_quantity <= 0 or requested_quantity > abs(position.net_quantity):
        reasons.append(GateCode.QUANTITY_INVALID)
    if unresolved_reduction_exists:
        reasons.append(GateCode.EXECUTION_STATE_UNSAFE)
    if not constraints_no_broader(
        current_constraints, entry_constraints, capital_basis=capital_basis
    ):
        reasons.append(GateCode.POLICY_INCOMPATIBLE)
    system = validate_system_state(context, execution_safety)
    if system.outcome is not KernelOutcome.ALLOW:
        reasons.extend(system.reason_codes)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return KernelResult(outcome=KernelOutcome.ALLOW, reason_codes=(GateCode.OK,))


def construct_reduction_token(
    *,
    eligibility: KernelResult,
    token_id: UUID,
    historical_candidate: OpportunityCandidate,
    policy: StrategyPolicy,
    risk_decision: RiskDecision,
    advisory: SupervisorAdvisory,
    context: GovernanceContext,
    issued_at: UTCDateTime,
    expires_at: UTCDateTime,
    nonce: str,
    token_policy: AutonomyTokenPolicy,
) -> AutonomyToken:
    """Mint a fresh exit token using historical candidate lineage, never entry token reuse."""
    if eligibility.outcome is not KernelOutcome.ALLOW:
        raise ValueError("reduction eligibility must ALLOW")
    if context.risk_direction is not RiskDirection.REDUCE:
        raise ValueError("reduction token requires REDUCE context")
    return construct_autonomy_token(
        eligibility=eligibility,
        token_id=token_id,
        candidate=historical_candidate,
        policy=policy,
        risk_decision=risk_decision,
        advisory=advisory,
        context=context,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        token_policy=token_policy,
    )


__all__ = ["construct_reduction_token", "validate_reduction_eligibility"]
