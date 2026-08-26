"""Unit tests for deterministic historical validation and classification."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from ats.contracts.domain.types import DataQualityState
from ats.market.history import (
    HistoricalTruthErrorCode,
    HistoryValidationPolicy,
    validate_market_history,
)

from tests.unit.market.history.fixtures import (
    SESSION_START,
    make_bar_observation,
    make_option_quote_observation,
    scenario_crossed_quote,
    scenario_duplicate_pair,
    scenario_future_leak,
    scenario_locked_quote,
    scenario_normal_series,
    scenario_revised_pair,
    scenario_stale_bar,
)

CODE = HistoricalTruthErrorCode


def codes(report) -> tuple[str, ...]:
    return tuple(item.code.value for item in report.findings)


def has_code(report, code: CODE) -> bool:
    return any(item.code is code for item in report.findings)


def test_valid_series_has_no_findings_and_good_state() -> None:
    report = validate_market_history(scenario_normal_series(5))
    assert report.findings == ()
    assert report.overall_quality_state is DataQualityState.GOOD
    assert report.evaluated_count == 5


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        validate_market_history(())


def test_bad_time_semantics_is_detected() -> None:
    report = validate_market_history((scenario_future_leak(),))
    assert has_code(report, CODE.BAD_TIME_SEMANTICS)
    assert report.overall_quality_state is DataQualityState.INVALID


def test_same_bar_availability_guard_uses_policy_delay() -> None:
    too_fast = make_bar_observation(
        sequence=1,
        source_lag_ms=100,
        ingest_lag_ms=500,
        availability_lag_ms=999,
    )
    report = validate_market_history((too_fast,))
    assert has_code(report, CODE.UNREALISTIC_SAME_BAR_AVAILABILITY)
    exact_minimum = make_bar_observation(sequence=1, availability_lag_ms=1_000)
    assert not has_code(
        validate_market_history((exact_minimum,)), CODE.UNREALISTIC_SAME_BAR_AVAILABILITY
    )


def test_quote_kind_allows_zero_availability_delay() -> None:
    quote = make_option_quote_observation(
        event_time=SESSION_START,
        source_lag_ms=0,
        ingest_lag_ms=0,
        availability_lag_ms=0,
    )
    report = validate_market_history((quote,))
    assert not has_code(report, CODE.UNREALISTIC_SAME_BAR_AVAILABILITY)
    assert report.overall_quality_state is DataQualityState.GOOD


def test_staleness_is_classified_degraded() -> None:
    report = validate_market_history((scenario_stale_bar(),))
    assert has_code(report, CODE.STALE_OBSERVATION)
    assert report.overall_quality_state is DataQualityState.DEGRADED


def test_missing_interval_is_detected_between_adjacent_bars() -> None:
    series = list(scenario_normal_series(4))
    del series[2]
    report = validate_market_history(tuple(series))
    assert has_code(report, CODE.MISSING_INTERVAL)
    assert report.overall_quality_state is DataQualityState.DEGRADED


def test_missing_interval_finding_carries_gap_boundaries() -> None:
    series = list(scenario_normal_series(3))
    del series[1]
    report = validate_market_history(tuple(series))
    finding = next(item for item in report.findings if item.code is CODE.MISSING_INTERVAL)
    assert "10 min" in finding.message or "600000" in finding.message or "300000" in finding.message


def test_custom_bar_interval_policy_suppresses_expected_gaps() -> None:
    policy = HistoryValidationPolicy(expected_bar_interval_ms=600_000)
    series = [make_bar_observation(sequence=index + 1) for index in (0, 2)]
    report = validate_market_history(tuple(series), policy=policy)
    assert not has_code(report, CODE.MISSING_INTERVAL)


def test_duplicate_identity_is_invalid() -> None:
    left, right = scenario_duplicate_pair()
    report = validate_market_history((left, right))
    assert has_code(report, CODE.DUPLICATE_OBSERVATION_IDENTITY)
    assert report.overall_quality_state is DataQualityState.INVALID


def test_conflicting_business_keys_without_revision_chain_rejected() -> None:
    first = make_bar_observation(sequence=1, close_price=Decimal("2918.50"))
    second = make_bar_observation(sequence=1, close_price=Decimal("2919.00"))
    report = validate_market_history((first, second))
    assert has_code(report, CODE.CONFLICTING_OBSERVATION_KEYS)


def test_valid_revision_chain_has_no_conflict() -> None:
    original, revision = scenario_revised_pair()
    report = validate_market_history((original, revision))
    assert not has_code(report, CODE.CONFLICTING_OBSERVATION_KEYS)
    assert report.overall_quality_state is DataQualityState.GOOD


def test_revision_ordering_violation_detected() -> None:
    original = make_bar_observation(sequence=1)
    early_revision = make_bar_observation(
        sequence=1,
        close_price=Decimal("2919.00"),
        availability_lag_ms=1_500,
        supersedes=original.observation_id,
    )
    report = validate_market_history((original, early_revision))
    assert has_code(report, CODE.REVISION_ORDER_INVALID)


def test_revision_identity_mismatch_detected() -> None:
    original = make_bar_observation(sequence=1)
    impostor = make_bar_observation(
        sequence=2,
        supersedes=original.observation_id,
    )
    report = validate_market_history((original, impostor))
    assert has_code(report, CODE.REVISION_IDENTITY_MISMATCH)


def test_missing_supersede_target_detected() -> None:
    orphan = make_bar_observation(
        sequence=1,
        supersedes=UUID("00000000-0000-0000-0000-000000000001"),
    )
    report = validate_market_history((orphan,))
    assert has_code(report, CODE.SUPERSEDED_TARGET_MISSING)


def test_crossed_and_locked_quotes_classified() -> None:
    crossed_report = validate_market_history((scenario_crossed_quote(),))
    assert has_code(crossed_report, CODE.CROSSED_QUOTE)
    assert crossed_report.overall_quality_state is DataQualityState.INVALID
    locked_report = validate_market_history((scenario_locked_quote(),))
    assert has_code(locked_report, CODE.LOCKED_QUOTE)
    assert locked_report.overall_quality_state is DataQualityState.GOOD


def test_expired_relationship_for_quotes_and_metadata() -> None:
    past_quote = make_option_quote_observation(
        event_time=SESSION_START + timedelta(days=40),
        expiry_date="2024-06-27",
    )
    report = validate_market_history((past_quote,))
    assert has_code(report, CODE.INVALID_EXPIRY_RELATIONSHIP)


def test_contract_universe_mismatch_detected() -> None:
    policy = HistoryValidationPolicy(contract_universe=("RELIANCE",))
    quote = make_option_quote_observation(event_time=SESSION_START)
    report = validate_market_history((quote,), policy=policy)
    assert has_code(report, CODE.CONTRACT_MISMATCH)
    assert report.overall_quality_state is DataQualityState.INVALID


def test_payload_hash_tampering_is_detected() -> None:
    observation = make_bar_observation(sequence=1).model_copy(update={"payload_hash": "e" * 64})
    report = validate_market_history((observation,))
    assert has_code(report, CODE.PAYLOAD_HASH_MISMATCH)


def test_report_is_deterministic_across_runs() -> None:
    records = (*scenario_normal_series(3), scenario_stale_bar())
    left = validate_market_history(records)
    right = validate_market_history(records)
    assert left.model_dump_json() == right.model_dump_json()
    ordered_codes = codes(left)
    assert ordered_codes == tuple(sorted(ordered_codes))


def test_worst_state_ranking() -> None:
    from ats.market.history.validation import worst_state

    assert (
        worst_state(DataQualityState.GOOD, DataQualityState.DEGRADED)
        is DataQualityState.DEGRADED
    )
    assert (
        worst_state(DataQualityState.DEGRADED, DataQualityState.UNKNOWN)
        is DataQualityState.UNKNOWN
    )
    assert (
        worst_state(DataQualityState.UNKNOWN, DataQualityState.INVALID)
        is DataQualityState.INVALID
    )
