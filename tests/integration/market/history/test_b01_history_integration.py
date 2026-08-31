"""Integration of the historical-truth layer with the existing B01 replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ats.market import (
    ApprovedFixture,
    ReplayConfiguration,
    approved_manifest,
    nse_cash_alpha_v1_calendar,
)
from ats.market.fixtures.loader import _load_approved_fixture
from ats.market.history import (
    DatasetSourceClass,
    FileHashEntry,
    FutureInformationError,
    HistoricalDataset,
    HistoricalReplaySession,
    HistoricalTruthError,
    HistoricalTruthErrorCode,
    HistoryTimeSemantics,
    TransformStep,
    build_historical_dataset,
    create_history_gated_replay,
    historical_bar_observations,
    require_available,
)

GOLDEN_DATASET_ID = "4e0745dc-0f7e-523e-9149-fe9721ae051a"
GOLDEN_MANIFEST_HASH = "b2af57a4127491ab92ab07b07a6199940e46b49686e8fc78a2cf130dea81e40d"
GOLDEN_OBSERVATION_HASHES = (
    "70ef2dd859f840a3f474769eee5194287ea5c8f0a32b55245e49ee6987bb3d17",
    "e7d388299d12ea989957318492ed35aeac944205537070f976df60576a871b21",
    "0975078b2b7b4f817407ba9bc2c2be8403d4ae02b871fe78414135c88a0f5be5",
    "df4c2f048eef39937f54d037d0429ffe024721e542454442cdd5650a2cc405cc",
)

REALISTIC_SEMANTICS = HistoryTimeSemantics(
    source_publication_delay_ms=500,
    ingestion_delay_ms=1000,
    strategy_visibility_delay_ms=500,
)


def _approved_dataset():
    calendar = nse_cash_alpha_v1_calendar()
    return _load_approved_fixture(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1, calendar)


def _golden_configuration() -> ReplayConfiguration:
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    return ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=2000)


def _golden_history_dataset() -> HistoricalDataset:
    dataset = _approved_dataset()
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    observations = historical_bar_observations(dataset, semantics=REALISTIC_SEMANTICS)
    return build_historical_dataset(
        observations,
        source="ATS_APPROVED_NSE_CASH_FIXTURE",
        source_version="1.0.0",
        data_classification=DatasetSourceClass.RECORDED_PROVIDER_SHAPE,
        contract_master_version="CASH_ONLY_NO_DERIVATIVES",
        file_hashes=(FileHashEntry(file_name="bars.json", content_sha256=manifest.content_sha256),),
        transform_lineage=(
            TransformStep(
                step_index=0,
                transform_id="REPLAY_BAR_PASSTHROUGH_V1",
                transform_version="1.0.0",
            ),
        ),
    )


def test_b01_replay_and_history_window_stay_in_parity() -> None:
    dataset = _approved_dataset()
    session = create_history_gated_replay(
        dataset, _golden_configuration(), semantics=REALISTIC_SEMANTICS
    )
    total = session.state.total_bars
    for step in range(total):
        snapshot = session.advance()
        visible = session.visible_observations()
        assert len(visible) == session.state.cursor.visible_count == step + 1
        latest_observation = visible[-1]
        assert latest_observation.times.event_time == snapshot.bar_timestamp
        assert latest_observation.times.available_to_strategy_time <= session.clock.now()


def test_bridged_history_matches_committed_golden() -> None:
    dataset = _golden_history_dataset()
    assert str(dataset.manifest.dataset_id) == GOLDEN_DATASET_ID
    assert dataset.manifest.payload_hash == GOLDEN_MANIFEST_HASH
    assert tuple(item.payload_hash for item in dataset.observations) == GOLDEN_OBSERVATION_HASHES


def test_availability_gate_is_independent_of_replay_cursor() -> None:
    dataset = _approved_dataset()
    delayed_visibility = REALISTIC_SEMANTICS.model_copy(
        update={"strategy_visibility_delay_ms": 60_000}
    )
    configuration = ReplayConfiguration(
        start_at=approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1).first_bar,
        received_delay_ms=250,
    )
    session = create_history_gated_replay(dataset, configuration, semantics=delayed_visibility)
    total = session.state.total_bars
    for _ in range(total):
        session.advance()
    assert session.state.phase.value == "TERMINAL"
    assert session.state.cursor.visible_count == total
    assert len(session.visible_observations()) == total - 1
    last_observation = historical_bar_observations(dataset, semantics=delayed_visibility)[-1]
    with pytest.raises(FutureInformationError):
        require_available(last_observation, at_time=session.clock.now())


def test_bridge_rejects_misaligned_history() -> None:
    dataset = _approved_dataset()
    replay_session = create_history_gated_replay(
        dataset, _golden_configuration(), semantics=REALISTIC_SEMANTICS
    )
    observations = historical_bar_observations(dataset, semantics=REALISTIC_SEMANTICS)
    from ats.market.replay.engine import DeterministicReplay

    fresh_replay = DeterministicReplay(dataset, _golden_configuration())
    with pytest.raises(HistoricalTruthError) as exc_info:
        HistoricalReplaySession(fresh_replay, observations[:-1])
    assert exc_info.value.code is HistoricalTruthErrorCode.HISTORY_REPLAY_MISALIGNED
    del replay_session


def test_golden_availability_timeline_is_realistic_and_monotonic() -> None:
    dataset = _golden_history_dataset()
    times = [item.times for item in dataset.observations]
    for left, right in zip(times, times[1:], strict=False):
        assert right.event_time > left.event_time
        assert right.available_to_strategy_time > left.available_to_strategy_time
    for item in times:
        lag = item.available_to_strategy_time - item.event_time
        assert lag >= timedelta(milliseconds=1000)
        assert item.source_time >= item.event_time
        assert item.ingest_time >= item.source_time
        assert item.available_to_strategy_time >= item.ingest_time
    first = times[0]
    expected_first_available = datetime(2024, 6, 3, 3, 45, 2, tzinfo=UTC)
    assert first.available_to_strategy_time == expected_first_available
