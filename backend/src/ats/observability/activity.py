"""Bounded read-side system activity; no financial authority."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from ats.api.models import ActivityReadModel

_SYSTEM_ACTIVITY_LOG: list[ActivityReadModel] = []


def record_system_activity(
    event_kind: str,
    summary: str,
    correlation_id: str | None = None,
    trace_id: str | None = None,
) -> ActivityReadModel:
    """Records an activity event into the platform unified activity log."""
    corr_uuid = None
    if correlation_id:
        clean_corr = correlation_id.replace("-", "").replace("_", "")
        if len(clean_corr) >= 32:
            try:
                corr_uuid = UUID(hex=clean_corr[:32])
            except Exception:
                corr_uuid = uuid.uuid4()
    if corr_uuid is None:
        corr_uuid = uuid.uuid4()

    item = ActivityReadModel(
        activity_id=uuid.uuid4(),
        event_kind=event_kind,
        occurred_at=datetime.now(UTC),
        correlation_id=corr_uuid,
        trace_id=trace_id or f"TRC-{uuid.uuid4().hex[:6].upper()}",
        aggregate_id=None,
        aggregate_version=None,
        summary=summary,
    )
    _SYSTEM_ACTIVITY_LOG.append(item)
    if len(_SYSTEM_ACTIVITY_LOG) > 1000:
        _SYSTEM_ACTIVITY_LOG.pop(0)

    try:
        from ats.api.models import StreamEvent
        from ats.api.stream import broadcast_stream_event

        broadcast_stream_event(
            StreamEvent(
                stream_event_id=item.activity_id,
                event_kind=item.event_kind,
                occurred_at=item.occurred_at,
                correlation_id=item.correlation_id,
                payload={"summary": item.summary, "trace_id": item.trace_id},
            )
        )
    except Exception:
        pass

    return item


def get_system_activity_items() -> list[ActivityReadModel]:
    return list(_SYSTEM_ACTIVITY_LOG)
