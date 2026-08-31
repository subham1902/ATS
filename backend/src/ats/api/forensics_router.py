"""Forensic REST API — read-only.

Provides:
GET /v1/sessions
GET /v1/sessions/{session_id}
GET /v1/sessions/{session_id}/summary
GET /v1/sessions/{session_id}/timeline
GET /v1/sessions/{session_id}/funnel
GET /v1/sessions/{session_id}/predictions
GET /v1/sessions/{session_id}/rejections
GET /v1/sessions/{session_id}/decisions
GET /v1/sessions/{session_id}/orders
GET /v1/sessions/{session_id}/fills
GET /v1/sessions/{session_id}/positions
GET /v1/sessions/{session_id}/gate-audit
GET /v1/sessions/{session_id}/integrity
GET /v1/session-evidence/status
No mutations. No real broker orders.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ats.observability.session_forensics_reader import SessionForensicsReader

router = APIRouter(prefix="/v1/forensics", tags=["forensics"])
READER = SessionForensicsReader()


# ============================================================================
# Response models (minimal — enough for dashboard)
# ============================================================================


class SessionReference(BaseModel):
    session_id: str
    trading_date: str
    finalized: bool


class SessionStatus(BaseModel):
    session_id: str
    event_count: int | None = None
    predictions: int = 0
    rejections: int = 0
    candidates: int = 0
    portfolio_decisions: int = 0
    a04_decisions: int = 0
    orders: int = 0
    fills: int = 0
    positions_opened: int = 0
    positions_closed: int = 0
    health: str = "HEALTHY"
    db_persistence: str = "LOCAL_DURABLE_ONLY"
    local_mirror: str = "AVAILABLE"
    integrity: str = "VALID"


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/sessions")
def list_sessions() -> list[SessionReference]:
    out: list[SessionReference] = []
    try:
        discovered = READER.list_session_ids()
    except Exception:
        discovered = []
    # Discover uses discover_sessions; we reconstruct minimal info
    for sid in discovered:
        summary = READER.get_summary_for_session(sid)
        out.append(
            SessionReference(
                session_id=sid,
                trading_date=summary.get("trading_date", "") if summary else "",
                finalized=READER.finalizer_available(sid),
            )
        )
    return out


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any] | None:
    summary = READER.get_summary_for_session(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    integrity = READER.get_integrity(session_id)
    return {
        "session_id": session_id,
        "summary": summary,
        "integrity": integrity,
    }


@router.get("/sessions/{session_id}/summary")
def get_session_summary(session_id: str) -> dict[str, Any] | None:
    summary = READER.get_summary_for_session(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Not found")
    return summary


@router.get("/sessions/{session_id}/timeline")
def get_session_timeline(session_id: str) -> list[dict[str, Any]] | None:
    timeline = READER.get_timeline(session_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Not found")
    return timeline


@router.get("/sessions/{session_id}/funnel")
def get_session_funnel(session_id: str) -> dict[str, Any] | None:
    funnel = READER.get_funnel(session_id)
    if funnel is None:
        raise HTTPException(status_code=404, detail="Not found")
    return funnel


@router.get("/sessions/{session_id}/predictions")
def get_session_predictions(session_id: str) -> list[dict[str, Any]] | None:
    predictions = READER.get_predictions(session_id)
    return predictions


@router.get("/sessions/{session_id}/rejections")
def get_session_rejections(session_id: str) -> dict[str, Any] | None:
    rejections = READER.get_rejections(session_id)
    if rejections is None:
        raise HTTPException(status_code=404, detail="Not found")
    return rejections


@router.get("/sessions/{session_id}/decisions")
def get_session_decisions(session_id: str) -> list[dict[str, Any]] | None:
    return READER.get_decisions(session_id)


@router.get("/sessions/{session_id}/orders")
def get_session_orders(session_id: str) -> list[dict[str, Any]] | None:
    return READER.get_orders(session_id)


@router.get("/sessions/{session_id}/fills")
def get_session_fills(session_id: str) -> list[dict[str, Any]] | None:
    return READER.get_fills(session_id)


@router.get("/sessions/{session_id}/positions")
def get_session_positions(session_id: str) -> list[dict[str, Any]] | None:
    return READER.get_positions(session_id)


@router.get("/sessions/{session_id}/gate-audit")
def get_session_gate_audit(session_id: str) -> dict[str, Any] | None:
    audit = READER.get_gate_audit(session_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Not found")
    return audit


@router.get("/sessions/{session_id}/integrity")
def get_session_integrity(session_id: str) -> dict[str, Any] | None:
    integrity = READER.get_integrity(session_id)
    if integrity is None:
        raise HTTPException(status_code=404, detail="Not found")
    return integrity


@router.get("/session-evidence/status")
def get_evidence_status() -> SessionStatus:
    # For active/live session status, we use the session discovery and pick the most recent
    discovered = READER.list_session_ids()
    if not discovered:
        return SessionStatus(
            session_id="NONE",
            health="HEALTHY",
            db_persistence="LOCAL_DURABLE_ONLY",
            local_mirror="NOT_INITIALIZED",
            integrity="VALID",
            predictions=0,
            rejections=0,
            candidates=0,
            portfolio_decisions=0,
            a04_decisions=0,
            orders=0,
            fills=0,
            positions_opened=0,
            positions_closed=0,
        )
    # Use the last session for basic metrics (simplified)
    sid = discovered[-1]
    summary = READER.get_summary_for_session(sid)
    integrity = READER.get_integrity(sid)
    predictions = READER.get_predictions(sid) or []
    rejections = READER.get_rejections(sid) or {}
    orders = READER.get_orders(sid) or []
    fills = READER.get_fills(sid) or []
    positions = READER.get_positions(sid) or []
    return SessionStatus(
        session_id=sid,
        event_count=summary.get("observations", 0) if isinstance(summary, dict) else 0,
        predictions=len(predictions),
        rejections=rejections.get("total_rejections", 0) if isinstance(rejections, dict) else 0,
        candidates=summary.get("candidates", 0) if isinstance(summary, dict) else 0,
        portfolio_decisions=(
            summary.get("portfolio_decisions", 0) if isinstance(summary, dict) else 0
        ),
        a04_decisions=summary.get("a04_decisions", 0) if isinstance(summary, dict) else 0,
        orders=len(orders),
        fills=len(fills),
        positions_opened=sum(1 for p in positions if p.get("event_type") == "POSITION_OPENED"),
        positions_closed=sum(1 for p in positions if p.get("event_type") == "POSITION_CLOSED"),
        health="HEALTHY",
        db_persistence="LOCAL_DURABLE_ONLY",
        local_mirror="AVAILABLE",
        integrity=integrity.get("status", "VALID") if isinstance(integrity, dict) else "VALID",
    )
