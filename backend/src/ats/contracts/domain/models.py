"""The 18 frozen A02 top-level domain contracts.

These immutable models contain data and intrinsic validation only. They perform
no acquisition, calculation, authorization, execution, persistence, or lookup.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, Probability, UTCDateTime
from ats.contracts.ids import OpaqueId

from .types import (
    AdvisoryOutcome,
    AuditResult,
    AutonomyLevel,
    BaselineResult,
    CooldownRule,
    DataQualityState,
    DataRequirement,
    EligibilityStatus,
    ExitReason,
    ForecastStatus,
    InstrumentId,
    JsonValue,
    LossState,
    LossStatePolicy,
    MoneyOrPortfolioFraction,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PaperOrderStatus,
    PaperOrderType,
    PolicyChangeProposal,
    PolicyStatus,
    PortfolioConstraints,
    PortfolioFraction,
    PositionStatus,
    PositiveDecimal,
    PositiveInt,
    Predicate,
    ProbabilityInterval,
    QualityFlag,
    RiskOutcome,
    SchemaV1,
    SemVer,
    SessionState,
    Sha256,
    Side,
    SizingRules,
    StopRule,
    TargetRule,
    TimeExitRule,
    TrailingRule,
    UncertaintyEvidence,
    UnitIntervalFloat,
    ValidationIssue,
    contains_executable_marker,
    ensure_non_empty_mapping_keys,
    ensure_unique,
)


class MarketSnapshot(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    snapshot_id: OpaqueId
    instrument_id: InstrumentId
    exchange: Literal["NSE"]
    segment: Literal["CASH"]
    timeframe: Literal["5m"]
    bar_timestamp: UTCDateTime
    received_at: UTCDateTime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    sequence: PositiveInt
    quality_state: DataQualityState
    quality_flags: tuple[QualityFlag, ...]
    source: NonEmptyStr
    source_version: NonEmptyStr
    session_state: SessionState
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_snapshot(self) -> MarketSnapshot:
        if (
            self.bar_timestamp.minute % 5
            or self.bar_timestamp.second
            or self.bar_timestamp.microsecond
        ):
            raise ValueError("bar_timestamp must align to a 5-minute close")
        if self.received_at < self.bar_timestamp:
            raise ValueError("received_at must be >= bar_timestamp")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low/high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low/high")
        ensure_unique(self.quality_flags, "quality_flags")
        return self


class FeatureBundle(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    feature_bundle_id: OpaqueId
    snapshot_id: OpaqueId
    feature_version: SemVer
    features: dict[str, FiniteFloat]
    quality_flags: tuple[QualityFlag, ...]
    computed_at: UTCDateTime
    input_hash: Sha256

    @model_validator(mode="after")
    def validate_features(self) -> FeatureBundle:
        ensure_non_empty_mapping_keys(self.features, "features")
        ensure_unique(self.quality_flags, "quality_flags")
        return self


class ForecastBundle(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    forecast_id: OpaqueId
    feature_bundle_id: OpaqueId
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    checkpoint_hash: Sha256
    data_version: NonEmptyStr
    horizon_bars: PositiveInt
    event_definition_id: NonEmptyStr
    raw_evidence: dict[str, JsonValue]
    forecast_paths: tuple[tuple[FiniteFloat, ...], ...] | None
    raw_probability: Probability | None
    calibrated_probability: Probability | None
    calibrator_version: NonEmptyStr | None
    uncertainty: UncertaintyEvidence
    baseline_results: tuple[BaselineResult, ...]
    seed: int
    status: ForecastStatus
    started_at: UTCDateTime
    completed_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_forecast(self) -> ForecastBundle:
        ensure_non_empty_mapping_keys(self.raw_evidence, "raw_evidence")
        if contains_executable_marker(self.raw_evidence):
            raise ValueError("raw_evidence contains an executable marker")
        if self.forecast_paths is not None and any(
            len(path) != self.horizon_bars for path in self.forecast_paths
        ):
            raise ValueError("every forecast path must match horizon_bars")
        if self.calibrated_probability is not None and self.calibrator_version is None:
            raise ValueError("calibrator_version is required for calibrated_probability")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must be >= started_at")
        return self


class ConfidenceEvidence(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    confidence_id: OpaqueId
    forecast_id: OpaqueId
    event_definition_id: NonEmptyStr
    horizon_bars: PositiveInt
    raw_probability: Probability
    calibrated_probability: Probability
    calibrator_version: NonEmptyStr
    support_count: NonNegativeInt
    reliability_bin: NonEmptyStr
    brier_score: UnitIntervalFloat | None
    confidence_interval: ProbabilityInterval | None
    regime_label: NonEmptyStr
    regime_familiarity: UnitIntervalFloat
    data_quality_state: DataQualityState
    ensemble_agreement: UnitIntervalFloat | None
    baseline_agreement: UnitIntervalFloat | None
    eligibility_status: EligibilityStatus
    reason_codes: tuple[NonEmptyStr, ...]
    computed_at: UTCDateTime


class StrategyPolicyDraft(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    draft_id: OpaqueId
    source_instruction_hash: Sha256
    compiler_model_id: NonEmptyStr
    compiler_model_version: NonEmptyStr
    requested_autonomy: AutonomyLevel
    proposed_policy: dict[str, JsonValue]
    ambiguities: tuple[ValidationIssue, ...]
    unsafe_requests: tuple[ValidationIssue, ...]
    executable: Literal[False]
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_proposal(self) -> StrategyPolicyDraft:
        ensure_non_empty_mapping_keys(self.proposed_policy, "proposed_policy")
        if contains_executable_marker(self.proposed_policy):
            raise ValueError("proposed_policy contains an executable marker")
        return self


class StrategyPolicy(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    policy_id: OpaqueId
    policy_version: PositiveInt
    owner_subject: NonEmptyStr
    lifecycle_status: PolicyStatus
    autonomy_level: AutonomyLevel
    universe: tuple[InstrumentId, ...]
    timeframe: Literal["5m"]
    data_requirements: tuple[DataRequirement, ...]
    event_definition_id: NonEmptyStr
    forecast_horizon_bars: PositiveInt
    confidence_threshold: Probability
    minimum_calibration_support: PositiveInt
    entry_predicates: tuple[Predicate, ...]
    sizing_rules: SizingRules
    maximum_loss: MoneyOrPortfolioFraction
    minimum_reward_risk: PositiveDecimal
    stop_rules: tuple[StopRule, ...]
    target_rules: tuple[TargetRule, ...]
    trailing_rules: tuple[TrailingRule, ...]
    time_exit: TimeExitRule | None
    portfolio_constraints: PortfolioConstraints
    daily_loss_limit: PositiveDecimal
    drawdown_limit: PortfolioFraction
    after_loss_state_machine: LossStatePolicy
    cooldown_rule: CooldownRule
    valid_from: UTCDateTime
    valid_until: UTCDateTime
    compatible_model_versions: tuple[NonEmptyStr, ...]
    compatible_calibrator_versions: tuple[NonEmptyStr, ...]
    created_at: UTCDateTime
    activated_at: UTCDateTime | None
    source_instruction_hash: Sha256
    validation_report_hash: Sha256
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_policy(self) -> StrategyPolicy:
        if not self.universe:
            raise ValueError("universe must be non-empty")
        ensure_unique(self.universe, "universe")
        if not self.stop_rules or not any(rule.hard_stop for rule in self.stop_rules):
            raise ValueError("at least one hard stop is required")
        if not self.target_rules and self.time_exit is None:
            raise ValueError("a target rule or time exit is required")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be > valid_from")
        if self.lifecycle_status is PolicyStatus.ACTIVE and self.activated_at is None:
            raise ValueError("ACTIVE policy requires activated_at")
        if self.lifecycle_status is not PolicyStatus.ACTIVE and self.activated_at is not None:
            raise ValueError("activated_at is only valid for ACTIVE policy")
        if not self.compatible_model_versions or not self.compatible_calibrator_versions:
            raise ValueError("compatible version allowlists must be non-empty")
        ensure_unique(self.compatible_model_versions, "compatible_model_versions")
        ensure_unique(self.compatible_calibrator_versions, "compatible_calibrator_versions")
        return self


class RiskFacts(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    risk_facts_id: OpaqueId
    snapshot_sequence: PositiveInt
    portfolio_version: PositiveInt
    policy_id: OpaqueId
    policy_version: PositiveInt
    data_quality_state: DataQualityState
    price_age_ms: NonNegativeInt
    gross_exposure: NonNegativeDecimal
    net_exposure: FiniteDecimal
    open_position_count: NonNegativeInt
    available_cash: FiniteDecimal
    realized_pnl_today: FiniteDecimal
    unrealized_pnl: FiniteDecimal
    drawdown_fraction: PortfolioFraction
    consecutive_losses: NonNegativeInt
    loss_state: LossState
    liquidity_measure: FiniteDecimal | None
    proposed_maximum_loss: PositiveDecimal
    expected_reward: FiniteDecimal
    measured_at: UTCDateTime
    payload_hash: Sha256


class RiskDecision(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    risk_decision_id: OpaqueId
    decision: RiskOutcome
    policy_id: OpaqueId
    policy_version: PositiveInt
    snapshot_sequence: PositiveInt
    risk_facts_id: OpaqueId
    applicable_rule_ids: tuple[NonEmptyStr, ...]
    measured_values: dict[str, FiniteDecimal]
    limits: dict[str, FiniteDecimal]
    loss_state: LossState
    reason_codes: tuple[NonEmptyStr, ...]
    decided_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_reasons(self) -> RiskDecision:
        if self.decision in (RiskOutcome.DENY, RiskOutcome.UNKNOWN) and not self.reason_codes:
            raise ValueError("DENY and UNKNOWN decisions require reason_codes")
        ensure_non_empty_mapping_keys(self.measured_values, "measured_values")
        ensure_non_empty_mapping_keys(self.limits, "limits")
        return self


class DecisionPacket(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    packet_id: OpaqueId
    candidate_id: OpaqueId
    snapshot_id: OpaqueId
    forecast_id: OpaqueId
    confidence_id: OpaqueId
    policy_id: OpaqueId
    policy_version: PositiveInt
    risk_decision_id: OpaqueId
    bounded_evidence: dict[str, JsonValue]
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_evidence(self) -> DecisionPacket:
        ensure_non_empty_mapping_keys(self.bounded_evidence, "bounded_evidence")
        if contains_executable_marker(self.bounded_evidence):
            raise ValueError("bounded_evidence contains an executable marker")
        return self


class SupervisorAdvisory(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    advisory_id: OpaqueId
    packet_id: OpaqueId
    recommendation: AdvisoryOutcome
    evidence_refs: tuple[OpaqueId, ...]
    reason_codes: tuple[NonEmptyStr, ...]
    uncertainty_flags: tuple[NonEmptyStr, ...]
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    latency_ms: NonNegativeInt
    created_at: UTCDateTime
    payload_hash: Sha256


class AutonomyToken(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    token_id: OpaqueId
    scope: Literal["A2_PAPER"]
    candidate_id: OpaqueId
    policy_id: OpaqueId
    policy_version: PositiveInt
    risk_decision_id: OpaqueId
    advisory_id: OpaqueId
    system_state_version: PositiveInt
    issued_at: UTCDateTime
    expires_at: UTCDateTime
    nonce: NonEmptyStr
    consumed_at: UTCDateTime | None
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_lifetime(self) -> AutonomyToken:
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be > issued_at")
        if self.consumed_at is not None and self.consumed_at < self.issued_at:
            raise ValueError("consumed_at must be >= issued_at")
        return self


class OrderIntent(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    intent_id: OpaqueId
    instrument_id: InstrumentId
    side: Side
    quantity: PositiveDecimal
    order_type: PaperOrderType
    entry_conditions: tuple[Predicate, ...]
    limit_price: PositiveDecimal | None
    stop_price: PositiveDecimal | None
    target_price: PositiveDecimal
    maximum_permitted_loss: PositiveDecimal
    expected_reward: PositiveDecimal
    policy_id: OpaqueId
    policy_version: PositiveInt
    forecast_id: OpaqueId
    risk_decision_id: OpaqueId
    supervisor_advisory_id: OpaqueId
    autonomy_token_id: OpaqueId
    idempotency_key: NonEmptyStr
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_order_prices(self) -> OrderIntent:
        if self.order_type in (PaperOrderType.LIMIT, PaperOrderType.STOP_LIMIT):
            if self.limit_price is None:
                raise ValueError("LIMIT and STOP_LIMIT require limit_price")
        if self.order_type is PaperOrderType.STOP_LIMIT and self.stop_price is None:
            raise ValueError("STOP_LIMIT requires stop_price")
        return self


class PaperOrder(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    paper_order_id: OpaqueId
    intent_id: OpaqueId
    status: PaperOrderStatus
    instrument_id: InstrumentId
    side: Side
    quantity: PositiveDecimal
    order_type: PaperOrderType
    limit_price: PositiveDecimal | None
    stop_price: PositiveDecimal | None
    filled_quantity: NonNegativeDecimal
    average_fill_price: PositiveDecimal | None
    rejection_reason: NonEmptyStr | None
    broker_model_version: NonEmptyStr
    accepted_at: UTCDateTime
    updated_at: UTCDateTime
    idempotency_key: NonEmptyStr
    version: PositiveInt

    @model_validator(mode="after")
    def validate_paper_order(self) -> PaperOrder:
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity must be <= quantity")
        if self.filled_quantity > Decimal(0) and self.average_fill_price is None:
            raise ValueError("average_fill_price is required for a fill")
        if self.status is PaperOrderStatus.REJECTED and self.rejection_reason is None:
            raise ValueError("REJECTED order requires rejection_reason")
        if self.updated_at < self.accepted_at:
            raise ValueError("updated_at must be >= accepted_at")
        return self


class Fill(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    fill_id: OpaqueId
    paper_order_id: OpaqueId
    instrument_id: InstrumentId
    side: Side
    quantity: PositiveDecimal
    price: PositiveDecimal
    fees: NonNegativeDecimal
    taxes: NonNegativeDecimal
    slippage: NonNegativeDecimal
    cost_model_version: NonEmptyStr
    filled_at: UTCDateTime
    idempotency_key: NonEmptyStr
    payload_hash: Sha256


class Position(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    position_id: OpaqueId
    portfolio_id: OpaqueId
    instrument_id: InstrumentId
    net_quantity: FiniteDecimal
    average_entry_price: PositiveDecimal
    mark_price: PositiveDecimal
    realized_pnl: FiniteDecimal
    unrealized_pnl: FiniteDecimal
    cash_effect: FiniteDecimal
    policy_id: OpaqueId
    policy_version: PositiveInt
    opened_at: UTCDateTime
    updated_at: UTCDateTime
    closed_at: UTCDateTime | None
    status: PositionStatus
    version: PositiveInt
    last_fill_id: OpaqueId
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Position:
        if self.updated_at < self.opened_at:
            raise ValueError("updated_at must be >= opened_at")
        if self.closed_at is not None and self.closed_at < self.updated_at:
            raise ValueError("closed_at must be >= updated_at")
        if self.status is PositionStatus.CLOSED and self.closed_at is None:
            raise ValueError("CLOSED position requires closed_at")
        if self.status is not PositionStatus.CLOSED and self.closed_at is not None:
            raise ValueError("closed_at is only valid for CLOSED position")
        return self


class ExitIntent(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    exit_intent_id: OpaqueId
    position_id: OpaqueId
    position_version: PositiveInt
    reason: ExitReason
    quantity: PositiveDecimal
    order_type: PaperOrderType
    limit_price: PositiveDecimal | None
    stop_price: PositiveDecimal | None
    risk_decision_id: OpaqueId
    autonomy_token_id: OpaqueId
    idempotency_key: NonEmptyStr
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_order_prices(self) -> ExitIntent:
        if self.order_type in (PaperOrderType.LIMIT, PaperOrderType.STOP_LIMIT):
            if self.limit_price is None:
                raise ValueError("LIMIT and STOP_LIMIT require limit_price")
        if self.order_type is PaperOrderType.STOP_LIMIT and self.stop_price is None:
            raise ValueError("STOP_LIMIT requires stop_price")
        return self


class TradeReview(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    review_id: OpaqueId
    position_id: OpaqueId
    policy_id: OpaqueId
    policy_version: PositiveInt
    forecast_id: OpaqueId
    confidence_id: OpaqueId
    outcome_metrics: dict[str, FiniteFloat]
    attribution: dict[str, JsonValue]
    lessons: tuple[NonEmptyStr, ...]
    policy_change_proposals: tuple[PolicyChangeProposal, ...]
    reviewer_model_id: NonEmptyStr
    reviewer_model_version: NonEmptyStr
    created_at: UTCDateTime
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_review(self) -> TradeReview:
        ensure_non_empty_mapping_keys(self.outcome_metrics, "outcome_metrics")
        ensure_non_empty_mapping_keys(self.attribution, "attribution")
        if contains_executable_marker(self.attribution):
            raise ValueError("attribution contains an executable marker")
        return self


class AuditEvent(ATSBaseModel):
    schema_version: SchemaV1 = "1.0"
    audit_event_id: OpaqueId
    event_id: OpaqueId
    actor_type: NonEmptyStr
    actor_id: NonEmptyStr
    action: NonEmptyStr
    object_type: NonEmptyStr
    object_id: NonEmptyStr
    decision_refs: tuple[OpaqueId, ...]
    before_hash: Sha256 | None
    after_hash: Sha256 | None
    result: AuditResult
    reason_codes: tuple[NonEmptyStr, ...]
    occurred_at: UTCDateTime
    trace_id: OpaqueId
    record_hash: Sha256


DOMAIN_CONTRACTS = (
    MarketSnapshot,
    FeatureBundle,
    ForecastBundle,
    ConfidenceEvidence,
    StrategyPolicyDraft,
    StrategyPolicy,
    RiskFacts,
    RiskDecision,
    DecisionPacket,
    SupervisorAdvisory,
    AutonomyToken,
    OrderIntent,
    PaperOrder,
    Fill,
    Position,
    ExitIntent,
    TradeReview,
    AuditEvent,
)

__all__ = [contract.__name__ for contract in DOMAIN_CONTRACTS] + ["DOMAIN_CONTRACTS"]
