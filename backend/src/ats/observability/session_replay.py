"""Deterministic summary/replay helpers for a session evidence ledger."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .session_evidence import EvidenceEventType, SessionEvidenceEvent, SessionEvidenceRecorder


def replay(events: tuple[SessionEvidenceEvent, ...]) -> dict[str, Any]:
    SessionEvidenceRecorder.verify(events)
    counts = Counter(event.event_type.value for event in events)
    return {
        "session_id": str(events[0].session_id) if events else None,
        "event_count": len(events),
        "event_counts": dict(sorted(counts.items())),
        "predictions": counts[EvidenceEventType.MODEL_PREDICTION.value],
        "rejections": (
            counts[EvidenceEventType.OPPORTUNITY_CANDIDATE_REJECTED.value]
            + counts[EvidenceEventType.THESIS_REJECTED.value]
        ),
        "portfolio_decisions": counts[EvidenceEventType.PORTFOLIO_DECISION.value],
        "a04_decisions": counts[EvidenceEventType.A04_AUTHORITY_DECISION.value],
        "orders": counts[EvidenceEventType.PAPER_ORDER_SUBMITTED.value],
        "fills": counts[EvidenceEventType.FILL_CREATED.value],
        "positions_opened": counts[EvidenceEventType.POSITION_OPENED.value],
        "positions_closed": counts[EvidenceEventType.POSITION_CLOSED.value],
    }


__all__ = ["replay"]
