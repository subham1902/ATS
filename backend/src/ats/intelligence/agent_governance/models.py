"""Typed, tamper-evident contracts for the advisory agent capability boundary."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, Sha256


class AgentToolName(StrEnum):
    GET_MARKET_CONTEXT = "get_market_context"
    GET_LATEST_MARKET_SNAPSHOT = "get_latest_market_snapshot"
    GET_OPTION_WINDOW = "get_option_window"
    GET_POSITION_CONTEXT = "get_position_context"
    GET_PORTFOLIO_CONTEXT = "get_portfolio_context"
    GET_CURRENT_RISK_STATE = "get_current_risk_state"
    GET_CAMPAIGN_STATE = "get_campaign_state"
    GET_STRATEGY_DEFINITION = "get_strategy_definition"
    GET_RECENT_TRADES = "get_recent_trades"
    GET_PERFORMANCE_ATTRIBUTION = "get_performance_attribution"
    GET_HISTORICAL_EVIDENCE = "get_historical_evidence"
    GET_RECENT_ACTIVITY = "get_recent_activity"
    GET_EXPERIMENT_STATE = "get_experiment_state"


class RuntimeChangeCategory(StrEnum):
    ADVISORY_STATE = "ADVISORY_STATE"
    RESEARCH_STATE = "RESEARCH_STATE"
    BOUNDED_RUNTIME_CONFIG = "BOUNDED_RUNTIME_CONFIG"
    FINANCIAL_AUTHORITY = "FINANCIAL_AUTHORITY"


class RuntimeChangeType(StrEnum):
    UPDATE_RESEARCH_QUEUE = "UPDATE_RESEARCH_QUEUE"
    CREATE_HYPOTHESIS = "CREATE_HYPOTHESIS"
    SET_ANALYSIS_PRIORITY = "SET_ANALYSIS_PRIORITY"
    REQUEST_THESIS_RECOMPUTATION = "REQUEST_THESIS_RECOMPUTATION"
    PROPOSE_EXPERIMENT = "PROPOSE_EXPERIMENT"
    ADD_ANNOTATION = "ADD_ANNOTATION"
    SET_SAFE_MODE = "SET_SAFE_MODE"
    PAUSE_STRATEGY = "PAUSE_STRATEGY"
    REDUCE_ALLOCATION = "REDUCE_ALLOCATION"
    TIGHTEN_THRESHOLD = "TIGHTEN_THRESHOLD"
    REQUEST_POSITION_REVIEW = "REQUEST_POSITION_REVIEW"
    REQUEST_CANDIDATE_REEVALUATION = "REQUEST_CANDIDATE_REEVALUATION"
    SET_AGGRESSIVE_MODE = "SET_AGGRESSIVE_MODE"
    INCREASE_HARD_RISK = "INCREASE_HARD_RISK"
    PLACE_ORDER = "PLACE_ORDER"
    PROMOTE_STRATEGY = "PROMOTE_STRATEGY"


class RuntimeChangeOutcome(StrEnum):
    APPLY = "APPLY"
    REJECT = "REJECT"


class RuntimeChangeProposal(ATSBaseModel):
    schema_version: str = "1.0"
    proposal_id: UUID
    agent_id: NonEmptyStr
    session_id: UUID
    created_at: UTCDateTime
    as_of: UTCDateTime
    data_cutoff: UTCDateTime
    category: RuntimeChangeCategory
    proposal_type: RuntimeChangeType
    target: NonEmptyStr
    requested_change: dict[str, Any]
    current_value: dict[str, Any]
    proposed_value: dict[str, Any]
    reason: NonEmptyStr
    evidence_refs: tuple[UUID, ...]
    input_hash: Sha256
    valid_until: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_temporal_and_evidence_bounds(self) -> RuntimeChangeProposal:
        if self.data_cutoff > self.as_of or self.as_of > self.created_at:
            raise ValueError("proposal temporal ordering is invalid")
        if self.valid_until <= self.created_at:
            raise ValueError("valid_until must be after created_at")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("evidence_refs must be deduplicated")
        if not self.requested_change:
            raise ValueError("requested_change must not be empty")
        return self


class RuntimeChangeDecision(ATSBaseModel):
    decision_id: UUID
    proposal_id: UUID
    proposal_hash: Sha256
    outcome: RuntimeChangeOutcome
    reason_codes: tuple[NonEmptyStr, ...]
    evaluated_at: UTCDateTime
    applied_change: dict[str, Any] | None
    payload_hash: Sha256


class AgentToolResponse(ATSBaseModel):
    tool: AgentToolName
    as_of: UTCDateTime
    data_cutoff: UTCDateTime
    context_hash: Sha256
    evidence_refs: tuple[UUID, ...]
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_cutoff(self) -> AgentToolResponse:
        if self.data_cutoff > self.as_of:
            raise ValueError("data_cutoff must not exceed as_of")
        return self


class GovernedAgentOutput(ATSBaseModel):
    output_id: UUID
    agent_id: NonEmptyStr
    session_id: UUID
    as_of: UTCDateTime
    data_cutoff: UTCDateTime
    context_hash: Sha256
    generated_at: UTCDateTime
    valid_until: UTCDateTime
    evidence_refs: tuple[UUID, ...]
    content: NonEmptyStr

    @model_validator(mode="after")
    def validate_time_bounds(self) -> GovernedAgentOutput:
        if self.data_cutoff > self.as_of or self.as_of > self.generated_at:
            raise ValueError("agent output temporal ordering is invalid")
        if self.valid_until <= self.generated_at:
            raise ValueError("valid_until must be after generated_at")
        return self


class MaterialWakeKind(StrEnum):
    PRICE_SHOCK = "PRICE_SHOCK"
    IV_SHOCK = "IV_SHOCK"
    OI_SHIFT = "OI_SHIFT"
    REGIME_CHANGE = "REGIME_CHANGE"
    MODEL_DISAGREEMENT = "MODEL_DISAGREEMENT"
    POSITION_RISK_CHANGE = "POSITION_RISK_CHANGE"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    EXECUTION_ANOMALY = "EXECUTION_ANOMALY"
    STRATEGY_DEGRADATION = "STRATEGY_DEGRADATION"
    NEW_HIGH_QUALITY_OPPORTUNITY = "NEW_HIGH_QUALITY_OPPORTUNITY"


class MaterialWakeEvent(ATSBaseModel):
    event_id: UUID
    kind: MaterialWakeKind
    scope: NonEmptyStr
    occurred_at: UTCDateTime
    evidence_refs: tuple[UUID, ...]
    context_hash: Sha256


class RuntimeChangeAudit(ATSBaseModel):
    audit_id: UUID
    proposal_id: UUID
    decision_id: UUID
    actor_id: NonEmptyStr
    outcome: RuntimeChangeOutcome
    reason_codes: tuple[NonEmptyStr, ...]
    occurred_at: UTCDateTime
    proposal_hash: Sha256
    decision_hash: Sha256


__all__ = [
    "AgentToolName",
    "AgentToolResponse",
    "GovernedAgentOutput",
    "MaterialWakeEvent",
    "MaterialWakeKind",
    "RuntimeChangeAudit",
    "RuntimeChangeCategory",
    "RuntimeChangeDecision",
    "RuntimeChangeOutcome",
    "RuntimeChangeProposal",
    "RuntimeChangeType",
]
