"""Frozen IBA-C01 governance contracts: data and intrinsic validation only."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, Probability, UTCDateTime
from ats.contracts.domain.types import (
    CooldownRule,
    DataQualityState,
    InstrumentId,
    MoneyOrPortfolioFraction,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PortfolioFraction,
    PositiveDecimal,
    PositiveInt,
    Predicate,
    Sha256,
    Side,
    ensure_unique,
)
from ats.contracts.intelligence.types import (
    BoundedText,
    ModelRequirement,
    PositiveFiniteFloat,
    RegimeConstraint,
    RegisteredCode,
    StrategyRef,
)

from .types import (
    ActionKind,
    CampaignStatus,
    CandidateStatus,
    ConstraintCode,
    ConstraintProvenance,
    EffectiveConstraintSet,
    PositionRecommendation,
    PositionThesisState,
    RiskDirection,
    StrategyExecutionMode,
    SystemState,
)


class TradingCampaign(ATSBaseModel):
    schema_version: Literal["1.0"]
    campaign_id: UUID
    campaign_version: PositiveInt
    name: NonEmptyStr
    objective: BoundedText
    scope: Literal["A2_PAPER"]
    policy_id: UUID
    policy_version: PositiveInt
    instrument_universe: tuple[InstrumentId, ...]
    allowed_strategies: tuple[StrategyRef, ...]
    strategy_execution_mode: StrategyExecutionMode
    allowed_timeframes: tuple[RegisteredCode, ...]
    max_trades: PositiveInt
    max_concurrent_positions: PositiveInt
    capital_budget: PositiveDecimal
    maximum_budget_per_trade: MoneyOrPortfolioFraction
    maximum_loss_per_trade: MoneyOrPortfolioFraction
    maximum_campaign_loss: MoneyOrPortfolioFraction
    drawdown_limit: PortfolioFraction
    minimum_calibrated_probability: Probability
    minimum_calibration_support: PositiveInt
    minimum_expected_edge_r: PositiveFiniteFloat
    minimum_reward_risk: PositiveDecimal
    regime_constraints: tuple[RegimeConstraint, ...]
    model_requirements: tuple[ModelRequirement, ...]
    start_at: UTCDateTime
    expires_at: UTCDateTime
    cooldown_rule: CooldownRule
    stop_conditions: tuple[Predicate, ...]
    status: CampaignStatus
    created_by: NonEmptyStr
    created_at: UTCDateTime
    activated_at: UTCDateTime | None
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_campaign(self) -> TradingCampaign:
        for name in ("instrument_universe", "allowed_strategies", "allowed_timeframes"):
            values = getattr(self, name)
            if not values:
                raise ValueError(f"{name} must be non-empty")
            ensure_unique(values, name)
        ensure_unique(self.regime_constraints, "regime_constraints")
        ensure_unique(self.model_requirements, "model_requirements")
        if self.expires_at <= self.start_at:
            raise ValueError("expires_at must be > start_at")
        activated_required = self.status in (
            CampaignStatus.ACTIVE,
            CampaignStatus.PAUSED,
            CampaignStatus.COMPLETED,
            CampaignStatus.HALTED,
        )
        activated_forbidden = self.status in (
            CampaignStatus.DRAFT,
            CampaignStatus.VALIDATED,
            CampaignStatus.REJECTED,
        )
        if activated_required and self.activated_at is None:
            raise ValueError("status requires activated_at")
        if activated_forbidden and self.activated_at is not None:
            raise ValueError("status forbids activated_at")
        if (
            self.activated_at is not None
            and not self.created_at <= self.activated_at <= self.expires_at
        ):
            raise ValueError("activated_at outside lifecycle")
        return self


class CampaignState(ATSBaseModel):
    schema_version: Literal["1.0"]
    campaign_state_id: UUID
    campaign_id: UUID
    campaign_version: PositiveInt
    state_version: PositiveInt
    status: CampaignStatus
    trades_started: NonNegativeInt
    trades_completed: NonNegativeInt
    open_positions: NonNegativeInt
    capital_committed: NonNegativeDecimal
    realized_pnl: FiniteDecimal
    unrealized_pnl: FiniteDecimal
    maximum_drawdown_observed: PortfolioFraction
    consecutive_losses: NonNegativeInt
    last_trade_at: UTCDateTime | None
    cooldown_until: UTCDateTime | None
    stop_reason_codes: tuple[RegisteredCode, ...]
    as_of_time: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_state(self) -> CampaignState:
        if self.trades_completed > self.trades_started:
            raise ValueError("trades_completed must be <= trades_started")
        if self.open_positions > self.trades_started - self.trades_completed:
            raise ValueError("open_positions exceeds unfinished trades")
        if self.status is CampaignStatus.HALTED and not self.stop_reason_codes:
            raise ValueError("HALTED requires stop_reason_codes")
        ensure_unique(self.stop_reason_codes, "stop_reason_codes")
        return self


class OpportunityCandidate(ATSBaseModel):
    schema_version: Literal["1.0"]
    candidate_id: UUID
    candidate_version: PositiveInt
    instrument_id: InstrumentId
    market_context_id: UUID
    thesis_id: UUID
    thesis_version: PositiveInt
    distribution_id: UUID
    campaign_id: UUID
    campaign_version: PositiveInt
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt
    side: Side
    event_definition_id: UUID
    horizon_bars: PositiveInt
    target_outcome_code: RegisteredCode
    calibrated_probability: Probability
    expected_net_edge_r: FiniteFloat
    expected_reward_risk: PositiveDecimal
    entry_conditions: tuple[Predicate, ...]
    proposed_stop_price: PositiveDecimal
    proposed_target_price: PositiveDecimal
    evidence_refs: tuple[UUID, ...]
    status: CandidateStatus
    risk_decision_id: UUID | None
    advisory_id: UUID | None
    autonomy_token_id: UUID | None
    created_at: UTCDateTime
    expires_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_candidate(self) -> OpportunityCandidate:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be > created_at")
        ensure_unique(self.evidence_refs, "evidence_refs")
        if (
            self.status
            in (
                CandidateStatus.RISK_EVALUATED,
                CandidateStatus.ADVISED,
                CandidateStatus.AUTHORIZED,
                CandidateStatus.CONSUMED,
            )
            and self.risk_decision_id is None
        ):
            raise ValueError("status requires risk_decision_id")
        if (
            self.status
            in (CandidateStatus.ADVISED, CandidateStatus.AUTHORIZED, CandidateStatus.CONSUMED)
            and self.advisory_id is None
        ):
            raise ValueError("status requires advisory_id")
        if (
            self.status in (CandidateStatus.AUTHORIZED, CandidateStatus.CONSUMED)
            and self.autonomy_token_id is None
        ):
            raise ValueError("status requires autonomy_token_id")
        return self


class PositionThesis(ATSBaseModel):
    schema_version: Literal["1.0"]
    position_thesis_id: UUID
    position_thesis_version: PositiveInt
    position_id: UUID
    position_version: PositiveInt
    originating_candidate_id: UUID
    entry_thesis_id: UUID
    entry_thesis_version: PositiveInt
    current_thesis_id: UUID
    current_thesis_version: PositiveInt
    campaign_id: UUID
    campaign_version: PositiveInt
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    state: PositionThesisState
    current_distribution_id: UUID
    original_invalidation_conditions: tuple[Predicate, ...]
    maximum_favourable_excursion_r: FiniteFloat
    maximum_adverse_excursion_r: FiniteFloat
    recommended_action: PositionRecommendation
    reason_codes: tuple[RegisteredCode, ...]
    evidence_refs: tuple[UUID, ...]
    expires_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_thesis(self) -> PositionThesis:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        if (
            self.state in (PositionThesisState.HEALTHY, PositionThesisState.DEGRADING)
            and self.expires_at <= self.as_of_time
        ):
            raise ValueError("nonterminal thesis must expire after as_of_time")
        ensure_unique(self.evidence_refs, "evidence_refs")
        return self


class GovernanceContext(ATSBaseModel):
    schema_version: Literal["1.0"]
    governance_context_id: UUID
    action_subject_id: UUID
    action_kind: ActionKind
    risk_direction: RiskDirection
    candidate_id: UUID | None
    candidate_version: PositiveInt | None
    position_thesis_id: UUID | None
    position_thesis_version: PositiveInt | None
    system_state: SystemState
    system_state_version: PositiveInt
    policy_id: UUID
    policy_version: PositiveInt
    campaign_id: UUID | None
    campaign_version: PositiveInt | None
    campaign_state_id: UUID | None
    campaign_state_version: PositiveInt | None
    strategy_definition_id: UUID
    strategy_definition_version: PositiveInt
    portfolio_version: PositiveInt
    market_context_id: UUID
    risk_facts_id: UUID
    data_quality_state: DataQualityState
    data_freshness_ms: NonNegativeInt
    authority_scope: Literal["A2_PAPER"]
    resolved_constraints: EffectiveConstraintSet
    constraint_provenance: tuple[ConstraintProvenance, ...]
    source_refs: tuple[UUID, ...]
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_context(self) -> GovernanceContext:
        candidate = (self.candidate_id, self.candidate_version)
        position = (self.position_thesis_id, self.position_thesis_version)
        campaign = (
            self.campaign_id,
            self.campaign_version,
            self.campaign_state_id,
            self.campaign_state_version,
        )
        if sum(v is not None for v in candidate) not in (0, 2):
            raise ValueError("candidate reference must be all-or-none")
        if sum(v is not None for v in position) not in (0, 2):
            raise ValueError("position thesis reference must be all-or-none")
        if sum(v is not None for v in campaign) not in (0, 4):
            raise ValueError("campaign quartet must be all-or-none")
        fixed = {
            ActionKind.OPEN_POSITION: RiskDirection.INCREASE,
            ActionKind.INCREASE_POSITION: RiskDirection.INCREASE,
            ActionKind.REDUCE_POSITION: RiskDirection.REDUCE,
            ActionKind.CLOSE_POSITION: RiskDirection.REDUCE,
            ActionKind.EMERGENCY_FLATTEN: RiskDirection.REDUCE,
        }
        if self.action_kind in fixed and self.risk_direction is not fixed[self.action_kind]:
            raise ValueError("risk_direction conflicts with action_kind")
        if self.action_kind is ActionKind.OPEN_POSITION and self.candidate_id is None:
            raise ValueError("OPEN_POSITION requires candidate")
        if self.action_kind is ActionKind.INCREASE_POSITION and (
            self.candidate_id is None or self.position_thesis_id is None
        ):
            raise ValueError("INCREASE_POSITION requires candidate and position thesis")
        if (
            self.action_kind
            in (
                ActionKind.REDUCE_POSITION,
                ActionKind.CLOSE_POSITION,
                ActionKind.MODIFY_PROTECTIVE_EXIT,
            )
            and self.position_thesis_id is None
        ):
            raise ValueError("action requires position thesis")
        codes = tuple(item.constraint_code for item in self.constraint_provenance)
        if len(codes) != len(ConstraintCode) or set(codes) != set(ConstraintCode):
            raise ValueError("constraint_provenance must contain exactly all codes")
        if not self.source_refs:
            raise ValueError("source_refs must be non-empty")
        ensure_unique(self.source_refs, "source_refs")
        return self


GOVERNANCE_CONTRACTS = (
    TradingCampaign,
    CampaignState,
    OpportunityCandidate,
    PositionThesis,
    GovernanceContext,
)

__all__ = [contract.__name__ for contract in GOVERNANCE_CONTRACTS] + ["GOVERNANCE_CONTRACTS"]
