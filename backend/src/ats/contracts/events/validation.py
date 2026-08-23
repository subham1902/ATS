"""Pure construction and supplied-chain validation for frozen event contracts."""

from __future__ import annotations

from collections.abc import Sequence

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveInt
from ats.contracts.hashing import canonical_sha256
from ats.contracts.ids import OpaqueId

from .models import EventEnvelope, EventPayload, EventType, TraceId


def create_event(
    *,
    event_id: OpaqueId,
    event_type: EventType,
    aggregate_id: OpaqueId,
    correlation_id: OpaqueId,
    sequence: PositiveInt,
    occurred_at: UTCDateTime,
    recorded_at: UTCDateTime,
    producer: NonEmptyStr,
    payload: EventPayload,
    trace_id: TraceId,
    causation_id: OpaqueId | None = None,
    event_version: PositiveInt = 1,
) -> EventEnvelope:
    """Construct an immutable envelope and compute only its typed payload hash."""

    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        event_version=event_version,
        aggregate_id=aggregate_id,
        causation_id=causation_id,
        correlation_id=correlation_id,
        sequence=sequence,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        producer=producer,
        schema_version="1.0",
        payload=payload,
        payload_hash=canonical_sha256(payload),
        trace_id=trace_id,
    )


def validate_event_chain(
    events: Sequence[EventEnvelope],
    *,
    require_single_correlation: bool = True,
) -> None:
    """Validate a complete ordered chain without replaying or persisting it."""

    if not events:
        raise ValueError("event chain must be non-empty")
    correlation_id = events[0].correlation_id
    seen_ids: set[OpaqueId] = set()
    next_sequence: dict[OpaqueId, int] = {}
    previous_id: OpaqueId | None = None

    for index, event in enumerate(events):
        if event.payload_hash != canonical_sha256(event.payload):
            raise ValueError("payload hash mismatch in event chain")
        if event.event_id in seen_ids:
            raise ValueError("duplicate event_id in event chain")
        if require_single_correlation and event.correlation_id != correlation_id:
            raise ValueError("event chain correlation_id mismatch")
        if index == 0:
            if event.causation_id is not None:
                raise ValueError("root event causation_id must be None")
        elif event.causation_id != previous_id:
            raise ValueError("causation_id must reference the immediately prior event")

        expected = next_sequence.get(event.aggregate_id, 1)
        if event.sequence != expected:
            raise ValueError("aggregate event sequence must be contiguous from one")
        next_sequence[event.aggregate_id] = expected + 1
        seen_ids.add(event.event_id)
        previous_id = event.event_id


__all__ = ["create_event", "validate_event_chain"]
