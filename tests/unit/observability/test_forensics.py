"""Tests for the forensic subsystem (SYNTHETIC_TEST_ONLY)."""

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


def _identity_zero_trade() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        trading_date="2026-08-28",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="1.0.0",
        system_version="a2-paper",
        started_at=datetime(2026, 8, 28, 9, 15, tzinfo=UTC),
    )


def _identity_full_trade() -> SessionIdentity:
    return SessionIdentity(
        session_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        trading_date="2026-08-28",
        champion_model_id="C0",
        champion_model_version="1.0.0",
        policy_version="1.0.0",
        system_version="a2-paper",
        started_at=datetime(2026, 8, 28, 9, 15, tzinfo=UTC),
    )


@pytest.fixture
def forensic_root():
    root = Path("data/runtime/test-forensics")
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _build_zero_trade_session(root: Path) -> SessionEvidenceRecorder:
    rec = SessionEvidenceRecorder(_identity_zero_trade(), root)
    rec.record(
        EvidenceEventType.SESSION_STARTED,
        EvidencePayload(state="ENTRY_ALLOWED"),
        producer="test",
    )
    # 5 predictions all neutral
    for _i in range(5):
        rec.record(
            EvidenceEventType.MODEL_PREDICTION,
            EvidencePayload(underlying="NIFTY", model_id="C0", probability=Decimal("0.48")),
            producer="test",
        )
    # 1 prediction with a rejection reason
    rec.record(
        EvidenceEventType.MODEL_PREDICTION,
        EvidencePayload(
            underlying="NIFTY",
            model_id="C0",
            probability=Decimal("0.45"),
            decision="REJECTED",
            reason_code="BELOW_ACTIVATION_THRESHOLD",
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.THESIS_REJECTED,
        EvidencePayload(
            reason_code="BELOW_ACTIVATION_THRESHOLD", reason_codes=("BELOW_ACTIVATION_THRESHOLD",)
        ),
        producer="test",
    )
    rec.record(
        EvidenceEventType.SESSION_CLOSED,
        EvidencePayload(state="CLOSED"),
        producer="test",
    )
    return rec


def _build_full_trade_session(root: Path) -> SessionEvidenceRecorder:
    rec = SessionEvidenceRecorder(_identity_full_trade(), root)
    rec.record(
        EvidenceEventType.SESSION_STARTED,
        EvidencePayload(state="ENTRY_ALLOWED"),
        producer="test",
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
            candidate_id=cand_id, instrument_id="BANKNIFTY_OPT", price=Decimal("160.00")
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
    rec.record(
        EvidenceEventType.SESSION_CLOSED,
        EvidencePayload(state="CLOSED"),
        producer="test",
    )
    return rec


def test_zero_trade_funnel_and_why_no_trade(forensic_root):
    rec = _build_zero_trade_session(forensic_root)
    events = rec.events()
    funnel = compute_pipeline_funnel(events)
    counts = funnel["counts"]
    assert counts["production_predictions"] == 6
    assert counts["thesis_rejections"] == 1
    assert counts["candidates"] == 0
    assert counts["portfolio_evaluations"] == 0
    assert counts["a04_evaluations"] == 0
    why = explain_why_no_trade(events)
    assert why["primary_cause"] == "MODEL_ACTIVATION"
    audit = audit_gates(events)
    assert audit["gates"]["portfolio"]["state"] == "NOT_REACHED"
    assert audit["gates"]["a04"]["state"] == "NOT_REACHED"
    assert audit["gates"]["token"]["state"] == "NOT_REACHED"


def test_full_trade_funnel_and_audit(forensic_root):
    rec = _build_full_trade_session(forensic_root)
    events = rec.events()
    funnel = compute_pipeline_funnel(events)
    counts = funnel["counts"]
    assert counts["fills"] == 1
    assert counts["positions_opened"] == 1
    assert counts["positions_closed"] == 1
    assert counts["tokens_issued"] == 1
    why = explain_why_no_trade(events)
    assert why["primary_cause"] == "TRADES_EXECUTED"
    audit = audit_gates(events)
    assert audit["gates"]["portfolio"]["state"] == "ALLOW"
    assert audit["gates"]["a04"]["state"] == "ALLOW"
    assert audit["gates"]["token"]["state"] == "ALLOW"
    assert audit["gates"]["paper_broker"]["state"] == "ALLOW"


def test_finalizer_produces_all_artifacts(forensic_root):
    rec = _build_full_trade_session(forensic_root)
    events = rec.events()
    artifacts = finalize_session(_identity_full_trade(), events, forensic_root)
    expected_files = [
        "session_manifest",
        "session_summary",
        "session_timeline_csv",
        "pipeline_funnel",
        "gate_audit",
        "model_probability_distribution",
        "evidence_integrity",
        "rejection_history_csv",
        "orders_csv",
        "fills_csv",
        "positions_csv",
        "pnl_series_csv",
        "prediction_history_csv",
        "decision_history_csv",
        "why_no_trade",
    ]
    for key in expected_files:
        assert artifacts[key] is not None
        assert Path(artifacts[key]).exists()
    assert artifacts["integrity_status"] == IntegrityStatus.VALID


def test_integrity_invalid_after_tamper(forensic_root):
    rec = _build_full_trade_session(forensic_root)
    rec.finalize()
    # Tamper with the events file
    path = rec.events_path
    text = path.read_text(encoding="utf-8")
    tampered = text.replace("BANKNIFTY", "TAMPERED", 1)
    path.write_text(tampered, encoding="utf-8")
    # Re-load: tamper is detected at load time
    with pytest.raises(ValueError):
        SessionEvidenceRecorder(_identity_full_trade(), forensic_root)
    # Confirm verification function would flag it
    path.write_text(tampered, encoding="utf-8")
    raw_events = []
    from ats.observability.session_evidence import SessionEvidenceEvent

    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            raw_events.append(SessionEvidenceEvent.model_validate_json(line))
    rep = verify_integrity(raw_events)
    assert rep["status"] == IntegrityStatus.INVALID


def test_rejection_analysis_aggregation(forensic_root):
    rec = _build_zero_trade_session(forensic_root)
    events = rec.events()
    analysis = analyze_rejections(events)
    assert analysis["total_rejections"] == 1
    assert "BELOW_ACTIVATION_THRESHOLD" in analysis["by_reason"]
    assert analysis["by_reason"]["BELOW_ACTIVATION_THRESHOLD"]["count"] == 1


def test_model_probability_distribution(forensic_root):
    rec = _build_zero_trade_session(forensic_root)
    events = rec.events()
    dist = compute_model_probability_distribution(events)
    assert "C0" in dist["models"]
    c0 = dist["models"]["C0"]
    assert c0["count"] == 6
    assert c0["max"] <= 0.55
    assert c0["threshold_crossings"]["0.55"] == 0
    assert c0["threshold_crossings"]["0.5"] == 0


def test_near_activations_finds_below_threshold(forensic_root):
    rec = _build_zero_trade_session(forensic_root)
    events = rec.events()
    near = find_near_activations(events, threshold=0.55, max_distance=0.10)
    assert len(near) >= 1
    for n in near:
        assert n["probability"] < 0.55


def test_timeline_ordered_by_sequence(forensic_root):
    rec = _build_full_trade_session(forensic_root)
    events = rec.events()
    timeline = build_session_timeline(events)
    seqs = [e["sequence_number"] for e in timeline]
    assert seqs == sorted(seqs)
    assert len(timeline) >= 10


def test_session_discovery(forensic_root):
    _build_zero_trade_session(forensic_root)
    _build_full_trade_session(forensic_root)
    sessions = discover_sessions(forensic_root)
    assert len(sessions) == 2
    ids = {s["session_id"] for s in sessions}
    assert "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" in ids
    assert "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" in ids


def test_summary_built_from_evidence(forensic_root):
    rec = _build_full_trade_session(forensic_root)
    events = rec.events()
    summary = build_session_summary(_identity_full_trade(), events)
    assert summary["fills"] == 1
    assert summary["positions_opened"] == 1
    assert summary["positions_closed"] == 1
    assert summary["production_predictions"] == 1
    assert summary["trading_date"] == "2026-08-28"
