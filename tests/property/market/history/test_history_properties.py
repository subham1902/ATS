"""Property tests: determinism, permutation invariance, as-of monotonicity."""

from __future__ import annotations

import random
from datetime import timedelta

import pytest
from ats.contracts.domain.types import DataQualityState
from ats.market.history import (
    HistoricalTruthErrorCode,
    require_available,
    validate_market_history,
    visible_observations,
)

from tests.unit.market.history.fixtures import (
    SESSION_START,
    bar_event_time,
    build_test_dataset,
    make_bar_observation,
    make_option_quote_observation,
    scenario_normal_series,
    scenario_revised_pair,
)

CODE = HistoricalTruthErrorCode


@pytest.mark.parametrize("repetition", range(8))
def test_dataset_construction_is_fully_deterministic(repetition: int) -> None:
    del repetition
    left = build_test_dataset(scenario_normal_series(4))
    right = build_test_dataset(scenario_normal_series(4))
    assert left.manifest.model_dump_json() == right.manifest.model_dump_json()
    assert left.model_dump_json() == right.model_dump_json()


@pytest.mark.parametrize("seed", range(10))
def test_dataset_identity_is_invariant_under_input_permutation(seed: int) -> None:
    records = list(
        (*scenario_normal_series(5), make_option_quote_observation(event_time=SESSION_START))
    )
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    baseline = build_test_dataset(tuple(records))
    permuted = build_test_dataset(tuple(shuffled))
    assert baseline.manifest.dataset_id == permuted.manifest.dataset_id
    assert baseline.manifest.payload_hash == permuted.manifest.payload_hash
    assert baseline.observations == permuted.observations


@pytest.mark.parametrize("repetition", range(4))
def test_validation_report_is_order_invariant(repetition: int) -> None:
    del repetition
    original, revision = scenario_revised_pair()
    forward = validate_market_history((original, revision))
    backward = validate_market_history((revision, original))
    assert forward.model_dump_json() == backward.model_dump_json()


def test_visible_window_grows_monotonically_with_decision_time() -> None:
    records = scenario_normal_series(6)
    boundaries = sorted({item.times.available_to_strategy_time for item in records})
    previous_count = 0
    previous_visible: tuple = ()
    for index, boundary in enumerate(boundaries):
        visible = visible_observations(records, at_time=boundary)
        assert len(visible) >= previous_count
        assert all(item.times.available_to_strategy_time <= boundary for item in visible)
        for earlier_item in previous_visible:
            assert earlier_item in visible
        if index < len(boundaries) - 1:
            next_boundary = boundaries[index + 1]
            grown = visible_observations(records, at_time=next_boundary)
            assert len(grown) > len(visible)
        previous_count = len(visible)
        previous_visible = visible


def test_every_admitted_record_satisfies_the_as_of_rule() -> None:
    records = (*scenario_normal_series(4), make_option_quote_observation(event_time=SESSION_START))
    decision_times = [
        SESSION_START + timedelta(seconds=offset) for offset in range(0, 1900, 250)
    ]
    for decision_time in decision_times:
        for observation in visible_observations(records, at_time=decision_time):
            assert observation.times.available_to_strategy_time <= decision_time
            assert (
                require_available(observation, at_time=decision_time) is observation
            )


def test_revision_resolution_is_deterministic_at_every_instant() -> None:
    original, revision = scenario_revised_pair()
    switch = revision.times.available_to_strategy_time
    probe_times = (
        original.times.available_to_strategy_time - timedelta(milliseconds=500),
        original.times.available_to_strategy_time,
        switch - timedelta(milliseconds=1),
        switch,
    )
    left_results = [
        [item.observation_id for item in visible_observations((original, revision), at_time=t)]
        for t in probe_times
    ]
    right_results = [
        [item.observation_id for item in visible_observations((revision, original), at_time=t)]
        for t in reversed(probe_times)
    ]
    assert left_results == list(reversed(right_results))


_MUTATIONS = {
    "availability_before_ingest": lambda obs: obs.model_copy(
        update={
            "times": obs.times.model_copy(
                update={"available_to_strategy_time": obs.times.event_time}
            )
        }
    ),
    "tampered_payload_hash": lambda obs: obs.model_copy(update={"payload_hash": "e" * 64}),
    "flipped_quality_state": lambda obs: obs.model_copy(
        update={"quality_state": DataQualityState.UNKNOWN}
    ),
}


@pytest.mark.parametrize("mutation_name", sorted(_MUTATIONS))
def test_tampered_records_are_always_detected(mutation_name: str) -> None:
    mutate = _MUTATIONS[mutation_name]
    base = make_bar_observation(sequence=3)
    tampered = mutate(base)
    report = validate_market_history((tampered,))
    invalid_codes = {
        item.code for item in report.findings if item.quality_state is DataQualityState.INVALID
    }
    assert invalid_codes, f"mutation {mutation_name} was not detected"


def test_missing_interval_property_holds_for_any_dropped_interior_bar() -> None:
    for dropped in range(1, 5):
        series = list(scenario_normal_series(6))
        del series[dropped]
        report = validate_market_history(tuple(series))
        assert any(item.code is CODE.MISSING_INTERVAL for item in report.findings)
    edges = list(scenario_normal_series(6))
    for edge_drop in (0, len(edges) - 1):
        trimmed = [item for index, item in enumerate(edges) if index != edge_drop]
        report = validate_market_history(tuple(trimmed))
        assert not any(item.code is CODE.MISSING_INTERVAL for item in report.findings)


def test_future_information_never_enters_earlier_windows() -> None:
    records = scenario_normal_series(5)
    last_event = bar_event_time(5)
    future_quote = make_option_quote_observation(event_time=last_event + timedelta(minutes=60))
    all_records = (*records, future_quote)
    for decision_time in [bar_event_time(index) for index in range(1, 6)]:
        visible = visible_observations(all_records, at_time=decision_time)
        visible_ids = {item.observation_id for item in visible}
        assert future_quote.observation_id not in visible_ids
