"""Deterministic construction of evidence-only OpportunityCandidate objects."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import Side
from ats.contracts.governance.models import (
    CampaignState,
    OpportunityCandidate,
    TradingCampaign,
)
from ats.contracts.governance.types import (
    CampaignStatus,
    CandidateStatus,
    StrategyExecutionMode,
)
from ats.contracts.intelligence.models import (
    CalibratedOutcomeDistribution,
    MarketThesis,
    StrategyDefinition,
)
from ats.contracts.intelligence.types import MarketThesisStatus, StrategyStatus
from ats.intelligence.instrument_selector import InstrumentCandidate

from .errors import OpportunityGovernorError
from .models import (
    OpportunityConstructionConfiguration,
    OpportunityConstructionResult,
    OpportunityConstructionStatus,
    OpportunityEconomicsFacts,
)

_CANDIDATE_NAMESPACE = UUID("ba8f10bc-f982-5bcb-909f-b6f422902141")


def construct_opportunity_candidate(
    *,
    instrument_candidate: InstrumentCandidate,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    campaign: TradingCampaign,
    campaign_state: CampaignState,
    strategy: StrategyDefinition,
    economics: OpportunityEconomicsFacts,
    configuration: OpportunityConstructionConfiguration,
    evaluation_time: UTCDateTime,
) -> OpportunityConstructionResult:
    """Build ELIGIBLE evidence; risk/advisory/token references remain absent."""

    _validate_lineage(
        instrument_candidate=instrument_candidate,
        thesis=thesis,
        distribution=distribution,
        campaign=campaign,
        campaign_state=campaign_state,
        strategy=strategy,
    )
    if (
        campaign.status is not CampaignStatus.ACTIVE
        or campaign_state.status is not CampaignStatus.ACTIVE
    ):
        return _ineligible("CAMPAIGN_NOT_ACTIVE")
    if not campaign.start_at <= evaluation_time < campaign.expires_at:
        return _ineligible("CAMPAIGN_TIME_INVALID")
    if (
        campaign_state.cooldown_until is not None
        and evaluation_time < campaign_state.cooldown_until
    ):
        return _ineligible("CAMPAIGN_COOLDOWN")
    if campaign_state.trades_started >= campaign.max_trades:
        return _ineligible("CAMPAIGN_TRADE_CEILING")
    if campaign_state.open_positions >= campaign.max_concurrent_positions:
        return _ineligible("CAMPAIGN_CONCURRENCY_CEILING")
    if thesis.status is not MarketThesisStatus.ACTIVE or thesis.expires_at <= evaluation_time:
        return _ineligible("THESIS_NOT_ACTIVE")
    if distribution.valid_until <= evaluation_time:
        return _ineligible("DISTRIBUTION_EXPIRED")
    if instrument_candidate.expected_net_pnl <= 0:
        return _ineligible("INSTRUMENT_EDGE_NON_POSITIVE")
    if (
        not economics.proposed_stop_price
        < instrument_candidate.entry_ask
        < economics.proposed_target_price
    ):
        raise OpportunityGovernorError("long-option stop/entry/target ordering is invalid")
    if instrument_candidate.instrument_id not in campaign.instrument_universe:
        return _ineligible("INSTRUMENT_OUTSIDE_CAMPAIGN")
    if thesis.timeframe not in campaign.allowed_timeframes:
        return _ineligible("TIMEFRAME_OUTSIDE_CAMPAIGN")
    if not _strategy_eligible(
        strategy,
        campaign,
        instrument_id=instrument_candidate.instrument_id,
        timeframe=thesis.timeframe,
    ):
        return _ineligible("STRATEGY_NOT_EXECUTION_ELIGIBLE")
    probability = _probability(distribution, configuration.target_outcome_code)
    expected_edge_r_decimal = instrument_candidate.expected_net_pnl / economics.maximum_loss
    expected_reward_risk = economics.expected_reward / economics.maximum_loss
    expires_at = min(
        thesis.expires_at,
        distribution.valid_until,
        evaluation_time + timedelta(milliseconds=configuration.maximum_ttl_ms),
    )
    if expires_at <= evaluation_time:
        return _ineligible("CANDIDATE_EXPIRY_INVALID")
    identity = ":".join(
        (
            str(instrument_candidate.instrument_candidate_id),
            str(thesis.thesis_id),
            str(campaign.campaign_id),
            str(strategy.strategy_definition_id),
            configuration.governor_version,
        )
    )
    value = OpportunityCandidate(
        schema_version="1.0",
        candidate_id=uuid5(_CANDIDATE_NAMESPACE, identity),
        candidate_version=1,
        instrument_id=instrument_candidate.instrument_id,
        market_context_id=thesis.market_context_id,
        thesis_id=thesis.thesis_id,
        thesis_version=thesis.thesis_version,
        distribution_id=distribution.distribution_id,
        campaign_id=campaign.campaign_id,
        campaign_version=campaign.campaign_version,
        strategy_definition_id=strategy.strategy_definition_id,
        strategy_definition_version=strategy.strategy_definition_version,
        side=Side.BUY,
        event_definition_id=distribution.event_definition_id,
        horizon_bars=distribution.horizon_bars,
        target_outcome_code=configuration.target_outcome_code,
        calibrated_probability=probability,
        expected_net_edge_r=float(expected_edge_r_decimal),
        expected_reward_risk=expected_reward_risk,
        entry_conditions=thesis.opportunity_conditions,
        proposed_stop_price=economics.proposed_stop_price,
        proposed_target_price=economics.proposed_target_price,
        evidence_refs=(
            instrument_candidate.instrument_candidate_id,
            thesis.thesis_id,
            distribution.distribution_id,
            campaign_state.campaign_state_id,
            strategy.strategy_definition_id,
        ),
        status=CandidateStatus.ELIGIBLE,
        risk_decision_id=None,
        advisory_id=None,
        autonomy_token_id=None,
        created_at=evaluation_time,
        expires_at=expires_at,
        payload_hash="0" * 64,
    )
    candidate = value.model_copy(update={"payload_hash": compute_payload_hash(value)})
    return OpportunityConstructionResult(
        status=OpportunityConstructionStatus.ELIGIBLE_CANDIDATE,
        candidate=candidate,
        reason_codes=("CANDIDATE_ELIGIBLE_FOR_RISK_EVALUATION",),
    )


def _validate_lineage(
    *,
    instrument_candidate: InstrumentCandidate,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    campaign: TradingCampaign,
    campaign_state: CampaignState,
    strategy: StrategyDefinition,
) -> None:
    for name, value in (
        ("instrument candidate", instrument_candidate),
        ("thesis", thesis),
        ("distribution", distribution),
        ("campaign", campaign),
        ("campaign state", campaign_state),
        ("strategy", strategy),
    ):
        if compute_payload_hash(value) != value.payload_hash:
            raise OpportunityGovernorError(f"{name} payload hash mismatch")
    if (
        instrument_candidate.thesis_id != thesis.thesis_id
        or instrument_candidate.thesis_version != thesis.thesis_version
        or instrument_candidate.distribution_id != distribution.distribution_id
        or thesis.distribution_id != distribution.distribution_id
        or distribution.market_context_id != thesis.market_context_id
        or distribution.instrument_id != thesis.instrument_id
    ):
        raise OpportunityGovernorError("instrument/thesis/distribution lineage mismatch")
    if (
        campaign_state.campaign_id != campaign.campaign_id
        or campaign_state.campaign_version != campaign.campaign_version
    ):
        raise OpportunityGovernorError("campaign state lineage mismatch")


def _strategy_eligible(
    strategy: StrategyDefinition,
    campaign: TradingCampaign,
    *,
    instrument_id: str,
    timeframe: str,
) -> bool:
    ref_allowed = any(
        ref.strategy_definition_id == strategy.strategy_definition_id
        and ref.strategy_definition_version == strategy.strategy_definition_version
        for ref in campaign.allowed_strategies
    )
    if not ref_allowed:
        return False
    if instrument_id not in strategy.compatible_instruments:
        return False
    if timeframe not in strategy.compatible_timeframes:
        return False
    if strategy.status is StrategyStatus.CHAMPION:
        return True
    return (
        strategy.status is StrategyStatus.CHALLENGER
        and campaign.strategy_execution_mode is StrategyExecutionMode.ISOLATED_CHALLENGER_PAPER
        and campaign.scope == "A2_PAPER"
    )


def _probability(distribution: CalibratedOutcomeDistribution, code: str) -> Decimal:
    matches = tuple(item for item in distribution.outcomes if item.outcome_code == code)
    if len(matches) != 1:
        raise OpportunityGovernorError("target outcome must exist exactly once")
    return matches[0].probability


def _ineligible(reason: str) -> OpportunityConstructionResult:
    return OpportunityConstructionResult(
        status=OpportunityConstructionStatus.INELIGIBLE,
        candidate=None,
        reason_codes=(reason,),
    )


__all__ = ["construct_opportunity_candidate"]
