"""Per-instrument and timeframe-scoped validation policy overrides."""

from __future__ import annotations

from datetime import UTC, datetime

from ats.market.history import (
    HistoricalTruthErrorCode,
    HistoryValidationPolicy,
    InstrumentPolicyOverride,
    validate_market_history,
)

from tests.unit.market.history.fixtures import make_bar_observation


def _same_bar_record(instrument: str):
    return make_bar_observation(
        sequence=1,
        instrument=instrument,
        event_time=datetime(2024, 6, 3, 3, 45, tzinfo=UTC),
        source_lag_ms=0,
        ingest_lag_ms=0,
        availability_lag_ms=0,
    )


def _stale_record(instrument: str):
    return make_bar_observation(
        sequence=1,
        instrument=instrument,
        availability_lag_ms=1_200_000,
    )


def test_override_relaxes_only_target_instrument() -> None:
    policy = HistoryValidationPolicy(
        instrument_overrides=(
            InstrumentPolicyOverride(
                instrument="RELIANCE",
                bar_minimum_availability_delay_ms=0,
            ),
        )
    )
    records = (_same_bar_record("RELIANCE"), _same_bar_record("TCS"))
    report = validate_market_history(records, policy=policy)
    by_code = {
        finding.code: finding.observation_id for finding in report.findings
    }
    assert HistoricalTruthErrorCode.UNREALISTIC_SAME_BAR_AVAILABILITY in by_code
    flagged_id = by_code[HistoricalTruthErrorCode.UNREALISTIC_SAME_BAR_AVAILABILITY]
    assert str(flagged_id) == str(records[1].observation_id)


def test_timeframe_scoped_override_applies_only_to_matching_bars() -> None:
    policy = HistoryValidationPolicy(
        instrument_overrides=(
            InstrumentPolicyOverride(
                instrument="RELIANCE",
                timeframe="5m",
                bar_maximum_source_lag_ms=2_000_000,
            ),
        )
    )
    report = validate_market_history((_stale_record("RELIANCE"),), policy=policy)
    assert not any(
        finding.code is HistoricalTruthErrorCode.STALE_OBSERVATION
        for finding in report.findings
    )
    other_timeframe = HistoryValidationPolicy(
        instrument_overrides=(
            InstrumentPolicyOverride(
                instrument="RELIANCE",
                timeframe="1m",
                bar_maximum_source_lag_ms=2_000_000,
            ),
        )
    )
    strict_report = validate_market_history(
        (_stale_record("RELIANCE"),), policy=other_timeframe
    )
    assert any(
        finding.code is HistoricalTruthErrorCode.STALE_OBSERVATION
        for finding in strict_report.findings
    )


def test_override_cannot_relax_quote_or_event_kinds() -> None:
    from tests.unit.market.history.fixtures import make_option_quote_observation

    policy = HistoryValidationPolicy(
        instrument_overrides=(
            InstrumentPolicyOverride(
                instrument="NIFTY",
                bar_minimum_availability_delay_ms=0,
                bar_maximum_source_lag_ms=999_999_999,
            ),
        )
    )
    quote = make_option_quote_observation(
        event_time=datetime(2024, 6, 3, 9, 15, tzinfo=UTC),
        availability_lag_ms=20_000,
    )
    report = validate_market_history((quote,), policy=policy)
    assert any(
        finding.code is HistoricalTruthErrorCode.STALE_OBSERVATION
        for finding in report.findings
    )
