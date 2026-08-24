"""Explicit, immutable A05 request, response, and read-stream models."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.models import (
    AutonomyToken,
    RiskDecision,
    StrategyPolicy,
    SupervisorAdvisory,
)
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    AutonomyLevel,
    InstrumentId,
    JsonValue,
    LossState,
    PolicyStatus,
    RiskOutcome,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.governance.models import GovernanceContext, OpportunityCandidate, TradingCampaign
from ats.contracts.governance.types import (
    CampaignStatus,
    CandidateStatus,
    RiskDirection,
    StrategyExecutionMode,
    SystemState,
)
from ats.kernel.types import GateCode, KernelOutcome


class ReadinessState(ATSStringEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class HealthState(ATSStringEnum):
    LIVE = "LIVE"
    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class TokenViewState(ATSStringEnum):
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class ErrorDetail(ATSBaseModel):
    field: str | None
    issue: str


class ErrorEnvelope(ATSBaseModel):
    code: str
    message: str
    correlation_id: str
    details: tuple[ErrorDetail, ...]


class HealthReadModel(ATSBaseModel):
    status: HealthState
    ready: bool
    reason_codes: tuple[str, ...]


class SystemReadModel(ATSBaseModel):
    system_state: SystemState
    system_state_version: int
    readiness: ReadinessState
    degradation_indicators: tuple[str, ...]
    loss_state: LossState
    active_policy_id: UUID | None
    active_policy_version: int | None
    active_campaign_id: UUID | None
    active_campaign_version: int | None
    authority_mode: Literal["A2_PAPER"]
    reconciliation_active: bool
    halted: bool
    last_state_at: UTCDateTime
    last_event_at: UTCDateTime | None


class PolicyReadModel(ATSBaseModel):
    policy_id: UUID
    policy_version: int
    owner_subject: str
    lifecycle_status: PolicyStatus
    autonomy_level: AutonomyLevel
    universe: tuple[InstrumentId, ...]
    timeframe: Literal["5m"]
    event_definition_id: str
    forecast_horizon_bars: int
    confidence_threshold: Decimal
    minimum_calibration_support: int
    minimum_reward_risk: Decimal
    valid_from: UTCDateTime
    valid_until: UTCDateTime
    activated_at: UTCDateTime | None

    @classmethod
    def from_contract(cls, policy: StrategyPolicy) -> PolicyReadModel:
        return cls(
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            owner_subject=policy.owner_subject,
            lifecycle_status=policy.lifecycle_status,
            autonomy_level=policy.autonomy_level,
            universe=policy.universe,
            timeframe=policy.timeframe,
            event_definition_id=policy.event_definition_id,
            forecast_horizon_bars=policy.forecast_horizon_bars,
            confidence_threshold=policy.confidence_threshold,
            minimum_calibration_support=policy.minimum_calibration_support,
            minimum_reward_risk=policy.minimum_reward_risk,
            valid_from=policy.valid_from,
            valid_until=policy.valid_until,
            activated_at=policy.activated_at,
        )


class PolicyValidationRequest(ATSBaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=False,
        validate_default=True,
        allow_inf_nan=False,
    )

    policy: dict[str, JsonValue]
    evaluation_time: UTCDateTime
    timeframe: str
    event_definition_id: str
    model_version: str
    calibrator_version: str


class PolicyValidationReadModel(ATSBaseModel):
    outcome: KernelOutcome
    reason_codes: tuple[GateCode, ...]


class CampaignReadModel(ATSBaseModel):
    campaign_id: UUID
    campaign_version: int
    name: str
    scope: Literal["A2_PAPER"]
    policy_id: UUID
    policy_version: int
    status: CampaignStatus
    strategy_execution_mode: StrategyExecutionMode
    instrument_universe: tuple[InstrumentId, ...]
    allowed_timeframes: tuple[str, ...]
    max_trades: int
    max_concurrent_positions: int
    capital_budget: Decimal
    start_at: UTCDateTime
    expires_at: UTCDateTime
    activated_at: UTCDateTime | None

    @classmethod
    def from_contract(cls, campaign: TradingCampaign) -> CampaignReadModel:
        return cls(
            campaign_id=campaign.campaign_id,
            campaign_version=campaign.campaign_version,
            name=campaign.name,
            scope=campaign.scope,
            policy_id=campaign.policy_id,
            policy_version=campaign.policy_version,
            status=campaign.status,
            strategy_execution_mode=campaign.strategy_execution_mode,
            instrument_universe=campaign.instrument_universe,
            allowed_timeframes=campaign.allowed_timeframes,
            max_trades=campaign.max_trades,
            max_concurrent_positions=campaign.max_concurrent_positions,
            capital_budget=campaign.capital_budget,
            start_at=campaign.start_at,
            expires_at=campaign.expires_at,
            activated_at=campaign.activated_at,
        )


class CandidateReadModel(ATSBaseModel):
    candidate_id: UUID
    candidate_version: int
    instrument_id: InstrumentId
    market_context_id: UUID
    thesis_id: UUID
    thesis_version: int
    distribution_id: UUID
    campaign_id: UUID
    campaign_version: int
    strategy_definition_id: UUID
    strategy_definition_version: int
    calibrated_probability: Decimal
    expected_net_edge_r: float
    expected_reward_risk: Decimal
    status: CandidateStatus
    risk_decision_id: UUID | None
    advisory_id: UUID | None
    autonomy_token_id: UUID | None
    created_at: UTCDateTime
    expires_at: UTCDateTime

    @classmethod
    def from_contract(cls, candidate: OpportunityCandidate) -> CandidateReadModel:
        fields = cls.model_fields
        return cls(**{name: getattr(candidate, name) for name in fields})


class GovernanceContextReadModel(ATSBaseModel):
    governance_context_id: UUID
    action_subject_id: UUID
    action_kind: str
    risk_direction: RiskDirection
    candidate_id: UUID | None
    candidate_version: int | None
    system_state: SystemState
    system_state_version: int
    policy_id: UUID
    policy_version: int
    campaign_id: UUID | None
    campaign_version: int | None
    strategy_definition_id: UUID
    strategy_definition_version: int
    portfolio_version: int
    market_context_id: UUID
    risk_facts_id: UUID
    data_quality_state: str
    data_freshness_ms: int
    authority_scope: Literal["A2_PAPER"]
    source_refs: tuple[UUID, ...]
    created_at: UTCDateTime

    @classmethod
    def from_contract(cls, context: GovernanceContext) -> GovernanceContextReadModel:
        return cls(**{name: getattr(context, name) for name in cls.model_fields})


class RiskDecisionReadModel(ATSBaseModel):
    risk_decision_id: UUID
    decision: RiskOutcome
    policy_id: UUID
    policy_version: int
    snapshot_sequence: int
    risk_facts_id: UUID
    applicable_rule_ids: tuple[str, ...]
    measured_values: dict[str, Decimal]
    limits: dict[str, Decimal]
    loss_state: LossState
    reason_codes: tuple[str, ...]
    decided_at: UTCDateTime

    @classmethod
    def from_contract(cls, decision: RiskDecision) -> RiskDecisionReadModel:
        return cls(**{name: getattr(decision, name) for name in cls.model_fields})


class AdvisoryReadModel(ATSBaseModel):
    advisory_id: UUID
    packet_id: UUID
    recommendation: AdvisoryOutcome
    evidence_refs: tuple[UUID, ...]
    reason_codes: tuple[str, ...]
    uncertainty_flags: tuple[str, ...]
    model_id: str
    model_version: str
    latency_ms: int
    created_at: UTCDateTime

    @classmethod
    def from_contract(cls, advisory: SupervisorAdvisory) -> AdvisoryReadModel:
        return cls(**{name: getattr(advisory, name) for name in cls.model_fields})


class AutonomyTokenReadModel(ATSBaseModel):
    token_id: UUID
    scope: Literal["A2_PAPER"]
    candidate_id: UUID
    policy_id: UUID
    policy_version: int
    risk_decision_id: UUID
    advisory_id: UUID
    system_state_version: int
    issued_at: UTCDateTime
    expires_at: UTCDateTime
    consumed_at: UTCDateTime | None
    state: TokenViewState

    @classmethod
    def from_contract(
        cls,
        token: AutonomyToken,
        *,
        evaluation_time: UTCDateTime,
        revoked: bool = False,
        valid: bool = True,
    ) -> AutonomyTokenReadModel:
        if not valid:
            state = TokenViewState.INVALID
        elif revoked:
            state = TokenViewState.REVOKED
        elif token.consumed_at is not None:
            state = TokenViewState.CONSUMED
        elif evaluation_time >= token.expires_at:
            state = TokenViewState.EXPIRED
        else:
            state = TokenViewState.ISSUED
        return cls(
            token_id=token.token_id,
            scope=token.scope,
            candidate_id=token.candidate_id,
            policy_id=token.policy_id,
            policy_version=token.policy_version,
            risk_decision_id=token.risk_decision_id,
            advisory_id=token.advisory_id,
            system_state_version=token.system_state_version,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
            consumed_at=token.consumed_at,
            state=state,
        )


class ActivityReadModel(ATSBaseModel):
    activity_id: UUID
    event_kind: str
    occurred_at: UTCDateTime
    correlation_id: UUID
    trace_id: str | None
    aggregate_id: UUID | None
    aggregate_version: int | None
    summary: str


class ActivityPage(ATSBaseModel):
    items: tuple[ActivityReadModel, ...]
    replay_supported: Literal[False] = False


class StreamEvent(ATSBaseModel):
    stream_event_id: UUID
    event_kind: str
    occurred_at: UTCDateTime
    correlation_id: UUID
    payload: dict[str, JsonValue]


__all__ = [name for name in globals() if not name.startswith("_")]
