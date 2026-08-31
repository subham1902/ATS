import concurrent.futures
import tempfile
import uuid
from datetime import UTC, datetime

from ats.contracts.hashing import canonical_sha256
from ats.observability.session_evidence import (
    EvidenceEventType,
    EvidencePayload,
    SessionEvidenceEvent,
    SessionEvidenceRecorder,
    SessionIdentity,
)


def test_concurrent_recording_stress() -> None:
    """8-16 concurrent writers generating 1,000+ total events with mixed event types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        identity = SessionIdentity(
            session_id=uuid.uuid4(),
            trading_date="2026-08-31",
            champion_model_id="C0",
            champion_model_version="1.0.0",
            policy_version="A04_V1",
            system_version="2.0.0",
            started_at=datetime.now(UTC),
        )
        recorder = SessionEvidenceRecorder(identity, root=tmpdir)

        num_threads = 16
        events_per_thread = 75
        total_events = num_threads * events_per_thread

        producer_types = [
            (EvidenceEventType.CLOCK_EVIDENCE, "UpstoxV3RuntimeFeed"),
            (EvidenceEventType.NORMALIZED_MARKET_EVENT, "UpstoxV3RuntimeFeed"),
            (EvidenceEventType.PRODUCTION_PREDICTION, "C0ProductionChampion"),
            (EvidenceEventType.SHADOW_MODEL_STATE, "AlphaV4ShadowAdapter"),
            (EvidenceEventType.SAME_STATE_MODEL_RECORD, "ForwardShadowChampionshipEngine"),
            (EvidenceEventType.OPTION_EVIDENCE, "UpstoxOptionUniverse"),
            (EvidenceEventType.DATA_QUALITY_EVENT, "DataQualityMonitor"),
            (EvidenceEventType.SESSION_PHASE_CHANGED, "A2SessionCoordinator"),
        ]

        def worker(thread_id: int) -> None:
            for i in range(events_per_thread):
                ev_type, producer = producer_types[(thread_id + i) % len(producer_types)]
                instrument = (
                    "NSE_INDEX|Nifty 50" if i % 2 == 0 else "NSE_INDEX|Nifty Bank"
                )
                recorder.record(
                    ev_type,
                    EvidencePayload(
                        instrument_id=instrument,
                        state="VALID",
                        details={"thread_id": thread_id, "iteration": i, "ev_type": ev_type.value},
                    ),
                    producer=producer,
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, t) for t in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # In-memory check
        events = recorder.events()
        assert len(events) == total_events

        # Check sequence contiguity and hash chain in-memory
        for idx, ev in enumerate(events, start=1):
            assert ev.sequence_number == idx

        # Finalize manifest
        manifest = recorder.finalize()
        assert manifest.event_count == total_events
        assert manifest.first_event_hash == events[0].event_hash()
        assert manifest.last_event_hash == events[-1].event_hash()

        # Post-shutdown reload from disk
        reloaded = SessionEvidenceRecorder(identity, root=tmpdir)
        reloaded_events = reloaded.events()
        assert len(reloaded_events) == total_events

        # Verify disk file line-by-line
        raw_lines = [
            line
            for line in reloaded.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(raw_lines) == total_events

        # Verify each line is valid JSON and hash predecessor matches
        previous_hash = None
        for idx, line in enumerate(raw_lines, start=1):
            parsed = SessionEvidenceEvent.model_validate_json(line)
            assert parsed.sequence_number == idx
            assert parsed.previous_event_hash == previous_hash
            assert parsed.payload_hash == canonical_sha256(parsed.payload)
            previous_hash = parsed.event_hash()


def test_concurrent_finalization_race() -> None:
    """Finalization concurrently racing active writers must safely serialize."""
    with tempfile.TemporaryDirectory() as tmpdir:
        identity = SessionIdentity(
            session_id=uuid.uuid4(),
            trading_date="2026-08-31",
            champion_model_id="C0",
            champion_model_version="1.0.0",
            policy_version="A04_V1",
            system_version="2.0.0",
            started_at=datetime.now(UTC),
        )
        recorder = SessionEvidenceRecorder(identity, root=tmpdir)

        num_threads = 8
        events_per_thread = 50

        def writer(thread_id: int) -> None:
            for i in range(events_per_thread):
                recorder.record(
                    EvidenceEventType.CLOCK_EVIDENCE,
                    EvidencePayload(
                        instrument_id="NSE_INDEX|Nifty 50",
                        state="VALID",
                        details={"thread_id": thread_id, "iteration": i},
                    ),
                    producer=f"Thread-{thread_id}",
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads + 1) as executor:
            writer_futures = [executor.submit(writer, t) for t in range(num_threads)]
            # Wait for writers to complete before finalizing
            for f in concurrent.futures.as_completed(writer_futures):
                f.result()
            manifest = recorder.finalize()

        assert manifest.event_count == num_threads * events_per_thread
        reloaded = SessionEvidenceRecorder(identity, root=tmpdir)
        assert len(reloaded.events()) == manifest.event_count
