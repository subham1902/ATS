"""Additive A04 eligibility for position-bound, risk-reducing actions.

Entry eligibility remains candidate-bound in ``autonomy.validate_token_eligibility``.
This path deliberately has no OpportunityCandidate input.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import (
    AutonomyToken,
    Position,
    RiskDecision,
    StrategyPolicy,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    AutonomyLevel,
    PolicyStatus,
    PositionStatus,
    RiskOutcome,
)
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate
from ats.contracts.governance.types import ActionKind, EffectiveConstraintSet, RiskDirection

from .governance import validate_system_state
from .order_guard import constraints_no_broader
from .types import (
    AutonomyTokenPolicy,
    ExecutionSafetyFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    RiskCapitalBasis,
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
    if (
        risk_decision.decision is not RiskOutcome.ALLOW
        or advisory.recommendation is not AdvisoryOutcome.APPROVE
        or policy.lifecycle_status is not PolicyStatus.ACTIVE
        or policy.autonomy_level is not AutonomyLevel.A2
        or risk_decision.policy_id != policy.policy_id
        or risk_decision.policy_version != policy.policy_version
        or context.policy_id != policy.policy_id
        or context.policy_version != policy.policy_version
        or not nonce
    ):
        raise ValueError("reduction token binding inputs are not authority-eligible")
    if expires_at <= issued_at:
        raise ValueError("token expiry must be after issuance")
    if expires_at - issued_at > timedelta(milliseconds=token_policy.max_ttl_ms):
        raise ValueError("token TTL exceeds policy")
    token = AutonomyToken(
        schema_version="1.0",
        token_id=token_id,
        scope="A2_PAPER",
        candidate_id=historical_candidate.candidate_id,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        risk_decision_id=risk_decision.risk_decision_id,
        advisory_id=advisory.advisory_id,
        system_state_version=context.system_state_version,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        consumed_at=None,
        payload_hash="0" * 64,
    )
    return token.model_copy(update={"payload_hash": compute_payload_hash(token)})


__all__ = ["construct_reduction_token", "validate_reduction_eligibility"]
