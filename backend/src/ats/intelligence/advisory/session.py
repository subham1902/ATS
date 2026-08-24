"""Pure persistent-context construction and event append operations."""

from __future__ import annotations

from ats.contracts.domain.hashing import compute_payload_hash

from .models import AdvisoryEvent, PositionAdvisoryContext


def create_position_context(
    *,
    context: PositionAdvisoryContext,
) -> PositionAdvisoryContext:
    """Validate frozen evidence before accepting caller-owned session state."""

    if compute_payload_hash(context.position_thesis) != context.position_thesis.payload_hash:
        raise ValueError("position thesis payload hash mismatch")
    return context


def append_advisory_event(
    context: PositionAdvisoryContext,
    *,
    event: AdvisoryEvent,
) -> PositionAdvisoryContext:
    """Append a typed event with bounded retention and no ambient session storage."""

    create_position_context(context=context)
    if event.position_id is not None and event.position_id != context.position_thesis.position_id:
        raise ValueError("event position does not match context")
    history = (*context.event_history, event)[-context.maximum_events :]
    return context.model_copy(update={"event_history": history, "updated_at": event.occurred_at})


__all__ = ["append_advisory_event", "create_position_context"]
