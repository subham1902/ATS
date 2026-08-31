"""AsOfTimeline equivalence, permutation invariance and dataset caching."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ats.market.history import AsOfTimeline, HistoricalDataset, visible_observations

from tests.unit.market.history.fixtures import (
    build_test_dataset,
    make_bar_observation,
    make_event_observation,
    make_option_quote_observation,
    scenario_normal_series,
)


def _reference_visible(observations, at_time):
    visible = [item for item in observations if item.times.available_to_strategy_time <= at_time]
    visible_ids = {item.observation_id for item in visible}
    superseded = {
        item.supersedes
        for item in visible
        if item.supersedes is not None and item.supersedes in visible_ids
    }
    effective = [item for item in visible if item.observation_id not in superseded]
    effective.sort(
        key=lambda item: (
            item.times.available_to_strategy_time,
            item.times.event_time,
            item.observation_id,
        )
    )
    return tuple(effective)


def _mixed_records():
    base = scenario_normal_series()
    revision = make_bar_observation(
        sequence=1,
        close_price=Decimal("2919.00"),
        availability_lag_ms=400_000,
        supersedes=base[0].observation_id,
    )
    quotes = tuple(
        make_option_quote_observation(
            event_time=datetime(2024, 6, 3, 3, 45, tzinfo=UTC) + timedelta(minutes=index)
        )
        for index in range(3)
    )
    event = make_event_observation(
        headline="RBI_POLICY_TEST_ONLY",
        event_time=datetime(2024, 6, 3, 4, 15, tzinfo=UTC),
        availability_lag_ms=90_000,
    )
    return (*base, revision, *quotes, event)


def _query_times(count: int = 12):
    base = datetime(2024, 6, 3, 3, 40, tzinfo=UTC)
    return [base + timedelta(seconds=37 * index) for index in range(count)]


def test_timeline_matches_naive_semantics_across_all_queries() -> None:
    records = _mixed_records()
    timeline = AsOfTimeline(records)
    for at_time in _query_times():
        assert timeline.visible(at_time) == _reference_visible(records, at_time)


def test_timeline_is_permutation_invariant() -> None:
    records = _mixed_records()
    shuffled = tuple(reversed(records))
    left = AsOfTimeline(records)
    right = AsOfTimeline(shuffled)
    for at_time in _query_times():
        assert left.visible(at_time) == right.visible(at_time)


def test_empty_timeline_returns_nothing() -> None:
    timeline: AsOfTimeline = AsOfTimeline(())
    assert timeline.visible(datetime(2024, 6, 3, 9, 0, tzinfo=UTC)) == ()


def test_dataset_visible_as_of_uses_cached_timeline_consistently() -> None:
    dataset: HistoricalDataset = build_test_dataset(_mixed_records())
    for at_time in _query_times():
        assert dataset.visible_as_of(at_time) == visible_observations(
            dataset.observations, at_time=at_time
        )
    assert dataset.timeline is dataset.timeline
