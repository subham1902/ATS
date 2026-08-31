"""Fault tests: deliberately injected future information is rejected.

Every scenario here injects information a strategy must not see at the
simulated decision time and proves the layer fails closed, either by refusing
dataset construction or by excluding the record from the as-of window.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from ats.market import ApprovedFixture, ReplayConfiguration
from ats.market.fixtures.loader import _load_approved_fixture
from ats.market.history import (
    DatasetSourceClass,
    FutureInformationError,
    HistoricalTruthError,
    HistoricalTruthErrorCode,
    HistoryTimeSemantics,
    build_historical_dataset,
    require_available,
    validate_market_history,
)

from tests.unit.market.history.fixtures import (
    EXPIRY_MONTHLY,
    EXPIRY_WEEKLY,
    MASTER_VERSION_V1,
    MASTER_VERSION_V2,
    SESSION_START,
    bar_event_time,
    build_test_dataset,
    make_bar_observation,
    make_event_observation,
    make_metadata_observation,
    make_option_quote_observation,
    scenario_duplicate_pair,
    scenario_future_leak,
    scenario_normal_series,
    scenario_revised_pair,
    scenario_stale_bar,
)

CODE = HistoricalTruthErrorCode


def _rejects(observations) -> HistoricalTruthError:
    with pytest.raises(HistoricalTruthError) as exc_info:
        build_historical_dataset(
            observations,
            source="ATS_TEST_ONLY_SYNTHETIC",
            source_version="1.0.0",
            data_classification=DatasetSourceClass.TEST_ONLY_SYNTHETIC,
            contract_master_version=MASTER_VERSION_V1,
            file_hashes=(),
            transform_lineage=(),
        )
    return exc_info.value


def test_future_leak_observation_is_rejected_at_construction() -> None:
    assert CODE.BAD_TIME_SEMANTICS.value in str(_rejects((scenario_future_leak(),)))


def test_same_bar_unrealistic_availability_is_rejected() -> None:
    instant = make_bar_observation(
        sequence=1,
        source_lag_ms=0,
        ingest_lag_ms=0,
        availability_lag_ms=0,
    )
    assert CODE.UNREALISTIC_SAME_BAR_AVAILABILITY.value in str(_rejects((instant,)))


def test_duplicate_injection_is_rejected() -> None:
    assert CODE.DUPLICATE_OBSERVATION_IDENTITY.value in str(_rejects(scenario_duplicate_pair()))


def test_malformed_early_revision_is_rejected() -> None:
    original = make_bar_observation(sequence=1)
    early_revision = make_bar_observation(
        sequence=1,
        close_price=Decimal("2919.00"),
        source_lag_ms=100,
        ingest_lag_ms=500,
        availability_lag_ms=1_000,
        supersedes=original.observation_id,
    )
    rejection = _rejects((original, early_revision))
    assert CODE.REVISION_ORDER_INVALID.value in str(rejection)
    report = validate_market_history((original, early_revision))
    assert any(item.code is CODE.REVISION_ORDER_INVALID for item in report.findings)


def test_validly_timestamped_future_bars_build_but_never_leak_early() -> None:
    horizon_start = SESSION_START + timedelta(days=30)
    future_series = tuple(
        make_bar_observation(
            sequence=index + 1,
            event_time=horizon_start + timedelta(minutes=5 * index),
        )
        for index in range(3)
    )
    dataset = build_test_dataset(future_series)
    for probe in [bar_event_time(index) for index in range(1, 6)]:
        assert dataset.visible_as_of(probe) == ()
    first_available = future_series[0].times.available_to_strategy_time
    assert len(dataset.visible_as_of(first_available)) == 1
    with pytest.raises(FutureInformationError):
        require_available(future_series[0], at_time=horizon_start)


def test_future_option_chain_data_is_invisible_until_available() -> None:
    quote = make_option_quote_observation(event_time=SESSION_START)
    dataset = build_test_dataset((*scenario_normal_series(2), quote))
    before = quote.times.available_to_strategy_time - timedelta(milliseconds=1)
    assert all(
        item.observation_id != quote.observation_id for item in dataset.visible_as_of(before)
    )
    assert any(
        item.observation_id == quote.observation_id
        for item in dataset.visible_as_of(quote.times.available_to_strategy_time)
    )
    with pytest.raises(FutureInformationError):
        require_available(quote, at_time=before)


def test_future_expiry_knowledge_is_gated_by_master_availability() -> None:
    v1_row = make_metadata_observation(
        master_version=MASTER_VERSION_V1,
        trading_symbol="NIFTY24JUN24000CE",
        expiry_date=EXPIRY_MONTHLY,
    )
    v2_row = make_metadata_observation(
        master_version=MASTER_VERSION_V2,
        trading_symbol="NIFTY24JUN24100CE",
        expiry_date=EXPIRY_WEEKLY,
        event_time=SESSION_START - timedelta(days=1),
    )
    dataset = build_test_dataset((v1_row, v2_row), contract_master_version=MASTER_VERSION_V2)
    switch = v2_row.times.available_to_strategy_time
    assert EXPIRY_WEEKLY not in dataset.known_expiries_as_of(
        "NIFTY", at_time=switch - timedelta(milliseconds=1)
    )
    assert EXPIRY_WEEKLY in dataset.known_expiries_as_of("NIFTY", at_time=switch)


def test_future_contract_metadata_is_invisible_before_publication() -> None:
    late_master_row = make_metadata_observation(
        master_version=MASTER_VERSION_V2,
        trading_symbol="NIFTY24JUL24500CE",
        expiry_date="2024-07-25",
        event_time=SESSION_START + timedelta(days=20),
        source_lag_ms=3_600_000,
        ingest_lag_ms=3_600_500,
        availability_lag_ms=3_601_000,
    )
    with pytest.raises(FutureInformationError):
        require_available(late_master_row, at_time=SESSION_START)


def test_future_revised_record_is_invisible_until_correction_arrives() -> None:
    original, revision = scenario_revised_pair()
    dataset = build_test_dataset((original, revision))
    before_revision = revision.times.available_to_strategy_time - timedelta(milliseconds=1)
    visible_before = dataset.visible_as_of(before_revision)
    visible_after = dataset.visible_as_of(revision.times.available_to_strategy_time)
    assert [item.observation_id for item in visible_before] == [original.observation_id]
    assert [item.observation_id for item in visible_after] == [revision.observation_id]
    assert visible_after[0].payload.close == revision.payload.close


def test_future_news_event_is_invisible_before_publication() -> None:
    headline = "SYNTHETIC_TEST_ONLY_HEADLINE"
    event = make_event_observation(headline=headline, event_time=SESSION_START)
    dataset = build_test_dataset((*scenario_normal_series(2), event))
    before = event.times.available_to_strategy_time - timedelta(milliseconds=1)
    assert all(
        item.observation_id != event.observation_id for item in dataset.visible_as_of(before)
    )
    assert any(
        item.observation_id == event.observation_id
        for item in dataset.visible_as_of(event.times.available_to_strategy_time)
    )


def test_stale_data_is_accepted_but_never_silently_good() -> None:
    records = (*scenario_normal_series(3), scenario_stale_bar())
    dataset = build_test_dataset(records)
    assert dataset.manifest.quality_summary.degraded_count == 1
    report = validate_market_history(records)
    assert any(item.code is CODE.STALE_OBSERVATION for item in report.findings)


def test_tampered_persisted_dataset_fails_integrity_on_reload() -> None:
    dataset = build_test_dataset(scenario_normal_series(3))
    document = json.loads(dataset.model_dump_json())
    document["observations"][1]["payload"]["volume"] = "12501"
    reloaded = type(dataset).model_validate_json(json.dumps(document))
    report = validate_market_history(reloaded.observations)
    assert any(item.code is CODE.PAYLOAD_HASH_MISMATCH for item in report.findings)


def test_b01_cursor_and_history_gate_diverge_only_when_delays_diverge() -> None:
    calendar_dataset = _load_approved_fixture(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1, nse_calendar()
    )
    configuration = ReplayConfiguration(start_at=bar_event_time(1), received_delay_ms=250)
    delayed = HistoryTimeSemantics(
        source_publication_delay_ms=100,
        ingestion_delay_ms=100,
        strategy_visibility_delay_ms=60_000,
    )
    session = create_history_gated_session(calendar_dataset, configuration, delayed)
    total = session.state.total_bars
    for _ in range(total):
        session.advance()
    assert session.state.cursor.visible_count == total
    assert len(session.visible_observations()) < total


def create_history_gated_session(dataset, configuration, semantics):
    from ats.market.history import create_history_gated_replay

    return create_history_gated_replay(dataset, configuration, semantics=semantics)


def nse_calendar():
    from ats.market import nse_cash_alpha_v1_calendar

    return nse_cash_alpha_v1_calendar()
