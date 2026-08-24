"""Pure Stage 1 A2 eligibility, decision binding, and token validation."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.models import (
    AutonomyToken,
    DecisionPacket,
    RiskDecision,
    StrategyPolicy,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import AdvisoryOutcome, AutonomyLevel, PolicyStatus, RiskOutcome
from ats.contracts.governance.models import (
    CampaignState,
    GovernanceContext,
    OpportunityCandidate,
    TradingCampaign,
)
from ats.contracts.governance.types import CandidateStatus, EffectiveConstraintSet
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    MarketContext,
    MarketThesis,
    StrategyDefinition,
)

from .action_risk import validate_declared_action_risk
from .governance import (
    validate_campaign_gate,
    validate_candidate_binding,
    validate_intelligence_freshness,
    validate_probability_economics,
    validate_strategy_status,
    validate_system_state,
)
from .policy import validate_strategy_policy
from .types import (
    ALLOW,
    AutonomyTokenPolicy,
    CampaignEvaluationFacts,
    DecisionBindingEvidence,
    ExecutionSafetyFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    RiskCapitalBasis,
)


def build_decision_binding(
    candidate: OpportunityCandidate,
    context: GovernanceContext,
    campaign: TradingCampaign,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    strategy: StrategyDefinition,
) -> DecisionBindingEvidence:
    return DecisionBindingEvidence(
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.candidate_version,
        candidate_payload_hash=candidate.payload_hash,
        governance_context_id=context.governance_context_id,
        governance_context_hash=context.payload_hash,
        campaign_id=campaign.campaign_id,
        campaign_version=campaign.campaign_version,
        market_thesis_id=thesis.thesis_id,
        market_thesis_version=thesis.thesis_version,
        distribution_id=distribution.distribution_id,
        strategy_definition_id=strategy.strategy_definition_id,
        strategy_definition_version=strategy.strategy_definition_version,
    )


def binding_to_bounded_json(binding: DecisionBindingEvidence) -> dict[str, object]:
    return binding.model_dump(mode="json")


def validate_decision_packet_binding(
    packet: DecisionPacket,
    binding: DecisionBindingEvidence,
    *,
    candidate: OpportunityCandidate,
    context: GovernanceContext,
    campaign: TradingCampaign,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    strategy: StrategyDefinition,
    risk_decision: RiskDecision,
) -> KernelResult:
    expected = build_decision_binding(candidate, context, campaign, thesis, distribution, strategy)
    valid = (
        binding == expected
        and packet.candidate_id == candidate.candidate_id
        and packet.policy_id == context.policy_id
        and packet.policy_version == context.policy_version
        and packet.risk_decision_id == risk_decision.risk_decision_id
        and packet.bounded_evidence == binding_to_bounded_json(binding)
        and candidate.payload_hash == compute_payload_hash(candidate)
        and context.payload_hash == compute_payload_hash(context)
    )
    if not valid:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.CANDIDATE_BINDING,))
    return ALLOW


def validate_token_eligibility(
    *,
    policy: StrategyPolicy,
    campaign: TradingCampaign,
    campaign_state: CampaignState,
    market: MarketContext,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    candidate: OpportunityCandidate,
    strategy: StrategyDefinition,
    context: GovernanceContext,
    risk_decision: RiskDecision,
    advisory: SupervisorAdvisory,
    packet: DecisionPacket,
    binding: DecisionBindingEvidence,
    constraints: EffectiveConstraintSet,
    campaign_facts: CampaignEvaluationFacts,
    capital_basis: RiskCapitalBasis | None,
    execution_safety: ExecutionSafetyFacts,
    evaluation_time: UTCDateTime,
    current_system_state_version: int,
    maximum_freshness_ms: int,
    model_version: str,
    model_family: str,
    calibrator_version: str,
) -> KernelResult:
    gates = (
        validate_strategy_policy(
            policy,
            evaluation_time=evaluation_time,
            timeframe=market.timeframe,
            event_definition_id=str(candidate.event_definition_id),
            model_version=model_version,
            calibrator_version=calibrator_version,
        ),
        validate_campaign_gate(
            campaign,
            campaign_state,
            constraints,
            campaign_facts,
            capital_basis=capital_basis,
            evaluation_time=evaluation_time,
        ),
        validate_strategy_status(strategy, campaign),
        validate_system_state(context, execution_safety),
        validate_declared_action_risk(context),
        validate_intelligence_freshness(
            context,
            market,
            thesis,
            distribution,
            candidate,
            constraints,
            evaluation_time=evaluation_time,
            maximum_freshness_ms=maximum_freshness_ms,
        ),
        validate_probability_economics(candidate, distribution, constraints),
        validate_candidate_binding(
            candidate,
            thesis,
            distribution,
            campaign,
            campaign_state,
            strategy,
            policy,
            context,
        ),
        validate_decision_packet_binding(
            packet,
            binding,
            candidate=candidate,
            context=context,
            campaign=campaign,
            thesis=thesis,
            distribution=distribution,
            strategy=strategy,
            risk_decision=risk_decision,
        ),
    )
    reasons = tuple(
        dict.fromkeys(
            reason
            for gate in gates
            if gate.outcome is not KernelOutcome.ALLOW
            for reason in gate.reason_codes
        )
    )
    if candidate.status is not CandidateStatus.ADVISED:
        reasons += (GateCode.CANDIDATE_BINDING,)
    if context.system_state_version != current_system_state_version:
        reasons += (GateCode.TOKEN_STALE_STATE,)
    if context.resolved_constraints != constraints:
        reasons += (GateCode.CANDIDATE_BINDING,)
    strategy_ref = (
        candidate.strategy_definition_id,
        candidate.strategy_definition_version,
    )
    allowed_strategy_refs = {
        (item.strategy_definition_id, item.strategy_definition_version)
        for item in constraints.allowed_strategies
    }
    if (
        candidate.instrument_id not in constraints.allowed_instruments
        or market.timeframe not in constraints.allowed_timeframes
        or strategy_ref not in allowed_strategy_refs
    ):
        reasons += (GateCode.CANDIDATE_BINDING,)
    for requirement in campaign.model_requirements:
        if requirement.required and (
            requirement.model_family != model_family
            or (requirement.allowed_versions and model_version not in requirement.allowed_versions)
        ):
            reasons += (GateCode.POLICY_INCOMPATIBLE,)
    if risk_decision.decision is RiskOutcome.DENY:
        reasons += (GateCode.RISK_DENY,)
    elif risk_decision.decision is RiskOutcome.UNKNOWN:
        reasons += (GateCode.RISK_UNKNOWN,)
    if (
        advisory.packet_id != packet.packet_id
        or advisory.recommendation is not AdvisoryOutcome.APPROVE
    ):
        reasons += (GateCode.ADVISORY_DENY,)
    if reasons:
        return KernelResult(
            outcome=KernelOutcome.DENY,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )
    return ALLOW


def construct_autonomy_token(
    *,
    eligibility: KernelResult,
    token_id: UUID,
    candidate: OpportunityCandidate,
    policy: StrategyPolicy,
    risk_decision: RiskDecision,
    advisory: SupervisorAdvisory,
    context: GovernanceContext,
    issued_at: UTCDateTime,
    expires_at: UTCDateTime,
    nonce: str,
    token_policy: AutonomyTokenPolicy,
) -> AutonomyToken:
    if eligibility.outcome is not KernelOutcome.ALLOW:
        raise ValueError("token eligibility did not ALLOW")
    if (
        risk_decision.decision is not RiskOutcome.ALLOW
        or advisory.recommendation is not AdvisoryOutcome.APPROVE
        or policy.lifecycle_status is not PolicyStatus.ACTIVE
        or policy.autonomy_level is not AutonomyLevel.A2
        or candidate.status is not CandidateStatus.ADVISED
        or candidate.risk_decision_id != risk_decision.risk_decision_id
        or candidate.advisory_id != advisory.advisory_id
        or context.candidate_id != candidate.candidate_id
        or context.candidate_version != candidate.candidate_version
        or context.policy_id != policy.policy_id
        or context.policy_version != policy.policy_version
    ):
        raise ValueError("token binding inputs are not authority-eligible")
    if expires_at <= issued_at:
        raise ValueError("token expiry must be after issuance")
    if expires_at - issued_at > timedelta(milliseconds=token_policy.max_ttl_ms):
        raise ValueError("token TTL exceeds policy")
    token = AutonomyToken(
        schema_version="1.0",
        token_id=token_id,
        scope="A2_PAPER",
        candidate_id=candidate.candidate_id,
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


def validate_token_for_use(
    token: AutonomyToken,
    *,
    evaluation_time: UTCDateTime,
    candidate_id: UUID,
    policy_id: UUID,
    policy_version: int,
    risk_decision_id: UUID,
    advisory_id: UUID,
    current_system_state_version: int,
) -> KernelResult:
    if token.scope != "A2_PAPER" or token.payload_hash != compute_payload_hash(token):
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,))
    if token.consumed_at is not None:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_CONSUMED,))
    if evaluation_time >= token.expires_at or evaluation_time < token.issued_at:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_EXPIRED,))
    if token.system_state_version != current_system_state_version:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_STALE_STATE,))
    if (
        token.candidate_id != candidate_id
        or token.policy_id != policy_id
        or token.policy_version != policy_version
        or token.risk_decision_id != risk_decision_id
        or token.advisory_id != advisory_id
        or not token.nonce
    ):
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.TOKEN_INVALID,))
    return ALLOW


__all__ = [
    "binding_to_bounded_json",
    "build_decision_binding",
    "construct_autonomy_token",
    "validate_decision_packet_binding",
    "validate_token_eligibility",
    "validate_token_for_use",
]
