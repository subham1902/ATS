import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceRecorder,
    SessionIdentity,
)
from ats.observability.session_replay import replay


def identity() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("11111111-1111-4111-8111-111111111111"),
        trading_date="2026-09-01", champion_model_id="C0", champion_model_version="1",
        policy_version="1", system_version="test", started_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


@pytest.fixture
def evidence_root():
    root = Path("data/runtime/test-session-evidence")
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_hash_chain_restart_and_replay(evidence_root):
    recorder = SessionEvidenceRecorder(identity(), evidence_root)
    recorder.record(EvidenceEventType.MODEL_PREDICTION,
                    EvidencePayload(underlying="NIFTY", model_id="C0", probability=Decimal("0.50")),
                    producer="test")
    recorder.record(EvidenceEventType.THESIS_REJECTED,
                    EvidencePayload(reason_code="NEUTRAL_THESIS"), producer="test")
    manifest = recorder.finalize()

    resumed = SessionEvidenceRecorder(identity(), evidence_root)
    assert len(resumed.events()) == 2
    assert resumed.finalize().session_digest == manifest.session_digest
    assert replay(resumed.events())["predictions"] == 1
    assert replay(resumed.events())["rejections"] == 1


def test_tamper_is_detected(evidence_root):
    recorder = SessionEvidenceRecorder(identity(), evidence_root)
    recorder.record(
        EvidenceEventType.SESSION_STARTED,
        EvidencePayload(state="STARTUP"),
        producer="test",
    )
    path = recorder.events_path
    path.write_text(path.read_text(encoding="utf-8").replace("STARTUP", "HALTED"), encoding="utf-8")
    with pytest.raises(ValueError):
        SessionEvidenceRecorder(identity(), evidence_root)


def test_payload_is_closed_and_decimal_boundary():
    with pytest.raises(ValueError):
        EvidencePayload.model_validate({"unexpected": "secret"})
    with pytest.raises(ValueError):
        EvidencePayload(probability=0.5)  # type: ignore[arg-type]
