"""Deterministic, non-destructive reconciliation of A2 launcher state."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class ReconciliationState(StrEnum):
    CLEAN_NO_PRIOR_SESSION = "CLEAN_NO_PRIOR_SESSION"
    RESTORED_VALID_SESSION = "RESTORED_VALID_SESSION"
    STALE_LAUNCHER_STATE = "STALE_LAUNCHER_STATE"
    UNFINALIZED_SESSION = "UNFINALIZED_SESSION"
    POSITION_RECONCILIATION_REQUIRED = "POSITION_RECONCILIATION_REQUIRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReconciliationResult:
    state: ReconciliationState
    checked_at: str
    state_file: str
    original_sha256: str | None
    recorded_session_id: str | None
    live_pids: tuple[int, ...]
    active_ports: tuple[int, ...]
    evidence_exists: bool
    manifest_exists: bool
    hash_chain_valid: bool | None
    session_closed: bool | None
    unresolved_positions: int | None
    safe_to_archive: bool
    reason: str
    archive_path: str | None = None


def reconcile_launcher_state(
    state_file: Path,
    *,
    evidence_root: Path,
    checkpoint_path: Path | None,
    pid_alive: Callable[[int], bool],
    port_active: Callable[[int], bool],
) -> ReconciliationResult:
    checked_at = datetime.now(UTC).isoformat()
    if not state_file.exists():
        return ReconciliationResult(
            ReconciliationState.CLEAN_NO_PRIOR_SESSION,
            checked_at,
            str(state_file),
            None,
            None,
            (),
            (),
            False,
            False,
            None,
            None,
            0,
            False,
            "LAUNCHER_STATE_ABSENT",
        )
    raw = state_file.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ReconciliationResult(
            ReconciliationState.UNKNOWN,
            checked_at,
            str(state_file),
            digest,
            None,
            (),
            (),
            False,
            False,
            False,
            None,
            None,
            False,
            "LAUNCHER_STATE_INVALID_JSON",
        )
    pids = tuple(
        sorted(
            {
                int(payload[key])
                for key in ("backend", "frontend", "backend_launcher", "frontend_launcher")
                if isinstance(payload.get(key), int) and payload[key] > 0
            }
        )
    )
    live_pids = tuple(pid for pid in pids if pid_alive(pid))
    active_ports = tuple(port for port in (8000, 3000) if port_active(port))
    session_id = payload.get("session_id")
    session_id = session_id if isinstance(session_id, str) and session_id else None

    unresolved_positions: int | None = 0
    if checkpoint_path is not None and checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            positions = checkpoint.get("positions", checkpoint.get("open_positions", []))
            unresolved_positions = len(positions) if isinstance(positions, list | dict) else None
        except (OSError, json.JSONDecodeError):
            unresolved_positions = None

    if live_pids or active_ports:
        return ReconciliationResult(
            ReconciliationState.RESTORED_VALID_SESSION,
            checked_at,
            str(state_file),
            digest,
            session_id,
            live_pids,
            active_ports,
            False,
            False,
            None,
            None,
            unresolved_positions,
            False,
            "RECORDED_PROCESS_OR_PORT_ACTIVE",
        )
    if unresolved_positions is None or unresolved_positions > 0:
        return ReconciliationResult(
            ReconciliationState.POSITION_RECONCILIATION_REQUIRED,
            checked_at,
            str(state_file),
            digest,
            session_id,
            (),
            (),
            False,
            False,
            None,
            None,
            unresolved_positions,
            False,
            "PAPER_POSITION_STATE_UNRESOLVED",
        )
    if session_id is None:
        return ReconciliationResult(
            ReconciliationState.UNFINALIZED_SESSION,
            checked_at,
            str(state_file),
            digest,
            None,
            (),
            (),
            False,
            False,
            None,
            None,
            0,
            False,
            "RECORDED_SESSION_ID_MISSING",
        )

    matches = tuple(evidence_root.glob(f"*/{session_id}"))
    session_dir = matches[0] if len(matches) == 1 else None
    evidence_path = session_dir / "events.jsonl" if session_dir else None
    manifest_candidates = (
        (session_dir / "manifest.json", session_dir / "session_manifest.json")
        if session_dir
        else ()
    )
    manifest_path = next((path for path in manifest_candidates if path.exists()), None)
    evidence_exists = evidence_path is not None and evidence_path.exists()
    manifest_exists = manifest_path is not None
    hash_chain_valid: bool | None = None
    session_closed: bool | None = None
    if evidence_exists and manifest_exists:
        try:
            from ats.observability.session_evidence import (
                EvidenceEventType,
                SessionEvidenceEvent,
                SessionEvidenceRecorder,
            )

            assert evidence_path is not None
            events = tuple(
                SessionEvidenceEvent.model_validate_json(line)
                for line in evidence_path.read_text(encoding="utf-8").splitlines()
                if line
            )
            SessionEvidenceRecorder.verify(events)
            hash_chain_valid = True
            session_closed = any(
                event.event_type is EvidenceEventType.SESSION_CLOSED for event in events
            )
        except Exception:
            hash_chain_valid = False
            session_closed = None
    safe = bool(evidence_exists and manifest_exists and hash_chain_valid and session_closed)
    return ReconciliationResult(
        ReconciliationState.STALE_LAUNCHER_STATE
        if safe
        else ReconciliationState.UNFINALIZED_SESSION,
        checked_at,
        str(state_file),
        digest,
        session_id,
        (),
        (),
        evidence_exists,
        manifest_exists,
        hash_chain_valid,
        session_closed,
        0,
        safe,
        "FINALIZED_CLOSED_SESSION" if safe else "FINALIZED_EVIDENCE_NOT_PROVEN",
    )


def archive_stale_state(
    result: ReconciliationResult, *, archive_root: Path
) -> ReconciliationResult:
    if result.state is not ReconciliationState.STALE_LAUNCHER_STATE or not result.safe_to_archive:
        raise RuntimeError("LAUNCHER_STATE_NOT_PROVEN_STALE")
    source = Path(result.state_file)
    if (
        not source.exists()
        or hashlib.sha256(source.read_bytes()).hexdigest() != result.original_sha256
    ):
        raise RuntimeError("LAUNCHER_STATE_CHANGED_SINCE_CHECK")
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = archive_root / f"processes-{stamp}-{result.original_sha256[:12]}.json"
    os.replace(source, destination)
    return ReconciliationResult(
        **{**result.__dict__, "archive_path": str(destination), "reason": "ARCHIVED_PROVEN_STALE"}
    )


__all__ = [
    "ReconciliationResult",
    "ReconciliationState",
    "archive_stale_state",
    "reconcile_launcher_state",
]
