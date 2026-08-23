"""Frozen A03 event payloads and strict event envelope.

The payload models contain only the exact fields in the M0.8 event catalogue.
The envelope validates its static registry binding and payload integrity without
publishing, persisting, dispatching, or allocating aggregate sequences.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    ValidationInfo,
    model_validator,
)

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.domain.types import (
    AdvisoryOutcome,
    AutonomyLevel,
    DataQualityState,
    ExitReason,
    ForecastStatus,
    InstrumentId,
    LossState,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PaperOrderType,
    PositiveDecimal,
    PositiveInt,
    QualityFlag,
    RiskOutcome,
    SchemaV1,
    SemVer,
    Sha256,
    Side,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.hashing import canonical_sha256
from ats.contracts.ids import OpaqueId


class EventType(ATSStringEnum):
    MARKET_SNAPSHOT_READY = "MARKET_SNAPSHOT_READY"
    FEATURES_READY = "FEATURES_READY"
    FORECAST_READY = "FORECAST_READY"
    POLICY_DRAFTED = "POLICY_DRAFTED"
    POLICY_VALIDATED = "POLICY_VALIDATED"
    POLICY_ACTIVATED = "POLICY_ACTIVATED"
    CANDIDATE_CREATED = "CANDIDATE_CREATED"
    RISK_EVALUATED = "RISK_EVALUATED"
    SUPERVISOR_EVALUATED = "SUPERVISOR_EVALUATED"
    AUTONOMY_GRANTED = "AUTONOMY_GRANTED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    PAPER_ORDER_ACCEPTED = "PAPER_ORDER_ACCEPTED"
    PAPER_ORDER_REJECTED = "PAPER_ORDER_REJECTED"
    PAPER_ORDER_PARTIALLY_FILLED = "PAPER_ORDER_PARTIALLY_FILLED"
    PAPER_ORDER_FILLED = "PAPER_ORDER_FILLED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_UPDATED = "POSITION_UPDATED"
    EXIT_INTENT_CREATED = "EXIT_INTENT_CREATED"
    POSITION_CLOSED = "POSITION_CLOSED"
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
    RECONCILIATION_COMPLETED = "RECONCILIATION_COMPLETED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    SYSTEM_HALTED = "SYSTEM_HALTED"
    TRADE_REVIEW_READY = "TRADE_REVIEW_READY"


def _require_nonzero_trace_id(value: str) -> str:
    if value == "0" * 32:
        raise ValueError("trace_id must not be all zeroes")
    return value


TraceId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{32}$"),
    AfterValidator(_require_nonzero_trace_id),
]
IssueCodes = tuple[NonEmptyStr, ...]
ReasonCodes = tuple[NonEmptyStr, ...]


class MarketSnapshotReadyPayload(ATSBaseModel):
    snapshot_id: OpaqueId
    instrument_id: InstrumentId
    timeframe: Literal["5m"]
    sequence: PositiveInt
    quality_state: DataQualityState
    payload_hash: Sha256


class FeaturesReadyPayload(ATSBaseModel):
    feature_bundle_id: OpaqueId
    snapshot_id: OpaqueId
    feature_version: SemVer
    quality_flags: tuple[QualityFlag, ...]
    input_hash: Sha256

    @model_validator(mode="after")
    def validate_flags(self) -> FeaturesReadyPayload:
        ensure_unique(self.quality_flags, "quality_flags")
        return self


class ForecastReadyPayload(ATSBaseModel):
    forecast_id: OpaqueId
    feature_bundle_id: OpaqueId
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    horizon_bars: PositiveInt
    status: ForecastStatus
    payload_hash: Sha256


class PolicyDraftedPayload(ATSBaseModel):
    draft_id: OpaqueId
    source_instruction_hash: Sha256
    requested_autonomy: AutonomyLevel
    executable: Literal[False]
    issue_codes: IssueCodes


class PolicyValidatedPayload(ATSBaseModel):
    policy_id: OpaqueId
    policy_version: PositiveInt
    validation_result: NonEmptyStr
    validation_report_hash: Sha256
    issue_codes: IssueCodes


class PolicyActivatedPayload(ATSBaseModel):
    policy_id: OpaqueId
    policy_version: PositiveInt
    activation_mode: Literal["A2_PAPER"]
    actor_subject: NonEmptyStr
    activated_at: UTCDateTime


class CandidateCreatedPayload(ATSBaseModel):
    candidate_id: OpaqueId
    snapshot_id: OpaqueId
    forecast_id: OpaqueId
    confidence_id: OpaqueId
    policy_id: OpaqueId
    policy_version: PositiveInt


class RiskEvaluatedPayload(ATSBaseModel):
    risk_decision_id: OpaqueId
    risk_facts_id: OpaqueId
    decision: RiskOutcome
    loss_state: LossState
    reason_codes: ReasonCodes

    @model_validator(mode="after")
    def validate_reasons(self) -> RiskEvaluatedPayload:
        if self.decision in (RiskOutcome.DENY, RiskOutcome.UNKNOWN) and not self.reason_codes:
            raise ValueError("DENY and UNKNOWN decisions require reason_codes")
        return self


class SupervisorEvaluatedPayload(ATSBaseModel):
    advisory_id: OpaqueId
    packet_id: OpaqueId
    recommendation: AdvisoryOutcome
    model_id: NonEmptyStr
    model_version: NonEmptyStr
    reason_codes: ReasonCodes


class AutonomyGrantedPayload(ATSBaseModel):
    token_id: OpaqueId
    scope: Literal["A2_PAPER"]
    policy_id: OpaqueId
    policy_version: PositiveInt
    risk_decision_id: OpaqueId
    advisory_id: OpaqueId
    expires_at: UTCDateTime
    nonce: NonEmptyStr


class OrderIntentCreatedPayload(ATSBaseModel):
    intent_id: OpaqueId
    instrument_id: InstrumentId
    side: Side
    quantity: PositiveDecimal
    order_type: PaperOrderType
    token_id: OpaqueId
    idempotency_key: NonEmptyStr


class PaperOrderAcceptedPayload(ATSBaseModel):
    paper_order_id: OpaqueId
    intent_id: OpaqueId
    status: Literal["ACCEPTED"]
    broker_model_version: NonEmptyStr
    accepted_at: UTCDateTime


class PaperOrderRejectedPayload(ATSBaseModel):
    paper_order_id: OpaqueId
    intent_id: OpaqueId
    status: Literal["REJECTED"]
    rejection_reason: NonEmptyStr
    updated_at: UTCDateTime


class PaperOrderPartiallyFilledPayload(ATSBaseModel):
    paper_order_id: OpaqueId
    fill_id: OpaqueId
    fill_quantity: PositiveDecimal
    cumulative_quantity: NonNegativeDecimal
    remaining_quantity: NonNegativeDecimal


class PaperOrderFilledPayload(ATSBaseModel):
    paper_order_id: OpaqueId
    fill_id: OpaqueId
    fill_quantity: PositiveDecimal
    cumulative_quantity: NonNegativeDecimal
    status: Literal["FILLED"]


class PositionOpenedPayload(ATSBaseModel):
    position_id: OpaqueId
    portfolio_id: OpaqueId
    instrument_id: InstrumentId
    opening_fill_id: OpaqueId
    position_version: PositiveInt


class PositionUpdatedPayload(ATSBaseModel):
    position_id: OpaqueId
    position_version: PositiveInt
    last_fill_id: OpaqueId
    net_quantity: FiniteDecimal
    realized_pnl: FiniteDecimal
    unrealized_pnl: FiniteDecimal


class ExitIntentCreatedPayload(ATSBaseModel):
    exit_intent_id: OpaqueId
    position_id: OpaqueId
    position_version: PositiveInt
    reason: ExitReason
    quantity: PositiveDecimal
    idempotency_key: NonEmptyStr


class PositionClosedPayload(ATSBaseModel):
    position_id: OpaqueId
    position_version: PositiveInt
    closing_fill_id: OpaqueId
    realized_pnl: FiniteDecimal
    closed_at: UTCDateTime


class ReconciliationStartedPayload(ATSBaseModel):
    reconciliation_id: OpaqueId
    scope: NonEmptyStr
    started_at: UTCDateTime
    prior_system_state: NonEmptyStr


class ReconciliationCompletedPayload(ATSBaseModel):
    reconciliation_id: OpaqueId
    checked_orders: NonNegativeInt
    checked_fills: NonNegativeInt
    checked_positions: NonNegativeInt
    differences: Literal[0]
    completed_at: UTCDateTime


class ReconciliationFailedPayload(ATSBaseModel):
    reconciliation_id: OpaqueId
    difference_count: PositiveInt
    reason_codes: Annotated[ReasonCodes, Field(min_length=1)]
    failed_at: UTCDateTime


class SystemHaltedPayload(ATSBaseModel):
    halt_id: OpaqueId
    reason_codes: Annotated[ReasonCodes, Field(min_length=1)]
    prior_state: NonEmptyStr
    halted_at: UTCDateTime
    manual_clear_required: bool


class TradeReviewReadyPayload(ATSBaseModel):
    review_id: OpaqueId
    position_id: OpaqueId
    policy_id: OpaqueId
    policy_version: PositiveInt
    reviewer_model_id: NonEmptyStr
    payload_hash: Sha256


EventPayload: TypeAlias = (
    MarketSnapshotReadyPayload
    | FeaturesReadyPayload
    | ForecastReadyPayload
    | PolicyDraftedPayload
    | PolicyValidatedPayload
    | PolicyActivatedPayload
    | CandidateCreatedPayload
    | RiskEvaluatedPayload
    | SupervisorEvaluatedPayload
    | AutonomyGrantedPayload
    | OrderIntentCreatedPayload
    | PaperOrderAcceptedPayload
    | PaperOrderRejectedPayload
    | PaperOrderPartiallyFilledPayload
    | PaperOrderFilledPayload
    | PositionOpenedPayload
    | PositionUpdatedPayload
    | ExitIntentCreatedPayload
    | PositionClosedPayload
    | ReconciliationStartedPayload
    | ReconciliationCompletedPayload
    | ReconciliationFailedPayload
    | SystemHaltedPayload
    | TradeReviewReadyPayload
)


def _require_typed_payload(value: object, info: ValidationInfo) -> object:
    if info.mode == "python" and isinstance(value, Mapping):
        raise ValueError("payload must be an instantiated registered payload model")
    return value


TypedPayload = Annotated[EventPayload, BeforeValidator(_require_typed_payload)]


class EventEnvelope(ATSBaseModel):
    event_id: OpaqueId
    event_type: EventType
    event_version: PositiveInt
    aggregate_id: OpaqueId
    causation_id: OpaqueId | None = None
    correlation_id: OpaqueId
    sequence: PositiveInt
    occurred_at: UTCDateTime
    recorded_at: UTCDateTime
    producer: NonEmptyStr
    schema_version: SchemaV1 = "1.0"
    payload: TypedPayload
    payload_hash: Sha256
    trace_id: TraceId

    @model_validator(mode="after")
    def validate_envelope(self) -> EventEnvelope:
        from .registry import EVENT_REGISTRY

        if self.recorded_at < self.occurred_at:
            raise ValueError("recorded_at must be >= occurred_at")
        entry = EVENT_REGISTRY.get((self.event_type, self.event_version))
        if entry is None:
            raise ValueError("unknown event_type/event_version pair")
        if type(self.payload) is not entry.payload_model:
            raise ValueError("event_type/event_version does not match payload model")
        if self.producer != entry.producer:
            raise ValueError("producer does not match registered event producer")
        if self.payload_hash != canonical_sha256(self.payload):
            raise ValueError("payload_hash does not match canonical typed payload")
        return self


EVENT_PAYLOAD_MODELS = (
    MarketSnapshotReadyPayload,
    FeaturesReadyPayload,
    ForecastReadyPayload,
    PolicyDraftedPayload,
    PolicyValidatedPayload,
    PolicyActivatedPayload,
    CandidateCreatedPayload,
    RiskEvaluatedPayload,
    SupervisorEvaluatedPayload,
    AutonomyGrantedPayload,
    OrderIntentCreatedPayload,
    PaperOrderAcceptedPayload,
    PaperOrderRejectedPayload,
    PaperOrderPartiallyFilledPayload,
    PaperOrderFilledPayload,
    PositionOpenedPayload,
    PositionUpdatedPayload,
    ExitIntentCreatedPayload,
    PositionClosedPayload,
    ReconciliationStartedPayload,
    ReconciliationCompletedPayload,
    ReconciliationFailedPayload,
    SystemHaltedPayload,
    TradeReviewReadyPayload,
)


__all__ = [
    "EVENT_PAYLOAD_MODELS",
    "EventEnvelope",
    "EventPayload",
    "EventType",
    "TraceId",
] + [model.__name__ for model in EVENT_PAYLOAD_MODELS]
