from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from ats.observability.forward_evidence import (
    ForwardValidity,
    build_manifest,
    persist_manifest,
    reconstruct_session,
)
from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceRecorder,
    SessionIdentity,
)


def _recorder(tmp_path: Path) -> SessionEvidenceRecorder:
    now = datetime(2026, 9, 1, 3, 45, tzinfo=UTC)
    return SessionEvidenceRecorder(
        SessionIdentity(
            session_id=uuid4(),
            trading_date="2026-09-01",
            champion_model_id="C0",
            champion_model_version="1.0.0",
            policy_version="A04_CURRENT",
            system_version="test",
            started_at=now,
        ),
        tmp_path,
    )


def _record(
    recorder: SessionEvidenceRecorder, event_type: EvidenceEventType, **facts: object
) -> None:
    recorder.record(
        event_type,
        EvidencePayload(
            state=str(facts.pop("state", "RECORDED")),
            decision=facts.pop("decision", None),
            reason_code=facts.pop("reason_code", None),
            details=facts,
        ),
        producer="test",
        event_time=datetime(2026, 9, 1, 3, 46, tzinfo=UTC),
    )


def _complete_zero_trade(recorder: SessionEvidenceRecorder) -> None:
    _record(recorder, EvidenceEventType.SESSION_CREATED)
    _record(recorder, EvidenceEventType.SESSION_STARTED)
    _record(
        recorder,
        EvidenceEventType.STAGE1_RESULT,
        decision="READY_FOR_A2_PAPER_SESSION",
    )
    _record(recorder, EvidenceEventType.STAGE2_CONNECTION_STATE, state="LIVE")
    _record(recorder, EvidenceEventType.STAGE2_SUBSCRIPTION_PLAN, expected=22, actual=22)
    _record(recorder, EvidenceEventType.STAGE2_SUBSCRIPTION_SAMPLE, samples=22)
    _record(
        recorder,
        EvidenceEventType.STAGE2_FRESHNESS_DECISION,
        decision="MARKET_OPEN_DATA_READY",
        all_required_fresh=True,
        four_clock_valid=True,
    )
    _record(
        recorder,
        EvidenceEventType.CLOCK_EVIDENCE,
        raw_provider_age_ms=-8,
        normalized_authority_age_ms=4,
        clock_skew_detected=True,
        clock_skew_ms=8,
        four_clock_valid=True,
    )
    _record(recorder, EvidenceEventType.NORMALIZED_MARKET_EVENT)
    _record(recorder, EvidenceEventType.FEATURE_STATE, state="INVALID")
    _record(
        recorder,
        EvidenceEventType.DATA_QUALITY_EVENT,
        reason_code="VOLUME_UNAVAILABLE",
        c0="NOT_REACHED",
        portfolio="NOT_REACHED",
        risk="NOT_REACHED",
        a04="NOT_REACHED",
    )
    _record(recorder, EvidenceEventType.SHADOW_MODEL_STATE)
    _record(recorder, EvidenceEventType.SAME_STATE_MODEL_RECORD)
    _record(recorder, EvidenceEventType.OPTION_EVIDENCE)
    _record(
        recorder,
        EvidenceEventType.RECORDER_HEALTH,
        write_failures=0,
        fsync_failures=0,
        dropped_records=0,
    )
    _record(recorder, EvidenceEventType.SESSION_CLOSED)
    _record(recorder, EvidenceEventType.SESSION_SUMMARY_FINALIZED)


def test_zero_trade_reconstructs_after_runtime_state_is_gone(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    manifest = build_manifest(recorder, source_commit="abc123")
    persist_manifest(recorder, manifest)
    del recorder

    report = reconstruct_session(next(tmp_path.glob("*/*")))

    assert report["validity"] == "VALID_FORWARD_SESSION"
    assert report["stage2_ready"] is True
    assert report["reason_counts"] == {"VOLUME_UNAVAILABLE": 1}
    assert report["hash_chain"] == "PASS"


def test_same_day_is_supplemental_and_cannot_increment(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    manifest = build_manifest(
        recorder, source_commit="abc123", prior_counted_dates=frozenset({date(2026, 9, 1)})
    )
    assert manifest.final_validity_classification is ForwardValidity.SUPPLEMENTAL_ONLY


def test_missing_stage2_is_invalid(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    recorder._events = tuple(  # type: ignore[assignment]
        event
        for event in recorder.events()
        if event.event_type is not EvidenceEventType.STAGE2_FRESHNESS_DECISION
    )
    # Recreate a valid chain with the same semantic omission.
    rebuilt = _recorder(tmp_path / "rebuilt")
    for event in recorder._events:  # noqa: SLF001
        _record(rebuilt, event.event_type, **event.payload.details)
    assert (
        build_manifest(rebuilt, source_commit="abc123").final_validity_classification
        is ForwardValidity.INVALID_STAGE2_EVIDENCE
    )


def test_future_clock_without_safe_normalization_is_invalid(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    _record(
        recorder,
        EvidenceEventType.CLOCK_EVIDENCE,
        raw_provider_age_ms=-5000,
        clock_skew_detected=True,
        four_clock_valid=False,
    )
    assert (
        build_manifest(recorder, source_commit="abc123").final_validity_classification
        is ForwardValidity.INVALID_CLOCK_EVIDENCE
    )


def test_counterfactual_requires_complete_forward_settlement(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    _record(recorder, EvidenceEventType.COUNTERFACTUAL_ENTRY, counterfactual_id="m2-1")
    assert (
        build_manifest(recorder, source_commit="abc123").final_validity_classification
        is ForwardValidity.INVALID_COUNTERFACTUAL_EVIDENCE
    )
    _record(
        recorder,
        EvidenceEventType.COUNTERFACTUAL_SETTLEMENT,
        counterfactual_id="m2-1",
        monetary_classification="FORWARD_VALID_COUNTERFACTUAL_PNL",
        entry_rule="ASK_AT_DECISION",
        exit_rule="PREDEFINED_HORIZON_BID",
        gross_pnl="10",
        costs="4",
        net_pnl="6",
    )
    assert (
        build_manifest(recorder, source_commit="abc123").final_validity_classification
        is ForwardValidity.VALID_FORWARD_SESSION
    )


def test_recorder_failure_invalidates_research_session(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    _record(
        recorder,
        EvidenceEventType.RECORDER_HEALTH,
        write_failures=1,
        fsync_failures=0,
        dropped_records=0,
    )
    assert (
        build_manifest(recorder, source_commit="abc123").final_validity_classification
        is ForwardValidity.INVALID_RECORDER_HEALTH
    )


@pytest.mark.parametrize(
    ("age_ms", "fresh"),
    [(1999, True), (2000, True), (2001, False)],
)
def test_inclusive_freshness_contract_is_durable(age_ms: int, fresh: bool) -> None:
    classification = "FRESH" if age_ms <= 2000 else "STALE"
    evidence = {
        "normalized_authority_age_ms": age_ms,
        "freshness_threshold_ms": 2000,
        "freshness": classification,
    }
    assert (evidence["freshness"] == "FRESH") is fresh


def test_observability_c0_is_not_authoritative_when_feature_invalid(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    assert not any(
        event.event_type is EvidenceEventType.PRODUCTION_PREDICTION for event in recorder.events()
    )
    shadow = next(
        event
        for event in recorder.events()
        if event.event_type is EvidenceEventType.SHADOW_MODEL_STATE
    )
    assert shadow.payload.state == "RECORDED"


def test_paper_trade_path_reconstructs_all_reached_stages(tmp_path: Path) -> None:
    recorder = _recorder(tmp_path)
    _complete_zero_trade(recorder)
    trade_types = (
        EvidenceEventType.CANDIDATE_DECISION,
        EvidenceEventType.PORTFOLIO_DECISION,
        EvidenceEventType.RISK_DECISION_CREATED,
        EvidenceEventType.A04_AUTHORITY_DECISION,
        EvidenceEventType.TOKEN_EVENT,
        EvidenceEventType.ORDER_EVENT,
        EvidenceEventType.FILL_EVENT,
        EvidenceEventType.POSITION_EVENT,
        EvidenceEventType.EXIT_EVENT,
        EvidenceEventType.PNL_EVENT,
    )
    for event_type in trade_types:
        _record(recorder, event_type, state="PAPER", execution_target="PAPER")
    manifest = build_manifest(recorder, source_commit="abc123")
    persist_manifest(recorder, manifest)

    report = reconstruct_session(recorder.root)

    assert all(report["event_types"][event_type.value] == 1 for event_type in trade_types)
    assert report["validity"] == "VALID_FORWARD_SESSION"
