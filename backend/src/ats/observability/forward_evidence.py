"""Post-shutdown reconstruction and deterministic forward-session validity.

This module has no trading authority.  It consumes only the durable evidence
ledger and therefore cannot turn a live observation into a research claim.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.observability.session_evidence import (
    EvidenceEventType,
    SessionEvidenceEvent,
    SessionEvidenceRecorder,
)


class ForwardValidity(StrEnum):
    VALID_FORWARD_SESSION = "VALID_FORWARD_SESSION"
    VALID_FORWARD_SESSION_WITH_LIMITATIONS = "VALID_FORWARD_SESSION_WITH_LIMITATIONS"
    SUPPLEMENTAL_ONLY = "SUPPLEMENTAL_ONLY"
    INVALID_STAGE2_EVIDENCE = "INVALID_STAGE2_EVIDENCE"
    INVALID_CLOCK_EVIDENCE = "INVALID_CLOCK_EVIDENCE"
    INVALID_PRODUCTION_FUNNEL = "INVALID_PRODUCTION_FUNNEL"
    INVALID_OPTION_EVIDENCE = "INVALID_OPTION_EVIDENCE"
    INVALID_COUNTERFACTUAL_EVIDENCE = "INVALID_COUNTERFACTUAL_EVIDENCE"
    INVALID_RECORDER_HEALTH = "INVALID_RECORDER_HEALTH"
    INVALID_HASH_CHAIN = "INVALID_HASH_CHAIN"
    INVALID_SAME_DAY_DUPLICATE = "INVALID_SAME_DAY_DUPLICATE"


MANDATORY_EVENT_TYPES = frozenset(
    {
        EvidenceEventType.SESSION_CREATED,
        EvidenceEventType.SESSION_STARTED,
        EvidenceEventType.STAGE1_RESULT,
        EvidenceEventType.STAGE2_CONNECTION_STATE,
        EvidenceEventType.STAGE2_SUBSCRIPTION_PLAN,
        EvidenceEventType.STAGE2_SUBSCRIPTION_SAMPLE,
        EvidenceEventType.STAGE2_FRESHNESS_DECISION,
        EvidenceEventType.CLOCK_EVIDENCE,
        EvidenceEventType.NORMALIZED_MARKET_EVENT,
        EvidenceEventType.FEATURE_STATE,
        EvidenceEventType.SAME_STATE_MODEL_RECORD,
        EvidenceEventType.RECORDER_HEALTH,
        EvidenceEventType.SESSION_CLOSED,
        EvidenceEventType.SESSION_SUMMARY_FINALIZED,
    }
)


class ForwardEvidenceManifest(ATSBaseModel):
    session_id: str
    trading_date: str
    source_commit: str
    config_hashes: dict[str, str] = Field(default_factory=dict)
    event_count: int
    event_types_present: dict[str, int]
    required_event_types: tuple[str, ...]
    first_sequence: int | None
    last_sequence: int | None
    hash_chain_result: str
    clock_evidence_completeness: bool
    stage2_completeness: bool
    production_funnel_completeness: bool
    shadow_telemetry_completeness: bool
    option_evidence_completeness: bool
    counterfactual_completeness: bool
    recorder_health_complete: bool
    limitations: tuple[str, ...] = ()
    final_validity_classification: ForwardValidity
    finalized_at: UTCDateTime


def _has_ready_stage2(events: tuple[SessionEvidenceEvent, ...]) -> bool:
    return any(
        event.event_type is EvidenceEventType.STAGE2_FRESHNESS_DECISION
        and event.payload.decision == "MARKET_OPEN_DATA_READY"
        and event.payload.details.get("all_required_fresh") is True
        and event.payload.details.get("four_clock_valid") is True
        for event in events
    )


def _counterfactual_complete(events: tuple[SessionEvidenceEvent, ...]) -> bool:
    entries = {
        str(event.payload.details.get("counterfactual_id"))
        for event in events
        if event.event_type is EvidenceEventType.COUNTERFACTUAL_ENTRY
    }
    settlements = {
        str(event.payload.details.get("counterfactual_id"))
        for event in events
        if event.event_type is EvidenceEventType.COUNTERFACTUAL_SETTLEMENT
        and event.payload.details.get("monetary_classification")
        == "FORWARD_VALID_COUNTERFACTUAL_PNL"
    }
    return not entries or entries <= settlements


def build_manifest(
    recorder: SessionEvidenceRecorder,
    *,
    source_commit: str,
    prior_counted_dates: frozenset[date] = frozenset(),
    config_hashes: dict[str, str] | None = None,
) -> ForwardEvidenceManifest:
    """Classify a closed session solely from its persisted, verified ledger."""
    events = recorder.events()
    try:
        recorder.verify(events)
        hash_result = "PASS"
    except ValueError:
        hash_result = "FAIL"
    counts = Counter(event.event_type.value for event in events)
    present = {event.event_type for event in events}
    lifecycle_complete = {
        EvidenceEventType.SESSION_CREATED,
        EvidenceEventType.SESSION_STARTED,
        EvidenceEventType.STAGE1_RESULT,
        EvidenceEventType.SESSION_CLOSED,
        EvidenceEventType.SESSION_SUMMARY_FINALIZED,
    } <= present
    stage2 = (
        _has_ready_stage2(events)
        and {
            EvidenceEventType.STAGE2_CONNECTION_STATE,
            EvidenceEventType.STAGE2_SUBSCRIPTION_PLAN,
            EvidenceEventType.STAGE2_SUBSCRIPTION_SAMPLE,
        }
        <= present
    )
    clock_events = [
        event for event in events if event.event_type is EvidenceEventType.CLOCK_EVIDENCE
    ]
    clock = bool(clock_events) and all(
        event.payload.details.get("four_clock_valid") is True
        and "raw_provider_age_ms" in event.payload.details
        for event in clock_events
    )
    funnel = EvidenceEventType.FEATURE_STATE in present and any(
        event.event_type
        in {
            EvidenceEventType.PRODUCTION_PREDICTION,
            EvidenceEventType.DATA_QUALITY_EVENT,
        }
        for event in events
    )
    shadow = EvidenceEventType.SAME_STATE_MODEL_RECORD in present
    option = EvidenceEventType.OPTION_EVIDENCE in present
    counterfactual = _counterfactual_complete(events)
    health_events = [e for e in events if e.event_type is EvidenceEventType.RECORDER_HEALTH]
    recorder_health = bool(health_events) and all(
        e.payload.details.get("write_failures") == 0
        and e.payload.details.get("fsync_failures") == 0
        and e.payload.details.get("dropped_records") == 0
        for e in health_events
    )
    limitations: list[str] = []
    trading_day = date.fromisoformat(recorder.identity.trading_date)

    if hash_result != "PASS":
        validity = ForwardValidity.INVALID_HASH_CHAIN
    elif not recorder_health:
        validity = ForwardValidity.INVALID_RECORDER_HEALTH
    elif not stage2:
        validity = ForwardValidity.INVALID_STAGE2_EVIDENCE
    elif not clock:
        validity = ForwardValidity.INVALID_CLOCK_EVIDENCE
    elif not lifecycle_complete or not funnel or not shadow:
        validity = ForwardValidity.INVALID_PRODUCTION_FUNNEL
    elif trading_day in prior_counted_dates:
        validity = ForwardValidity.SUPPLEMENTAL_ONLY
    elif not counterfactual:
        validity = ForwardValidity.INVALID_COUNTERFACTUAL_EVIDENCE
    elif not option:
        limitations.append("OPTION_EVIDENCE_UNAVAILABLE")
        validity = ForwardValidity.VALID_FORWARD_SESSION_WITH_LIMITATIONS
    else:
        validity = ForwardValidity.VALID_FORWARD_SESSION

    return ForwardEvidenceManifest(
        session_id=str(recorder.identity.session_id),
        trading_date=recorder.identity.trading_date,
        source_commit=source_commit,
        config_hashes=config_hashes or {},
        event_count=len(events),
        event_types_present=dict(sorted(counts.items())),
        required_event_types=tuple(sorted(item.value for item in MANDATORY_EVENT_TYPES)),
        first_sequence=events[0].sequence_number if events else None,
        last_sequence=events[-1].sequence_number if events else None,
        hash_chain_result=hash_result,
        clock_evidence_completeness=clock,
        stage2_completeness=stage2,
        production_funnel_completeness=funnel,
        shadow_telemetry_completeness=shadow,
        option_evidence_completeness=option,
        counterfactual_completeness=counterfactual,
        recorder_health_complete=recorder_health,
        limitations=tuple(limitations),
        final_validity_classification=validity,
        finalized_at=datetime.now().astimezone(),
    )


def persist_manifest(recorder: SessionEvidenceRecorder, manifest: ForwardEvidenceManifest) -> Path:
    path = recorder.root / "FORWARD_EVIDENCE_MANIFEST.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def reconstruct_session(session_dir: Path | str) -> dict[str, Any]:
    """Reload facts after runtime destruction; never consult process state."""
    root = Path(session_dir)
    lines = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = tuple(SessionEvidenceEvent.model_validate_json(line) for line in lines if line)
    SessionEvidenceRecorder.verify(events)
    manifest = json.loads((root / "FORWARD_EVIDENCE_MANIFEST.json").read_text("utf-8"))
    counts = Counter(event.event_type.value for event in events)
    reasons = Counter(
        event.payload.reason_code for event in events if event.payload.reason_code is not None
    )
    settlements = [
        event.payload.details
        for event in events
        if event.event_type is EvidenceEventType.COUNTERFACTUAL_SETTLEMENT
    ]
    return {
        "session_id": manifest["session_id"],
        "trading_date": manifest["trading_date"],
        "validity": manifest["final_validity_classification"],
        "event_count": len(events),
        "event_types": dict(sorted(counts.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "stage2_ready": _has_ready_stage2(events),
        "counterfactual_settlements": settlements,
        "hash_chain": "PASS",
    }


__all__ = [
    "ForwardEvidenceManifest",
    "ForwardValidity",
    "MANDATORY_EVENT_TYPES",
    "build_manifest",
    "persist_manifest",
    "reconstruct_session",
]
