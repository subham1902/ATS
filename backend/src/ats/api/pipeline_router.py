"""Live pipeline counters exposed truthfully for Operator Intelligence."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1/pipeline", tags=["pipeline"])


@router.get("/counters")
def get_pipeline_counters(request: Request) -> dict[str, object]:
    bridge = getattr(request.app.state, "live_pipeline_bridge", None)
    if bridge is None:
        return {
            "upstox_raw_messages": 0,
            "normalized_messages": 0,
            "fresh_messages": 0,
            "scanner_observations": 0,
            "candidates_considered": 0,
            "candidates_qualified": 0,
            "rejection_reasons": {},
            "nifty_last": None,
            "banknifty_last": None,
            "attached": False,
        }
    snap = bridge.snapshot_dict()
    snap["attached"] = True
    return snap


__all__ = ["router"]
