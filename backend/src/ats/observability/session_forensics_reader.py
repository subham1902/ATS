"""Forensic read service — typed read-model layer independent of UI.

Reads completed session evidence from JSONL mirror and serves all
forensic artifacts (summary, funnel, timeline, gate audit, probability
distribution, near-activations, decisions, orders, fills, positions,
predictions, rejections, integrity).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ats.contracts.common import UTCDateTime
from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceEvent,
    SessionEvidenceRecorder,
    SessionIdentity,
)
from ats.observability.session_forensics import (
    IntegrityStatus,
    analyze_rejections,
    audit_gates,
    build_session_summary,
    build_session_timeline,
    compute_model_probability_distribution,
    compute_pipeline_funnel,
    discover_sessions,
    explain_why_no_trade,
    finalize_session,
    find_near_activations,
    verify_integrity,
)


# ============================================================================
# Read Service
# ============================================================================


class SessionForensicsReader:
    """Read completed session forensic artifacts from durable evidence."""

    def __init__(self, root: Path | str = "data/runtime/sessions") -> None:
        self.root = Path(root)

    def list_session_ids(self) -> list[str]:
        result: list[str] = []
        discovered = discover_sessions(str(self.root))
        for item in discovered:
            result.append(str(item["session_id"]))
        return sorted(result, key=lambda s: s)

    def get_summary(self, session_id: str) -> dict[str, Any] | None:
        identity = self._resolve_identity(session_id)
        if identity is None:
            return None
        events = self._load_events(identity)
        if events is None:
            return None
        return build_session_summary(identity, events)

    def get_funnel(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return compute_pipeline_funnel(events)

    def get_timeline(self, session_id: str) -> list[dict[str, Any]] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return build_session_timeline(events)

    def get_rejections(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return analyze_rejections(events)

    def get_predictions(self, session_id: str) -> list[dict[str, Any]]:
        events = self._load_events_safe(session_id) or ()
        out: list[dict[str, Any]] = []
        for ev in events:
            if ev.event_type == EvidenceEventType.MODEL_PREDICTION:
                out.append(
                    {
                        "event_id": str(ev.event_id),
                        "sequence_number": ev.sequence_number,
                        "event_time_utc": ev.event_time.isoformat(),
                        "model_id": ev.payload.model_id,
                        "underlying": ev.payload.underlying,
                        "probability": float(ev.payload.probability) if ev.payload.probability is not None else None,
                        "decision": ev.payload.decision,
                        "reason_code": ev.payload.reason_code,
                    }
                )
        return out

    def get_decisions(self, session_id: str) -> list[dict[str, Any]]:
        events = self._load_events_safe(session_id) or ()
        out: list[dict[str, Any]] = []
        for ev in events:
            if ev.event_type in (
                EvidenceEventType.PORTFOLIO_DECISION,
                EvidenceEventType.A04_AUTHORITY_DECISION,
                EvidenceEventType.AUTONOMY_TOKEN_ISSUED,
                EvidenceEventType.ORDER_INTENT_CREATED,
                EvidenceEventType.EXIT_INTENT_CREATED,
            ):
                out.append(
                    {
                        "event_id": str(ev.event_id),
                        "sequence_number": ev.sequence_number,
                        "event_time_utc": ev.event_time.isoformat(),
                        "event_type": ev.event_type.value,
                        "decision": ev.payload.decision,
                        "reason_codes": list(ev.payload.reason_codes) if ev.payload.reason_codes else [],
                    }
                )
        return out

    def get_orders(self, session_id: str) -> list[dict[str, Any]]:
        events = self._load_events_safe(session_id) or ()
        out: list[dict[str, Any]] = []
        for ev in events:
            if ev.event_type in (
                EvidenceEventType.PAPER_ORDER_SUBMITTED,
                EvidenceEventType.PAPER_ORDER_ACKNOWLEDGED,
                EvidenceEventType.PAPER_ORDER_REJECTED,
                EvidenceEventType.PAPER_ORDER_CANCELLED,
            ):
                out.append(
                    {
                        "event_id": str(ev.event_id),
                        "sequence_number": ev.sequence_number,
                        "event_time_utc": ev.event_time.isoformat(),
                        "event_type": ev.event_type.value,
                        "instrument_id": ev.payload.instrument_id,
                        "underlying": ev.payload.underlying,
                    }
                )
        return out

    def get_fills(self, session_id: str) -> list[dict[str, Any]]:
        events = self._load_events_safe(session_id) or ()
        out: list[dict[str, Any]] = []
        for ev in events:
            if ev.event_type == EvidenceEventType.FILL_CREATED:
                out.append(
                    {
                        "event_id": str(ev.event_id),
                        "sequence_number": ev.sequence_number,
                        "event_time_utc": ev.event_time.isoformat(),
                        "instrument_id": ev.payload.instrument_id,
                        "underlying": ev.payload.underlying,
                        "price": str(ev.payload.price) if ev.payload.price is not None else None,
                    }
                )
        return out

    def get_positions(self, session_id: str) -> list[dict[str, Any]]:
        events = self._load_events_safe(session_id) or ()
        out: list[dict[str, Any]] = []
        for ev in events:
            if ev.event_type in (
                EvidenceEventType.POSITION_OPENED,
                EvidenceEventType.POSITION_MARKED,
                EvidenceEventType.POSITION_CLOSED,
                EvidenceEventType.POSITION_REDUCED,
            ):
                out.append(
                    {
                        "event_id": str(ev.event_id),
                        "sequence_number": ev.sequence_number,
                        "event_time_utc": ev.event_time.isoformat(),
                        "event_type": ev.event_type.value,
                        "instrument_id": ev.payload.instrument_id,
                        "price": str(ev.payload.price) if ev.payload.price is not None else None,
                    }
                )
        return out

    def get_gate_audit(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return audit_gates(events)

    def get_integrity(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return verify_integrity(events)

    def get_why_no_trade(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        identity = self._resolve_identity(session_id)
        return explain_why_no_trade(events)

    def get_near_activations(self, session_id: str, *, threshold: float = 0.55, max_distance: float = 0.05, limit: int = 20) -> list[dict[str, Any]] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return find_near_activations(events, threshold=threshold, max_distance=max_distance, limit=limit)

    def get_model_distribution(self, session_id: str) -> dict[str, Any] | None:
        events = self._load_events_safe(session_id)
        if events is None:
            return None
        return compute_model_probability_distribution(events)

    def finalizer_available(self, session_id: str) -> bool:
        discovered = discover_sessions(str(self.root))
        for item in discovered:
            if item["session_id"] == session_id:
                return item.get("finalized", False)
        return False

    def finalize_session(self, session_id: str) -> dict[str, Any] | None:
        identity = self._resolve_identity(session_id)
        if identity is None:
            return None
        root = self.root / identity.trading_date / session_id
        # Load events from JSONL to reconstruct
        recorder = SessionEvidenceRecorder(identity, self.root)
        events = recorder.events()
        return finalize_session(identity, tuple(events), root)

    def get_summary_for_session(self, session_id: str) -> dict[str, Any] | None:
        identity = self._resolve_identity(session_id)
        if identity is None:
            return None
        events = self._load_events_for_identity(identity)
        if events is None:
            return None
        return build_session_summary(identity, events)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_identity(self, session_id: str) -> SessionIdentity | None:
        # Scan the evidence root for the session directory
        for item in discover_sessions(str(self.root)):
            if item["session_id"] == session_id:
                date_dir = item.get("trading_date", "").split("/")[-1] if isinstance(item.get("trading_date"), str) else ""
                # We reconstruct from manifest if available, else from events
                manifest_path = item.get("manifest_path")
                if manifest_path and Path(manifest_path).exists():
                    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
                    return SessionIdentity(
                        session_id=UUID(session_id),
                        trading_date=manifest.get("trading_date", item.get("trading_date", "")),
                        champion_model_id=manifest.get("champion", "C0"),
                        champion_model_version=manifest.get("champion_version", "1.0.0"),
                        policy_version=manifest.get("policy_version", "1.0.0"),
                        system_version=manifest.get("system_version", "a2-paper"),
                        started_at=datetime.fromisoformat(manifest.get("started_at", "2026-01-01T09:15:00")),
                        market=manifest.get("market", "NSE"),
                    )
                else:
                    # Try to read first event for identity
                    events_path = Path(str(self.root)) / item.get("trading_date", "") / session_id / "events.jsonl"
                    if events_path.exists():
                        for line in events_path.read_text(encoding="utf-8").splitlines():
                            if not line:
                                continue
                            ev = SessionEvidenceEvent.model_validate_json(line)
                            # We need identity from session_evidence setup; assume identity built from events path
                            # For simplicity, reconstruct from first event session_id
                            # The session identity is usually stored in the events; but for simplicity we build a basic identity
                            # For real usage, the session identity should be persisted in manifest; we use manifest approach.
                            # If no manifest, return None.
                            return None
        return None

    def _load_events_for_identity(self, identity: SessionIdentity) -> tuple[SessionEvidenceEvent, ...] | None:
        recorder = SessionEvidenceRecorder(identity, self.root)
        try:
            events = recorder.events()
            return events
        except Exception:
            return None

    def _load_events_safe(self, session_id: str) -> tuple[SessionEvidenceEvent, ...] | None:
        identity = self._resolve_identity(session_id)
        if identity is None:
            return None
        return self._load_events_for_identity(identity)
