from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ats.market.calendar import SessionCalendar
from ats.market.derivatives.contract_master import (
    ContractMasterError,
    ContractMasterErrorCode,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    ExpiryLifecycle,
    OptionType,
    available_expiries,
    calendar_trading_day,
    classify_expiry,
    parse_expiry_date,
    select_explicit_expiry,
    select_nearest_expiry,
    select_next_expiry,
)

from . import expiry_helpers as fix

T0 = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
AFTER_WEEKLY = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)
ALL_EXPIRED = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
MAX_AGE_MS = 14 * 86_400_000


def calendar(*dates: object) -> SessionCalendar:
    from datetime import time

    return SessionCalendar(
        calendar_id="TEST_ONLY_D08_CALENDAR",
        calendar_version="1.0.0-test",
        timezone="Asia/Kolkata",
        trading_dates=tuple(dates),  # type: ignore[arg-type]
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )


class TestAvailableExpiries:
    def test_unique_sorted_expiries_from_actual_master(self) -> None:
        expiries = available_expiries(
            fix.master(),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert expiries == ("2026-08-25", "2026-09-01", "2026-09-29", "2026-10-27")

    def test_option_type_filter_uses_only_listed_contracts(self) -> None:
        rows = (fix.opt_row("25000", "CE", "2026-08-27", instrument_id="C1"),)
        expiries = available_expiries(
            fix.master(rows),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            option_type=OptionType.CE,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert expiries == ("2026-08-27",)

    def test_non_tradable_expiries_are_excluded(self) -> None:
        rows = (
            fix.opt_row("25000", "CE", "2026-08-25", instrument_id="E1C"),
            fix.opt_row("25000", "PE", "2026-08-25", instrument_id="E1P"),
            fix.opt_row("25000", "CE", "2026-09-01", instrument_id="W1C", tradable="FALSE"),
            fix.opt_row("25000", "PE", "2026-09-01", instrument_id="W1P", tradable="FALSE"),
        )
        expiries = available_expiries(
            fix.master(rows),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert expiries == ("2026-08-25",)

    def test_futidx_query_cannot_carry_option_type(self) -> None:
        with pytest.raises(ValueError):
            available_expiries(
                fix.master(),
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.FUTIDX,
                option_type=OptionType.CE,
                evaluation_time=T0,
                maximum_age_ms=MAX_AGE_MS,
            )

    def test_stale_master_fails_closed(self) -> None:
        late = datetime(2026, 8, 24, 4, 0, 1, tzinfo=UTC)
        with pytest.raises(ContractMasterError) as error:
            available_expiries(
                fix.master(),
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                evaluation_time=late,
                maximum_age_ms=1,
            )
        assert error.value.code is ContractMasterErrorCode.STALE_MASTER


class TestClassification:
    @pytest.mark.parametrize(
        ("expiry", "expected"),
        [
            ("2026-08-25", ExpiryLifecycle.ACTIVE),
            ("2026-08-24", ExpiryLifecycle.ACTIVE),
            ("2026-08-23", ExpiryLifecycle.EXPIRED),
        ],
    )
    def test_classification_against_evaluation_date(
        self, expiry: str, expected: ExpiryLifecycle
    ) -> None:
        assert classify_expiry(expiry=expiry, evaluation_time=T0) is expected

    def test_malformed_expiry_fails_closed(self) -> None:
        for malformed in ("2026-9-1", "26-09-01", "not-a-date", ""):
            with pytest.raises(ContractMasterError) as error:
                parse_expiry_date(malformed)
            assert error.value.code is ContractMasterErrorCode.MALFORMED_EXPIRY


class TestNearestAndNext:
    def test_nearest_is_earliest_active_listed_expiry(self) -> None:
        selection = select_nearest_expiry(
            fix.master(),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert selection.expiry == "2026-08-25"
        assert selection.lifecycle is ExpiryLifecycle.ACTIVE

    def test_expired_listing_is_skipped_not_resynthesized(self) -> None:
        selection = select_nearest_expiry(
            fix.master(),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=AFTER_WEEKLY,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert selection.expiry == "2026-09-01"

    def test_no_active_expiry_fails_closed(self) -> None:
        with pytest.raises(ContractMasterError) as error:
            select_nearest_expiry(
                fix.master(),
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                evaluation_time=ALL_EXPIRED,
                maximum_age_ms=90 * 86_400_000,
            )
        assert error.value.code is ContractMasterErrorCode.NO_ACTIVE_EXPIRY

    def test_next_expiry_strictly_after_anchor(self) -> None:
        selection = select_next_expiry(
            fix.master(),
            anchor_expiry="2026-09-29",
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert selection.expiry == "2026-10-27"

    def test_next_expiry_without_successor_fails_closed(self) -> None:
        with pytest.raises(ContractMasterError) as error:
            select_next_expiry(
                fix.master(),
                anchor_expiry="2026-10-27",
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                evaluation_time=T0,
                maximum_age_ms=MAX_AGE_MS,
            )
        assert error.value.code is ContractMasterErrorCode.EXPIRY_NOT_AFTER_ANCHOR


class TestExplicitSelection:
    def test_explicit_expiry_present_in_master(self) -> None:
        selection = select_explicit_expiry(
            fix.master(),
            requested_expiry="2026-09-29",
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert selection.expiry == "2026-09-29"

    def test_unlisted_expiry_is_refused_never_invented(self) -> None:
        with pytest.raises(ContractMasterError) as error:
            select_explicit_expiry(
                fix.master(),
                requested_expiry="2026-12-31",
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                evaluation_time=T0,
                maximum_age_ms=MAX_AGE_MS,
            )
        assert error.value.code is ContractMasterErrorCode.EXPIRY_NOT_AVAILABLE

    def test_malformed_requested_expiry_fails_closed(self) -> None:
        with pytest.raises(ContractMasterError) as error:
            select_explicit_expiry(
                fix.master(),
                requested_expiry="2026-9-29",
                underlying=DerivativeUnderlying.NIFTY,
                instrument_type=DerivativeInstrumentType.OPTIDX,
                evaluation_time=T0,
                maximum_age_ms=MAX_AGE_MS,
            )
        assert error.value.code is ContractMasterErrorCode.MALFORMED_EXPIRY


class TestHolidayAdjustedSourceExpiry:
    def test_calendar_trading_day_flag(self) -> None:
        session = calendar(datetime(2026, 9, 1).date(), datetime(2026, 10, 27).date())
        assert calendar_trading_day("2026-09-01", session) is True
        assert calendar_trading_day("2026-09-29", session) is False
        assert calendar_trading_day("2026-09-29", None) is None

    def test_holiday_adjusted_expiry_is_kept_exactly_as_supplied(self) -> None:
        session = calendar(datetime(2026, 9, 3).date())
        selection = select_explicit_expiry(
            fix.master(),
            requested_expiry="2026-09-01",
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
            calendar=session,
        )
        assert selection.expiry == "2026-09-01"
        assert selection.calendar_trading_day is False


class TestDeterminism:
    def test_repeated_selection_is_identical(self) -> None:
        first = select_nearest_expiry(
            fix.master(),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            option_type=OptionType.CE,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        second = select_nearest_expiry(
            fix.master(),
            underlying=DerivativeUnderlying.NIFTY,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            option_type=OptionType.CE,
            evaluation_time=T0,
            maximum_age_ms=MAX_AGE_MS,
        )
        assert first == second
