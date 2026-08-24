"""Pure campaign, system-state, intelligence, economics, and binding gates."""

from __future__ import annotations

from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import StrategyPolicy
from ats.contracts.domain.types import DataQualityState
from ats.contracts.governance.models import (
    CampaignState,
    GovernanceContext,
    OpportunityCandidate,
    TradingCampaign,
)
from ats.contracts.governance.types import (
    ActionKind,
    CampaignStatus,
    CandidateStatus,
    EffectiveConstraintSet,
    RiskDirection,
    StrategyExecutionMode,
    SystemState,
)
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    MarketContext,
    MarketThesis,
    StrategyDefinition,
)
from ats.contracts.intelligence.types import MarketThesisStatus, StrategyStatus

from .constraints import resolve_authority_value
from .types import (
    ALLOW,
    CampaignEvaluationFacts,
    ExecutionSafetyFacts,
    GateCode,
    KernelOutcome,
    KernelResult,
    RiskCapitalBasis,
)


def validate_system_state(
    context: GovernanceContext,
    safety: ExecutionSafetyFacts,
) -> KernelResult:
    state = context.system_state
    direction = context.risk_direction
    if state is SystemState.READY:
        if direction is RiskDirection.REDUCE and not safety.fully_known_safe:
            return KernelResult(
                outcome=KernelOutcome.DENY,
                reason_codes=(GateCode.EXECUTION_STATE_UNSAFE,),
            )
        return ALLOW
    if direction is RiskDirection.INCREASE:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.SYSTEM_STATE_DENY,))
    if direction is RiskDirection.REDUCE:
        if state in (SystemState.DEGRADED, SystemState.RECONCILING, SystemState.HALTED):
            return (
                ALLOW
                if safety.fully_known_safe
                else KernelResult(
                    outcome=KernelOutcome.DENY,
                    reason_codes=(GateCode.EXECUTION_STATE_UNSAFE,),
                )
            )
        if state is SystemState.UNKNOWN:
            if context.action_kind is ActionKind.EMERGENCY_FLATTEN and safety.fully_known_safe:
                return ALLOW
            return KernelResult(
                outcome=KernelOutcome.DENY,
                reason_codes=(GateCode.SYSTEM_STATE_DENY,),
            )
    return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.SYSTEM_STATE_DENY,))


def validate_campaign_gate(
    campaign: TradingCampaign,
    state: CampaignState,
    constraints: EffectiveConstraintSet,
    facts: CampaignEvaluationFacts,
    *,
    capital_basis: RiskCapitalBasis | None,
    evaluation_time: UTCDateTime,
) -> KernelResult:
    reasons: list[GateCode] = []
    if campaign.scope != "A2_PAPER" or campaign.status is not CampaignStatus.ACTIVE:
        reasons.append(GateCode.CAMPAIGN_INACTIVE)
    if not campaign.start_at <= evaluation_time < campaign.expires_at:
        reasons.append(GateCode.CAMPAIGN_TIME_INVALID)
    if (
        state.status is not CampaignStatus.ACTIVE
        or state.campaign_id != campaign.campaign_id
        or state.campaign_version != campaign.campaign_version
    ):
        reasons.append(GateCode.CAMPAIGN_BINDING_MISMATCH)
    if (
        state.trades_started >= constraints.max_trades
        or state.open_positions >= constraints.max_concurrent_positions
        or state.maximum_drawdown_observed >= constraints.drawdown_limit
        or facts.campaign_loss_limit_reached
        or facts.capital_limit_reached
        or facts.stop_condition_triggered
        or state.capital_committed >= constraints.capital_budget
    ):
        reasons.append(GateCode.CAMPAIGN_LIMIT_REACHED)
    try:
        maximum_campaign_loss = resolve_authority_value(
            constraints.maximum_campaign_loss,
            basis=capital_basis,
            campaign_basis=True,
        )
    except ValueError:
        return KernelResult(
            outcome=KernelOutcome.UNKNOWN,
            reason_codes=(GateCode.UNRESOLVED_BASIS,),
        )
    current_loss = max(Decimal("0"), -(state.realized_pnl + state.unrealized_pnl))
    if current_loss >= maximum_campaign_loss:
        reasons.append(GateCode.CAMPAIGN_LIMIT_REACHED)
    if state.cooldown_until is not None and evaluation_time < state.cooldown_until:
        reasons.append(GateCode.CAMPAIGN_COOLDOWN)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return ALLOW


def validate_strategy_status(
    strategy: StrategyDefinition,
    campaign: TradingCampaign,
) -> KernelResult:
    if strategy.status is StrategyStatus.CHAMPION:
        return ALLOW
    if (
        strategy.status is StrategyStatus.CHALLENGER
        and campaign.strategy_execution_mode is StrategyExecutionMode.ISOLATED_CHALLENGER_PAPER
        and campaign.scope == "A2_PAPER"
    ):
        return ALLOW
    return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.STRATEGY_STATUS,))


def validate_intelligence_freshness(
    context: GovernanceContext,
    market: MarketContext,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    candidate: OpportunityCandidate,
    constraints: EffectiveConstraintSet,
    *,
    evaluation_time: UTCDateTime,
    maximum_freshness_ms: int,
) -> KernelResult:
    reasons: list[GateCode] = []
    if market.market_context_id != context.market_context_id:
        reasons.append(GateCode.EVIDENCE_BINDING_MISMATCH)
    if market.data_quality_state is not DataQualityState.GOOD:
        reasons.append(GateCode.DATA_QUALITY)
    if market.freshness_ms > maximum_freshness_ms:
        reasons.append(GateCode.DATA_STALE)
    if thesis.status is not MarketThesisStatus.ACTIVE or thesis.expires_at <= evaluation_time:
        reasons.append(GateCode.EVIDENCE_EXPIRED)
    if (
        thesis.market_context_id != market.market_context_id
        or thesis.instrument_id != market.instrument_id
    ):
        reasons.append(GateCode.EVIDENCE_BINDING_MISMATCH)
    if distribution.valid_until <= evaluation_time:
        reasons.append(GateCode.EVIDENCE_EXPIRED)
    if distribution.quality_state is not DataQualityState.GOOD:
        reasons.append(GateCode.DATA_QUALITY)
    if distribution.market_context_id != market.market_context_id:
        reasons.append(GateCode.EVIDENCE_BINDING_MISMATCH)
    if distribution.support_count < constraints.minimum_calibration_support:
        reasons.append(GateCode.CALIBRATION_SUPPORT)
    if candidate.expires_at <= evaluation_time or candidate.status in (
        CandidateStatus.REJECTED,
        CandidateStatus.EXPIRED,
        CandidateStatus.CONSUMED,
    ):
        reasons.append(GateCode.EVIDENCE_EXPIRED)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return ALLOW


def validate_probability_economics(
    candidate: OpportunityCandidate,
    distribution: CalibratedOutcomeDistribution,
    constraints: EffectiveConstraintSet,
) -> KernelResult:
    reasons: list[GateCode] = []
    matches = [
        item for item in distribution.outcomes if item.outcome_code == candidate.target_outcome_code
    ]
    if len(matches) != 1:
        reasons.append(GateCode.PROBABILITY_BINDING)
    elif matches[0].probability != candidate.calibrated_probability:
        reasons.append(GateCode.PROBABILITY_BINDING)
    if candidate.calibrated_probability < constraints.minimum_calibrated_probability:
        reasons.append(GateCode.PROBABILITY_THRESHOLD)
    if distribution.support_count < constraints.minimum_calibration_support:
        reasons.append(GateCode.CALIBRATION_SUPPORT)
    if (
        candidate.expected_net_edge_r <= 0
        or candidate.expected_net_edge_r < constraints.minimum_expected_edge_r
    ):
        reasons.append(GateCode.EDGE_THRESHOLD)
    if candidate.expected_reward_risk < constraints.minimum_reward_risk:
        reasons.append(GateCode.REWARD_RISK_THRESHOLD)
    if reasons:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=tuple(dict.fromkeys(reasons)))
    return ALLOW


def validate_candidate_binding(
    candidate: OpportunityCandidate,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    campaign: TradingCampaign,
    campaign_state: CampaignState,
    strategy: StrategyDefinition,
    policy: StrategyPolicy,
    context: GovernanceContext,
) -> KernelResult:
    valid = (
        candidate.instrument_id == thesis.instrument_id == distribution.instrument_id
        and candidate.market_context_id
        == thesis.market_context_id
        == distribution.market_context_id
        and candidate.thesis_id == thesis.thesis_id
        and candidate.thesis_version == thesis.thesis_version
        and candidate.distribution_id == distribution.distribution_id
        and candidate.event_definition_id == distribution.event_definition_id
        and candidate.horizon_bars == distribution.horizon_bars
        and candidate.campaign_id == campaign.campaign_id == campaign_state.campaign_id
        and candidate.campaign_version
        == campaign.campaign_version
        == campaign_state.campaign_version
        and candidate.strategy_definition_id == strategy.strategy_definition_id
        and candidate.strategy_definition_version == strategy.strategy_definition_version
        and context.candidate_id == candidate.candidate_id
        and context.candidate_version == candidate.candidate_version
        and context.policy_id == policy.policy_id
        and context.policy_version == policy.policy_version
        and context.campaign_id == campaign.campaign_id
        and context.campaign_version == campaign.campaign_version
        and context.campaign_state_id == campaign_state.campaign_state_id
        and context.campaign_state_version == campaign_state.state_version
        and context.strategy_definition_id == strategy.strategy_definition_id
        and context.strategy_definition_version == strategy.strategy_definition_version
        and context.market_context_id == candidate.market_context_id
        and context.authority_scope == "A2_PAPER"
        and policy.event_definition_id == str(candidate.event_definition_id)
        and policy.forecast_horizon_bars == candidate.horizon_bars
        and candidate.instrument_id in policy.universe
        and candidate.instrument_id in campaign.instrument_universe
        and candidate.instrument_id in strategy.compatible_instruments
        and candidate.market_context_id == context.market_context_id
        and thesis.timeframe in campaign.allowed_timeframes
        and thesis.timeframe in strategy.compatible_timeframes
    )
    if not valid:
        return KernelResult(outcome=KernelOutcome.DENY, reason_codes=(GateCode.CANDIDATE_BINDING,))
    return ALLOW


__all__ = [
    "validate_campaign_gate",
    "validate_candidate_binding",
    "validate_intelligence_freshness",
    "validate_probability_economics",
    "validate_strategy_status",
    "validate_system_state",
]
