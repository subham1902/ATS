"""Closed, immutable M0.8 event registry for the Alpha version-one catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias

from ats.contracts.common import ATSBaseModel

from .models import (
    AutonomyGrantedPayload,
    CandidateCreatedPayload,
    EventType,
    ExitIntentCreatedPayload,
    FeaturesReadyPayload,
    ForecastReadyPayload,
    MarketSnapshotReadyPayload,
    OrderIntentCreatedPayload,
    PaperOrderAcceptedPayload,
    PaperOrderFilledPayload,
    PaperOrderPartiallyFilledPayload,
    PaperOrderRejectedPayload,
    PolicyActivatedPayload,
    PolicyDraftedPayload,
    PolicyValidatedPayload,
    PositionClosedPayload,
    PositionOpenedPayload,
    PositionUpdatedPayload,
    ReconciliationCompletedPayload,
    ReconciliationFailedPayload,
    ReconciliationStartedPayload,
    RiskEvaluatedPayload,
    SupervisorEvaluatedPayload,
    SystemHaltedPayload,
    TradeReviewReadyPayload,
)


@dataclass(frozen=True, slots=True)
class EventRegistryEntry:
    catalogue_sequence: int
    event_type: EventType
    event_version: int
    aggregate: str
    producer: str
    payload_model: type[ATSBaseModel]
    payload_fields: tuple[str, ...]
    idempotency: str
    transition: str


RegistryKey: TypeAlias = tuple[EventType, int]


def _entry(
    sequence: int,
    event_type: EventType,
    aggregate: str,
    producer: str,
    payload_model: type[ATSBaseModel],
    idempotency: str,
    transition: str,
) -> EventRegistryEntry:
    return EventRegistryEntry(
        catalogue_sequence=sequence,
        event_type=event_type,
        event_version=1,
        aggregate=aggregate,
        producer=producer,
        payload_model=payload_model,
        payload_fields=tuple(payload_model.model_fields),
        idempotency=idempotency,
        transition=transition,
    )


_ENTRIES = (
    _entry(
        1,
        EventType.MARKET_SNAPSHOT_READY,
        "instrument/timeframe",
        "market",
        MarketSnapshotReadyPayload,
        "unique snapshot_id",
        "bar accepted as durable evidence",
    ),
    _entry(
        2,
        EventType.FEATURES_READY,
        "feature bundle",
        "features",
        FeaturesReadyPayload,
        "unique(snapshot_id,feature_version)",
        "features persisted",
    ),
    _entry(
        3,
        EventType.FORECAST_READY,
        "forecast",
        "kronos-worker",
        ForecastReadyPayload,
        "unique(feature_bundle_id,model_version,horizon_bars,seed)",
        "forecast persisted",
    ),
    _entry(
        4,
        EventType.POLICY_DRAFTED,
        "policy family",
        "policy-compiler",
        PolicyDraftedPayload,
        "unique draft_id",
        "non-executable draft persisted",
    ),
    _entry(
        5,
        EventType.POLICY_VALIDATED,
        "policy family",
        "policy-service",
        PolicyValidatedPayload,
        "unique(policy_id,policy_version)",
        "validated immutable version appended",
    ),
    _entry(
        6,
        EventType.POLICY_ACTIVATED,
        "policy family",
        "policy-service",
        PolicyActivatedPayload,
        "one active version per policy family",
        "explicit active pointer changed transactionally",
    ),
    _entry(
        7,
        EventType.CANDIDATE_CREATED,
        "candidate",
        "decision-coordinator",
        CandidateCreatedPayload,
        "canonical candidate key",
        "candidate persisted",
    ),
    _entry(
        8,
        EventType.RISK_EVALUATED,
        "candidate",
        "risk",
        RiskEvaluatedPayload,
        "unique(candidate_id,risk_facts_id,policy_version)",
        "risk result persisted",
    ),
    _entry(
        9,
        EventType.SUPERVISOR_EVALUATED,
        "candidate",
        "supervisor",
        SupervisorEvaluatedPayload,
        "unique(packet_id,model_version)",
        "advisory persisted",
    ),
    _entry(
        10,
        EventType.AUTONOMY_GRANTED,
        "candidate",
        "autonomy-gate",
        AutonomyGrantedPayload,
        "unique candidate authorization",
        "single-use token issued",
    ),
    _entry(
        11,
        EventType.ORDER_INTENT_CREATED,
        "intent",
        "execution-gateway",
        OrderIntentCreatedPayload,
        "unique idempotency_key",
        "intent and outbox row committed atomically",
    ),
    _entry(
        12,
        EventType.PAPER_ORDER_ACCEPTED,
        "paper order",
        "paper-broker",
        PaperOrderAcceptedPayload,
        "unique intent_id",
        "paper order accepted",
    ),
    _entry(
        13,
        EventType.PAPER_ORDER_REJECTED,
        "paper order",
        "paper-broker",
        PaperOrderRejectedPayload,
        "unique intent terminal result",
        "paper order rejected",
    ),
    _entry(
        14,
        EventType.PAPER_ORDER_PARTIALLY_FILLED,
        "paper order",
        "paper-broker",
        PaperOrderPartiallyFilledPayload,
        "unique fill_id",
        "fill and order projection updated atomically",
    ),
    _entry(
        15,
        EventType.PAPER_ORDER_FILLED,
        "paper order",
        "paper-broker",
        PaperOrderFilledPayload,
        "unique fill_id + terminal guard",
        "order fully filled",
    ),
    _entry(
        16,
        EventType.POSITION_OPENED,
        "position",
        "portfolio-ledger",
        PositionOpenedPayload,
        "unique opening fill",
        "position projection created",
    ),
    _entry(
        17,
        EventType.POSITION_UPDATED,
        "position",
        "portfolio-ledger",
        PositionUpdatedPayload,
        "unique(position_id,position_version)",
        "position projection advanced",
    ),
    _entry(
        18,
        EventType.EXIT_INTENT_CREATED,
        "position",
        "position-monitor",
        ExitIntentCreatedPayload,
        "unique idempotency_key",
        "exit request committed",
    ),
    _entry(
        19,
        EventType.POSITION_CLOSED,
        "position",
        "portfolio-ledger",
        PositionClosedPayload,
        "unique closing fill",
        "position terminal state",
    ),
    _entry(
        20,
        EventType.RECONCILIATION_STARTED,
        "system",
        "reconciliation",
        ReconciliationStartedPayload,
        "unique active run per scope",
        "system enters RECONCILING",
    ),
    _entry(
        21,
        EventType.RECONCILIATION_COMPLETED,
        "system",
        "reconciliation",
        ReconciliationCompletedPayload,
        "unique reconciliation result",
        "system may enter READY",
    ),
    _entry(
        22,
        EventType.RECONCILIATION_FAILED,
        "system",
        "reconciliation",
        ReconciliationFailedPayload,
        "unique reconciliation result",
        "system remains/enters HALTED",
    ),
    _entry(
        23,
        EventType.SYSTEM_HALTED,
        "system",
        "kernel",
        SystemHaltedPayload,
        "unique halt transition version",
        "no new exposure permitted",
    ),
    _entry(
        24,
        EventType.TRADE_REVIEW_READY,
        "position",
        "trade-review",
        TradeReviewReadyPayload,
        "unique(position_id,reviewer_model_version)",
        "review evidence appended; no policy mutation",
    ),
)

EVENT_REGISTRY = MappingProxyType({(entry.event_type, 1): entry for entry in _ENTRIES})
EVENT_REGISTRY_ENTRIES = _ENTRIES

if len(EVENT_REGISTRY) != 24:
    raise RuntimeError("frozen event registry must contain exactly 24 unique keys")


__all__ = ["EVENT_REGISTRY", "EVENT_REGISTRY_ENTRIES", "EventRegistryEntry", "RegistryKey"]
