from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceRecorder,
    SessionIdentity,
)
from ats.trading_runtime.a2_runner import A2PaperSessionConfig, A2PaperSessionController
from ats.trading_runtime.session_reconciliation import (
    ReconciliationResult,
    ReconciliationState,
    archive_stale_state,
    reconcile_launcher_state,
)


def check(
    state_file: Path,
    evidence: Path,
    checkpoint: Path | None = None,
    *,
    live: bool = False,
    port: bool = False,
) -> ReconciliationResult:
    return reconcile_launcher_state(
        state_file,
        evidence_root=evidence,
        checkpoint_path=checkpoint,
        pid_alive=lambda _pid: live,
        port_active=lambda _port: port,
    )


def test_absent_state_is_clean(tmp_path: Path) -> None:
    assert (
        check(tmp_path / "missing.json", tmp_path).state
        is ReconciliationState.CLEAN_NO_PRIOR_SESSION
    )


def test_live_pid_or_port_never_archives(tmp_path: Path) -> None:
    state = tmp_path / "processes.json"
    state.write_text(json.dumps({"backend": 123, "session_id": "s"}))
    assert check(state, tmp_path, live=True).safe_to_archive is False
    assert check(state, tmp_path, port=True).safe_to_archive is False


def test_dead_process_without_session_id_is_unfinalized(tmp_path: Path) -> None:
    state = tmp_path / "processes.json"
    state.write_text(json.dumps({"backend": 123}))
    result = check(state, tmp_path)
    assert result.state is ReconciliationState.UNFINALIZED_SESSION
    assert result.reason == "RECORDED_SESSION_ID_MISSING"


def test_unresolved_position_blocks(tmp_path: Path) -> None:
    state = tmp_path / "processes.json"
    state.write_text(json.dumps({"backend": 123, "session_id": "s"}))
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"positions": [{"id": "p"}]}))
    assert (
        check(state, tmp_path, checkpoint).state
        is ReconciliationState.POSITION_RECONCILIATION_REQUIRED
    )


def test_hash_mismatch_or_unfinalized_evidence_blocks(tmp_path: Path) -> None:
    state = tmp_path / "processes.json"
    state.write_text(json.dumps({"backend": 123, "session_id": "s"}))
    session = tmp_path / "2026-08-31" / "s"
    session.mkdir(parents=True)
    (session / "events.jsonl").write_text("not-json\n")
    (session / "manifest.json").write_text("{}")
    result = check(state, tmp_path)
    assert result.state is ReconciliationState.UNFINALIZED_SESSION
    assert result.hash_chain_valid is False


def test_safe_archive_requires_proven_result_and_is_non_destructive_on_repeat(
    tmp_path: Path,
) -> None:
    state = tmp_path / "processes.json"
    state.write_text("{}")
    digest = hashlib.sha256(state.read_bytes()).hexdigest()
    from ats.trading_runtime.session_reconciliation import ReconciliationResult

    proven = ReconciliationResult(
        ReconciliationState.STALE_LAUNCHER_STATE,
        "now",
        str(state),
        digest,
        "s",
        (),
        (),
        True,
        True,
        True,
        True,
        0,
        True,
        "FINALIZED_CLOSED_SESSION",
    )
    archived = archive_stale_state(proven, archive_root=tmp_path / "archive")
    assert not state.exists()
    assert archived.archive_path and Path(archived.archive_path).exists()
    with pytest.raises(RuntimeError, match="LAUNCHER_STATE_CHANGED_SINCE_CHECK"):
        archive_stale_state(proven, archive_root=tmp_path / "archive")


def test_a2_lifecycle_writes_closed_finalized_evidence(tmp_path: Path) -> None:
    session_id = uuid4()
    controller = A2PaperSessionController(
        A2PaperSessionConfig(session_id=session_id, evidence_root=str(tmp_path))
    )
    assert controller.start(require_token=False)
    assert controller.stop()
    session_dirs = tuple(tmp_path.glob(f"*/{session_id}"))
    assert len(session_dirs) == 1
    assert (session_dirs[0] / "events.jsonl").exists()
    assert (session_dirs[0] / "manifest.json").exists()
    events = (session_dirs[0] / "events.jsonl").read_text().splitlines()
    assert any("SESSION_CLOSED" in line for line in events)
    assert any("SESSION_SUMMARY_FINALIZED" in line for line in events)


def test_dead_pids_closed_ports_and_valid_finalization_is_proven_stale(tmp_path: Path) -> None:
    session_id = uuid4()
    identity = SessionIdentity(
        session_id=session_id,
        trading_date="2026-08-31",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="A04_CURRENT",
        system_version="TEST",
        started_at=datetime(2026, 8, 31, 3, 30, tzinfo=UTC),
    )
    recorder = SessionEvidenceRecorder(identity, tmp_path / "evidence")
    recorder.record(
        EvidenceEventType.SESSION_CLOSED,
        EvidencePayload(state="CLOSED"),
        producer="test",
    )
    recorder.finalize()
    state = tmp_path / "processes.json"
    state.write_text(json.dumps({"backend": 123, "session_id": str(session_id)}))

    result = check(state, tmp_path / "evidence")

    assert result.state is ReconciliationState.STALE_LAUNCHER_STATE
    assert result.hash_chain_valid is True
    assert result.session_closed is True
    assert result.safe_to_archive is True
