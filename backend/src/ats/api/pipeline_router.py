"""Live pipeline counters exposed truthfully for Operator Intelligence."""

from __future__ import annotations

from typing import cast

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
    snap = cast("dict[str, object]", bridge.snapshot_dict())
    controller = getattr(request.app.state, "a2_session_controller", None)
    feed = getattr(controller, "upstox_feed", None)
    if feed is not None:
        telemetry = feed.telemetry()
        snap.update(
            {
                "upstox_raw_messages": telemetry["upstox_raw_messages"],
                "normalized_messages": telemetry["normalized_updates"],
                "fresh_messages": telemetry["fresh_updates"],
                "subscription_count": telemetry["subscription_count"],
                "connection_state": telemetry["connection_state"],
                "freshness": telemetry["freshness"],
                "by_underlying": telemetry["by_underlying"],
                "option_evidence": telemetry["option_evidence"],
            }
        )
    else:
        snap.update(
            {
                "subscription_count": 0,
                "connection_state": "DISCONNECTED",
                "freshness": {},
                "by_underlying": {},
                "option_evidence": [],
            }
        )
    snap["attached"] = True
    return snap


@router.get("/predictions")
def get_pipeline_predictions(request: Request) -> dict[str, object]:
    bridge = getattr(request.app.state, "live_pipeline_bridge", None)
    if bridge is None:
        return {"predictions": {}, "recent_predictions": []}
    return {
        "predictions": getattr(bridge.counters, "predictions", {}),
        "recent_predictions": getattr(bridge.counters, "recent_predictions", []),
    }


__all__ = ["router"]
