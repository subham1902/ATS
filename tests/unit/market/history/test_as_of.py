"""Unit tests for as-of information gates and revision resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ats.market.history import (
    FutureInformationError,
    HistoricalTruthErrorCode,
    require_available,
    visible_observations,
)

from tests.unit.market.history.fixtures import (
    EXPIRY_MONTHLY,
    EXPIRY_WEEKLY,
    SESSION_START,
    bar_event_time,
    build_test_dataset,
    make_bar_observation,
    scenario_contract_master_change,
    scenario_normal_series,
    scenario_revised_pair,
)

_FAR_FUTURE = datetime(2099, 1, 1, tzinfo=UTC)


def at(seconds: int) -> datetime:
    return SESSION_START + timedelta(seconds=seconds)


def test_require_available_admits_only_visible_records() -> None:
    observation = make_bar_observation(sequence=1)
    assert (
        require_available(observation, at_time=observation.times.available_to_strategy_time)
        is observation
    )
    with pytest.raises(FutureInformationError) as exc_info:
        require_available(observation, at_time=at(0))
    assert exc_info.value.code is HistoricalTruthErrorCode.FUTURE_INFORMATION_NOT_AVAILABLE


def test_visible_window_excludes_future_information() -> None:
    records = scenario_normal_series(4)
    cutoff = bar_event_time(3)
    visible = visible_observations(records, at_time=cutoff)
    assert all(item.times.available_to_strategy_time <= cutoff for item in visible)
    assert len(visible) == 2
    assert {item.instrument for item in visible} == {"RELIANCE"}


def test_revision_replaces_original_only_after_its_availability() -> None:
    original, revision = scenario_revised_pair()
    dataset = build_test_dataset((original, revision))
    before = dataset.visible_as_of(
        original.times.available_to_strategy_time + timedelta(milliseconds=1)
    )
    assert [item.observation_id for item in before] == [original.observation_id]
    after = dataset.visible_as_of(revision.times.available_to_strategy_time)
    assert [item.observation_id for item in after] == [revision.observation_id]


def test_known_expiries_grow_only_at_master_change_availability() -> None:
    v1_row, v2_row = scenario_contract_master_change()
    dataset = build_test_dataset(
        (v1_row, v2_row), contract_master_version="NSE_TEST_MASTER_V2"
    )
    switch_instant = v2_row.times.available_to_strategy_time
    before = dataset.known_expiries_as_of(
        "NIFTY", at_time=switch_instant - timedelta(milliseconds=1)
    )
    after = dataset.known_expiries_as_of("NIFTY", at_time=switch_instant)
    assert before == (EXPIRY_MONTHLY,)
    assert after == tuple(sorted({EXPIRY_MONTHLY, EXPIRY_WEEKLY}))


def test_latest_metadata_switches_with_availability_ordering() -> None:
    v1_row, v2_row = scenario_contract_master_change()
    dataset = build_test_dataset(
        (v1_row, v2_row), contract_master_version="NSE_TEST_MASTER_V2"
    )
    symbol_v1 = "NIFTY24JUN24000CE"
    symbol_v2 = "NIFTY24JUN24100CE"
    latest_before = dataset.latest_contract_metadata_as_of(
        symbol_v1,
        at_time=v2_row.times.available_to_strategy_time - timedelta(milliseconds=1),
    )
    assert latest_before is not None and latest_before.payload.trading_symbol == symbol_v1
    latest_after = dataset.latest_contract_metadata_as_of(symbol_v2, at_time=_FAR_FUTURE)
    assert latest_after is not None and latest_after.payload.trading_symbol == symbol_v2


def test_dataset_manifest_never_contains_market_values() -> None:
    dataset = build_test_dataset(scenario_normal_series(2))
    manifest_json = dataset.manifest.model_dump_json()
    assert "2915" not in manifest_json
    assert "2918.5" not in manifest_json
