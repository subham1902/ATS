"""Synthetic end-to-end session finalization and corruption tests."""

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
from ats.observability.session_forensics import IntegrityStatus, finalize_session, verify_integrity


def identity_trade() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        trading_date="2026-08-28",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="1.0.0",
        system_version="a2-paper",
        started_at=datetime(2026, 8, 28, 9, 15, tzinfo=UTC),
    )


def identity_zero() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        trading_date="2026-08-28",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="1.0.0",
        system_version="a2-paper",
        started_at=datetime(2026, 8, 28, 9, 15, tzinfo=UTC),
    )


@pytest.fixture
def synthetic_root():
    root = Path("data/runtime/test-e2e")
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_synthetic_zero_trade_finalized(synthetic_root):
    """Zero-trade synthetic session finalized successfully (SYNTHETIC_TEST_ONLY)."""
    # Build zero-trade events manually
    rec = SessionEvidenceRecorder(identity_zero(), synthetic_root)
    rec.record(
        EvidenceEventType.SESSION_STARTED, EvidencePayload(state="ENTRY_ALLOWED"), producer="test"
    )
    rec.record(
        EvidenceEventType.MODEL_PREDICTION,
        EvidencePayload(underlying="NIFTY", model_id="C0", probability=Decimal("0.45")),
        producer="test",
    )
    rec.record(
        EvidenceEventType.THESIS_REJECTED,
        EvidencePayload(
            reason_code="BELOW_ACTIVATION_THRESHOLD", reason_codes=("BELOW_ACTIVATION_THRESHOLD",)
        ),
        producer="test",
    )
    rec.record(EvidenceEventType.SESSION_CLOSED, EvidencePayload(state="CLOSED"), producer="test")
    rec.finalize()
    events = rec.events()
    artifacts = finalize_session(identity_zero(), events, synthetic_root)
    assert artifacts["why_no_trade"] is not None
    assert artifacts["integrity_status"] == "VALID"
    assert Path(artifacts["root"]).exists()
    # Read why_no_trade
    import json

    why = json.loads(Path(artifacts["why_no_trade"]).read_text(encoding="utf-8"))
    assert why["primary_cause"] == "MODEL_ACTIVATION"


def test_synthetic_full_trade_finalized(synthetic_root):
    """Full synthetic paper trade session finalized (SYNTHETIC_TEST_ONLY)."""
    rec = SessionEvidenceRecorder(identity_trade(), synthetic_root)
    rec.record(
        EvidenceEventType.SESSION_STARTED, EvidencePayload(state="ENTRY_ALLOWED"), producer="test"
    )
    rec.record(
        EvidenceEventType.MODEL_PREDICTION,
        EvidencePayload(underlying="BANKNIFTY", model_id="C0", probability=Decimal("0.62")),
        producer="test",
    )
    cand_id = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    rec.record(
        EvidenceEventType.OPPORTUNITY_CANDIDATE_CREATED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.PORTFOLIO_DECISION,
        EvidencePayload(
            candidate_id=cand_id, decision="ALLOW", reason_codes=("PORTFOLIO_ALLOCATION_PERMITTED",)
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.A04_AUTHORITY_DECISION,
        EvidencePayload(candidate_id=cand_id, decision="ALLOW", reason_codes=("ALLOW",)),
        producer="test",
    )
    rec.record(
        EvidenceEventType.AUTONOMY_TOKEN_ISSUED,
        EvidencePayload(
            candidate_id=cand_id, token_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.ORDER_INTENT_CREATED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.PAPER_ORDER_SUBMITTED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.PAPER_ORDER_ACKNOWLEDGED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.FILL_CREATED,
        EvidencePayload(
            candidate_id=cand_id, instrument_id="BANKNIFTY_OPT", price=Decimal("150.00")
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.POSITION_OPENED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.POSITION_MARKED,
        EvidencePayload(
            candidate_id=cand_id, instrument_id="BANKNIFTY_OPT", price=Decimal("152.50")
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.EXIT_INTENT_CREATED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT", reason_code="TRAIL"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.POSITION_CLOSED,
        EvidencePayload(candidate_id=cand_id, instrument_id="BANKNIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.PNL_SNAPSHOT,
        EvidencePayload(state="REALIZED_PNL", net_pnl=Decimal("250.00")),
        producer="test",
    )
    rec.record(EvidenceEventType.SESSION_CLOSED, EvidencePayload(state="CLOSED"), producer="test")
    rec.finalize()
    events = rec.events()
    artifacts = finalize_session(identity_trade(), events, synthetic_root)
    assert artifacts["integrity_status"] == "VALID"
    why = __import__("json").loads(
        __import__("pathlib").Path(artifacts["why_no_trade"]).read_text(encoding="utf-8")
    )
    assert why["primary_cause"] == "TRADES_EXECUTED"


def test_restart_and_finalization(synthetic_root):
    """Restart between open and exit, then finalize (SYNTHETIC_TEST_ONLY)."""
    # First session (open)
    identity = identity_trade()
    rec = SessionEvidenceRecorder(identity, synthetic_root)
    rec.record(
        EvidenceEventType.SESSION_STARTED, EvidencePayload(state="ENTRY_ALLOWED"), producer="test"
    )
    rec.record(
        EvidenceEventType.MODEL_PREDICTION,
        EvidencePayload(underlying="NIFTY", model_id="C0", probability=Decimal("0.60")),
        producer="test",
    )
    cand_id = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    rec.record(
        EvidenceEventType.OPPORTUNITY_CANDIDATE_CREATED,
        EvidencePayload(candidate_id=cand_id, instrument_id="NIFTY_OPT"),
        producer="test",
    )
    rec.record(
        EvidenceEventType.POSITION_OPENED,
        EvidencePayload(candidate_id=cand_id, instrument_id="NIFTY_OPT"),
        producer="test",
    )
    # Restart: same identity
    rec2 = SessionEvidenceRecorder(identity, synthetic_root)
    # Continue events
    rec2.record(
        EvidenceEventType.POSITION_MARKED,
        EvidencePayload(candidate_id=cand_id, instrument_id="NIFTY_OPT", price=Decimal("21000")),
        producer="test",
    )
    rec2.record(
        EvidenceEventType.EXIT_INTENT_CREATED,
        EvidencePayload(candidate_id=cand_id, instrument_id="NIFTY_OPT", reason_code="TRAIL"),
        producer="test",
    )
    rec2.record(
        EvidenceEventType.POSITION_CLOSED,
        EvidencePayload(candidate_id=cand_id, instrument_id="NIFTY_OPT"),
        producer="test",
    )
    rec2.record(
        EvidenceEventType.PNL_SNAPSHOT,
        EvidencePayload(state="REALIZED_PNL", net_pnl=Decimal("100.00")),
        producer="test",
    )
    rec2.record(EvidenceEventType.SESSION_CLOSED, EvidencePayload(state="CLOSED"), producer="test")
    rec2.finalize()
    events = rec2.events()
    # Verify sequence continuity
    seqs = [ev.sequence_number for ev in events]
    assert seqs == sorted(seqs)
    # No duplicates
    event_ids = [str(ev.event_id) for ev in events]
    assert len(event_ids) == len(set(event_ids))
    # Verify manifest exists (finalize creates it)
    finalize_session(identity, events, synthetic_root)
    manifest_path = (
        synthetic_root / identity.trading_date / str(identity.session_id) / "session_manifest.json"
    )
    assert manifest_path.exists()


def test_corruption_detected_and_not_hidden(synthetic_root):
    """Corruption in a synthetic session must report INVALID integrity."""
    identity = identity_trade()
    rec = SessionEvidenceRecorder(identity, synthetic_root)
    rec.record(
        EvidenceEventType.SESSION_STARTED, EvidencePayload(state="ENTRY_ALLOWED"), producer="test"
    )
    rec.record(
        EvidenceEventType.MODEL_PREDICTION,
        EvidencePayload(underlying="BANKNIFTY", model_id="C0", probability=Decimal("0.60")),
        producer="test",
    )
    rec.record(EvidenceEventType.SESSION_CLOSED, EvidencePayload(state="CLOSED"), producer="test")
    rec.finalize()
    path = synthetic_root / identity.trading_date / str(identity.session_id) / "events.jsonl"
    text = path.read_text(encoding="utf-8")
    # Corrupt one line by replacing a number
    corrupted = text.replace("0.60", "0.99", 1)
    path.write_text(corrupted, encoding="utf-8")
    # Load events manually and verify
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            events.append(
                __import__(
                    "ats.observability.session_evidence", fromlist=[""]
                ).SessionEvidenceEvent.model_validate_json(line)
            )
    result = verify_integrity(tuple(events))
    assert result["status"] == IntegrityStatus.INVALID
    assert result["reason"] != "OK"
    # Do NOT use the corrupted session for forensic production
    # Artifacts from corrupted session must not be treated as authoritative
