from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceRecorder,
    SessionIdentity,
)
from ats.observability.session_forensics_reader import SessionForensicsReader


def _identity() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("11111111-2222-4333-8444-555555555555"),
        trading_date="2026-08-31",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="A04_CURRENT",
        system_version="A2_TEST",
        started_at=datetime(2026, 8, 31, 9, 10, tzinfo=UTC),
    )


def test_reader_discovers_canonical_manifest_and_preserves_identity(tmp_path) -> None:
    identity = _identity()
    recorder = SessionEvidenceRecorder(identity, tmp_path)
    recorder.record(
        EvidenceEventType.SESSION_STARTED,
        EvidencePayload(state="RUNNING"),
        producer="test",
    )
    recorder.record(
        EvidenceEventType.SESSION_CLOSED,
        EvidencePayload(state="CLOSED"),
        producer="test",
    )
    recorder.finalize()

    reader = SessionForensicsReader(tmp_path)
    session_id = str(identity.session_id)
    assert reader.list_session_ids() == [session_id]
    assert reader.finalizer_available(session_id) is True
    summary = reader.get_summary(session_id)
    assert summary is not None
    assert summary["system_version"] == "A2_TEST"
    assert reader.get_integrity(session_id)["status"] == "VALID"


def test_reader_supports_legacy_manifest_without_identity(tmp_path) -> None:
    identity = _identity()
    recorder = SessionEvidenceRecorder(identity, tmp_path)
    recorder.record(
        EvidenceEventType.SESSION_STARTED,
        EvidencePayload(state="RUNNING"),
        producer="test",
    )
    recorder.finalize()
    manifest_path = recorder.manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("identity")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    reader = SessionForensicsReader(tmp_path)
    session_id = str(identity.session_id)
    summary = reader.get_summary(session_id)
    assert summary is not None
    assert summary["system_version"] == "A2_PAPER_LEGACY_MANIFEST"
    assert reader.get_integrity(session_id)["status"] == "VALID"
