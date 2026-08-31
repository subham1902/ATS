"""Durable, typed, tamper-evident A2 session evidence mirror.

This adapter is intentionally authority-neutral: it records decisions made by
existing components and never creates candidates, orders, or risk decisions.
The local JSONL mirror is append-only and is suitable for recovery/export when
the operational database is unavailable.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from ats.contracts.common import ATSBaseModel, FiniteDecimal, SchemaVersion, UTCDateTime
from ats.contracts.hashing import canonical_sha256


class EvidenceEventType(StrEnum):
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_PHASE_CHANGED = "SESSION_PHASE_CHANGED"
    SESSION_ENTRY_CUTOFF = "SESSION_ENTRY_CUTOFF"
    SESSION_FLATTEN_WINDOW = "SESSION_FLATTEN_WINDOW"
    SESSION_CLOSED = "SESSION_CLOSED"
    SYSTEM_STATE_CHANGED = "SYSTEM_STATE_CHANGED"
    TRADING_MODE_REQUESTED = "TRADING_MODE_REQUESTED"
    TRADING_MODE_EFFECTIVE_CHANGED = "TRADING_MODE_EFFECTIVE_CHANGED"
    FEED_HEALTH_CHANGED = "FEED_HEALTH_CHANGED"
    BROKER_HEALTH_CHANGED = "BROKER_HEALTH_CHANGED"
    INSTRUMENT_FRESHNESS_CHANGED = "INSTRUMENT_FRESHNESS_CHANGED"
    MARKET_OBSERVATION_ACCEPTED = "MARKET_OBSERVATION_ACCEPTED"
    FEATURE_BUNDLE_CREATED = "FEATURE_BUNDLE_CREATED"
    REGIME_EVALUATED = "REGIME_EVALUATED"
    CALIBRATION_EVALUATED = "CALIBRATION_EVALUATED"
    MODEL_PREDICTION = "MODEL_PREDICTION"
    R10_EVALUATED = "R10_EVALUATED"
    R10X_EVALUATED = "R10X_EVALUATED"
    THESIS_CREATED = "THESIS_CREATED"
    THESIS_REJECTED = "THESIS_REJECTED"
    OPPORTUNITY_CANDIDATE_CREATED = "OPPORTUNITY_CANDIDATE_CREATED"
    OPPORTUNITY_CANDIDATE_REJECTED = "OPPORTUNITY_CANDIDATE_REJECTED"
    PORTFOLIO_DECISION = "PORTFOLIO_DECISION"
    RISK_FACTS_CREATED = "RISK_FACTS_CREATED"
    RISK_DECISION_CREATED = "RISK_DECISION_CREATED"
    A04_AUTHORITY_DECISION = "A04_AUTHORITY_DECISION"
    AUTONOMY_TOKEN_ISSUED = "AUTONOMY_TOKEN_ISSUED"
    AUTONOMY_TOKEN_CONSUMED = "AUTONOMY_TOKEN_CONSUMED"
    AUTONOMY_TOKEN_EXPIRED = "AUTONOMY_TOKEN_EXPIRED"
    AUTONOMY_TOKEN_REVOKED = "AUTONOMY_TOKEN_REVOKED"
    ORDER_INTENT_CREATED = "ORDER_INTENT_CREATED"
    PAPER_ORDER_SUBMITTED = "PAPER_ORDER_SUBMITTED"
    PAPER_ORDER_ACKNOWLEDGED = "PAPER_ORDER_ACKNOWLEDGED"
    PAPER_ORDER_REJECTED = "PAPER_ORDER_REJECTED"
    PAPER_ORDER_CANCELLED = "PAPER_ORDER_CANCELLED"
    FILL_CREATED = "FILL_CREATED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_MARKED = "POSITION_MARKED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    EXIT_INTENT_CREATED = "EXIT_INTENT_CREATED"
    PNL_SNAPSHOT = "PNL_SNAPSHOT"
    OPERATOR_COMMAND = "OPERATOR_COMMAND"
    HARNESS_ADVISORY_CREATED = "HARNESS_ADVISORY_CREATED"
    SESSION_SUMMARY_FINALIZED = "SESSION_SUMMARY_FINALIZED"
    STAGE1_RESULT = "STAGE1_RESULT"
    STAGE2_CONNECTION_STATE = "STAGE2_CONNECTION_STATE"
    STAGE2_SUBSCRIPTION_PLAN = "STAGE2_SUBSCRIPTION_PLAN"
    STAGE2_SUBSCRIPTION_SAMPLE = "STAGE2_SUBSCRIPTION_SAMPLE"
    STAGE2_FRESHNESS_DECISION = "STAGE2_FRESHNESS_DECISION"
    CLOCK_EVIDENCE = "CLOCK_EVIDENCE"
    NORMALIZED_MARKET_EVENT = "NORMALIZED_MARKET_EVENT"
    FEATURE_STATE = "FEATURE_STATE"
    PRODUCTION_PREDICTION = "PRODUCTION_PREDICTION"
    THESIS_DECISION = "THESIS_DECISION"
    CANDIDATE_DECISION = "CANDIDATE_DECISION"
    TOKEN_EVENT = "TOKEN_EVENT"
    ORDER_EVENT = "ORDER_EVENT"
    FILL_EVENT = "FILL_EVENT"
    POSITION_EVENT = "POSITION_EVENT"
    EXIT_EVENT = "EXIT_EVENT"
    PNL_EVENT = "PNL_EVENT"
    OPTION_EVIDENCE = "OPTION_EVIDENCE"
    SHADOW_MODEL_STATE = "SHADOW_MODEL_STATE"
    SAME_STATE_MODEL_RECORD = "SAME_STATE_MODEL_RECORD"
    COUNTERFACTUAL_ENTRY = "COUNTERFACTUAL_ENTRY"
    COUNTERFACTUAL_EXIT = "COUNTERFACTUAL_EXIT"
    COUNTERFACTUAL_SETTLEMENT = "COUNTERFACTUAL_SETTLEMENT"
    SCANNER_FAILURE = "SCANNER_FAILURE"
    DATA_QUALITY_EVENT = "DATA_QUALITY_EVENT"
    RECORDER_HEALTH = "RECORDER_HEALTH"


class SessionIdentity(ATSBaseModel):
    session_id: UUID
    trading_date: str
    market: str = "NSE"
    execution_target: str = "A2_PAPER"
    autonomy_level: str = "A2"
    champion_model_id: str
    champion_model_version: str
    policy_version: str
    system_version: str
    started_at: UTCDateTime
    timezone: str = "Asia/Calcutta"


class EvidencePayload(ATSBaseModel):
    """Closed vocabulary for common evidence fields; absent means unavailable."""

    candidate_id: UUID | None = None
    instrument_id: str | None = None
    underlying: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    feature_bundle_id: UUID | None = None
    regime_id: str | None = None
    decision: str | None = None
    reason_code: str | None = None
    reason_codes: tuple[str, ...] = ()
    probability: FiniteDecimal | None = None
    activation_threshold: FiniteDecimal | None = None
    net_pnl: FiniteDecimal | None = None
    quantity: FiniteDecimal | None = None
    price: FiniteDecimal | None = None
    state: str | None = None
    token_id: UUID | None = None
    thesis_id: UUID | None = None
    portfolio_decision_id: UUID | None = None
    risk_facts_id: UUID | None = None
    risk_decision_id: UUID | None = None
    order_intent_id: UUID | None = None
    paper_order_id: UUID | None = None
    fill_id: UUID | None = None
    position_id: UUID | None = None
    exit_intent_id: UUID | None = None
    source_id: str | None = None
    state_hash: str | None = None
    note: str | None = None
    # Versioned event-specific facts. Values remain inside payload_hash and the
    # session hash chain; this is not an unverified metadata escape hatch.
    details: dict[str, Any] = Field(default_factory=dict)


class SessionEvidenceEvent(ATSBaseModel):
    event_id: UUID
    event_type: EvidenceEventType
    schema_version: SchemaVersion = "1.0"
    session_id: UUID
    sequence_number: int = Field(gt=0)
    event_time: UTCDateTime
    source_time: UTCDateTime | None = None
    ingest_time: UTCDateTime
    available_to_strategy_time: UTCDateTime | None = None
    recorded_at: UTCDateTime
    system_state_version: int = Field(default=1, gt=0)
    payload_hash: str
    previous_event_hash: str | None = None
    producer: str = Field(min_length=1)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    payload: EvidencePayload

    @classmethod
    def build(
        cls,
        *,
        event_type: EvidenceEventType,
        session_id: UUID,
        sequence_number: int,
        payload: EvidencePayload,
        producer: str,
        event_time: datetime | None = None,
        previous_event_hash: str | None = None,
        **kwargs: Any,
    ) -> SessionEvidenceEvent:
        now = datetime.now(UTC)
        occurred = event_time or now
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            session_id=session_id,
            sequence_number=sequence_number,
            event_time=occurred,
            ingest_time=now,
            recorded_at=now,
            payload_hash=canonical_sha256(payload),
            previous_event_hash=previous_event_hash,
            producer=producer,
            payload=payload,
            **kwargs,
        )

    def event_hash(self) -> str:
        return canonical_sha256(self)


class EvidenceManifest(ATSBaseModel):
    session_id: UUID
    identity: SessionIdentity | None = None
    event_count: int = Field(ge=0)
    first_event_hash: str | None = None
    last_event_hash: str | None = None
    session_digest: str
    finalized_at: UTCDateTime


class SessionEvidenceRecorder:
    """Synchronous crash-safe recorder for a single session mirror."""

    def __init__(
        self, identity: SessionIdentity, root: Path | str = "data/runtime/sessions"
    ) -> None:
        self.identity = identity
        self.root = Path(root) / identity.trading_date / str(identity.session_id)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "events.jsonl"
        self.manifest_path = self.root / "manifest.json"
        self._lock = threading.RLock()
        self.write_failures = 0
        self.fsync_failures = 0
        self.dropped_records = 0
        self.last_write_latency_ms = 0.0
        self.max_write_latency_ms = 0.0
        self._events = self._load_events()

    def _load_events(self) -> list[SessionEvidenceEvent]:
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text(encoding="utf-8").splitlines()
        events = [SessionEvidenceEvent.model_validate_json(line) for line in lines if line]
        self.verify(events)
        return events

    @staticmethod
    def verify(events: Iterable[SessionEvidenceEvent]) -> None:
        previous: str | None = None
        expected = 1
        for event in events:
            if event.sequence_number != expected:
                raise ValueError("evidence sequence is not contiguous")
            if event.previous_event_hash != previous:
                raise ValueError("evidence hash chain predecessor mismatch")
            if event.payload_hash != canonical_sha256(event.payload):
                raise ValueError("evidence payload hash mismatch")
            previous = event.event_hash()
            expected += 1

    def append(self, event: SessionEvidenceEvent) -> SessionEvidenceEvent:
        with self._lock:
            if event.session_id != self.identity.session_id:
                raise ValueError("event session_id does not match recorder")
            expected = len(self._events) + 1
            if event.sequence_number != expected:
                raise ValueError("event sequence must continue from durable ledger")
            last_hash = self._events[-1].event_hash() if self._events else None
            if event.previous_event_hash != last_hash:
                raise ValueError("event previous hash does not continue durable ledger")
            self.verify((*self._events, event))
            line = event.model_dump_json() + "\n"
            started = time.perf_counter()
            try:
                with self.events_path.open("ab") as handle:
                    handle.write(line.encode("utf-8"))
                    handle.flush()
                    try:
                        os.fsync(handle.fileno())
                    except OSError:
                        self.fsync_failures += 1
                        raise
            except OSError:
                self.write_failures += 1
                raise
            finally:
                self.last_write_latency_ms = (time.perf_counter() - started) * 1000
                self.max_write_latency_ms = max(
                    self.max_write_latency_ms, self.last_write_latency_ms
                )
            self._events.append(event)
            return event

    def record(
        self,
        event_type: EvidenceEventType,
        payload: EvidencePayload,
        *,
        producer: str,
        event_time: datetime | None = None,
        source_time: datetime | None = None,
        available_to_strategy_time: datetime | None = None,
        correlation_id: UUID | None = None,
    ) -> SessionEvidenceEvent:
        with self._lock:
            previous = self._events[-1].event_hash() if self._events else None
            return self.append(
                SessionEvidenceEvent.build(
                    event_type=event_type,
                    session_id=self.identity.session_id,
                    sequence_number=len(self._events) + 1,
                    payload=payload,
                    producer=producer,
                    event_time=event_time,
                    previous_event_hash=previous,
                    source_time=source_time,
                    available_to_strategy_time=available_to_strategy_time,
                    correlation_id=correlation_id,
                )
            )

    def finalize(self) -> EvidenceManifest:
        with self._lock:
            self.verify(self._events)
            hashes = [event.event_hash() for event in self._events]
            digest = hashlib.sha256("".join(hashes).encode("ascii")).hexdigest()
            manifest = EvidenceManifest(
                session_id=self.identity.session_id,
                identity=self.identity,
                event_count=len(hashes),
                first_event_hash=hashes[0] if hashes else None,
                last_event_hash=hashes[-1] if hashes else None,
                session_digest=digest,
                finalized_at=datetime.now(UTC),
            )
            manifest_json = manifest.model_dump_json(indent=2) + "\n"
            self.manifest_path.write_text(manifest_json, encoding="utf-8")
            return manifest

    def health_snapshot(self) -> dict[str, Any]:
        """Return durable-recorder facts without claiming asynchronous capacity."""
        with self._lock:
            return {
                "recorder_path": str(self.root),
                "sequence_counter": len(self._events),
                "last_hash": self._events[-1].event_hash() if self._events else None,
                "write_failures": self.write_failures,
                "fsync_failures": self.fsync_failures,
                "dropped_records": self.dropped_records,
                "queue_depth": 0,
                "last_write_latency_ms": self.last_write_latency_ms,
                "max_write_latency_ms": self.max_write_latency_ms,
                "fsync_mode": "EACH_EVENT",
            }

    def events(self) -> tuple[SessionEvidenceEvent, ...]:
        with self._lock:
            return tuple(self._events)


__all__ = [
    "EvidenceEventType",
    "EvidenceManifest",
    "EvidencePayload",
    "SessionEvidenceEvent",
    "SessionEvidenceRecorder",
    "SessionIdentity",
]
