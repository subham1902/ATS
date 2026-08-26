from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market.calendar import SessionCalendar
from ats.market.derivatives.contract_master import (
    ContractMaster,
    DerivativeUnderlying,
)
from ats.market.derivatives.strike_window import (
    PairedStrike,
    StrikeWindowError,
    StrikeWindowErrorCode,
    StrikeWindowPlan,
    build_strike_window,
)

from . import helpers as fix
from .helpers import EXPIRY, IRREGULAR_STRIKES, master, policy, rows_for

T0 = fix.AS_OF


def window(
    rows: tuple[bytes, ...] | None = None,
    *,
    underlying_price: str = "25010",
    window_size: int = 2,
    evaluation_time: datetime = T0,
    calendar: SessionCalendar | None = None,
) -> StrikeWindowPlan:
    return build_strike_window(
        master(rows if rows is not None else rows_for(IRREGULAR_STRIKES)),
        underlying=DerivativeUnderlying.NIFTY,
        underlying_price=Decimal(underlying_price),
        policy=policy(window_size),
        evaluation_time=evaluation_time,
        calendar=calendar,
    )


class TestAtmSelection:
    def test_atm_is_nearest_listed_paired_strike(self) -> None:
        plan = window()
        assert plan.atm_strike == Decimal("25000")

    def test_atm_tie_breaks_to_lower_listed_strike(self) -> None:
        plan = window(underlying_price="25025")
        assert plan.atm_strike == Decimal("25000")

    def test_window_is_exactly_atm_plus_minus_n(self) -> None:
        plan = window(window_size=2)
        assert [str(item.strike) for item in plan.strikes] == [
            "24500",
            "24750",
            "25000",
            "25050",
            "25300",
        ]

    def test_window_never_assumes_regular_spacing(self) -> None:
        """Listed strikes 24750/25000/25050 are irregular and must be used as-is."""

        plan = window(underlying_price="24990", window_size=1)
        assert [str(item.strike) for item in plan.strikes] == ["24750", "25000", "25050"]


class TestMoneynessOrdering:
    def test_ce_itm_strikes_are_below_reference(self) -> None:
        plan = window()
        ordering = dict(plan.moneyness_ordering_ce())
        assert ordering[Decimal("24750")] == "ITM"
        assert ordering[Decimal("25000")] == "ITM"
        assert ordering[Decimal("25050")] == "OTM"

    def test_pe_itm_strikes_are_above_reference(self) -> None:
        plan = window()
        ordering = dict(plan.moneyness_ordering_pe())
        assert ordering[Decimal("25050")] == "ITM"
        assert ordering[Decimal("24750")] == "OTM"

    def test_atm_first_traversal_starts_at_selected_atm(self) -> None:
        plan = window(window_size=2)
        first = plan.moneyness_ordering_ce()[0][0]
        assert first == plan.atm_strike


class TestPairingAndEvidence:
    def test_missing_side_becomes_explicit_evidence(self) -> None:
        rows = (
            fix.opt_row("24750", "CE"),
            fix.opt_row("24750", "PE"),
            fix.opt_row("25000", "CE"),
            fix.opt_row("25000", "PE"),
            fix.opt_row("25050", "CE"),
            fix.opt_row("25300", "PE"),
            fix.opt_row("25550", "CE"),
            fix.opt_row("25550", "PE"),
        )
        plan = window(rows=rows, window_size=1)
        evidence = {(item.strike, item.missing_side) for item in plan.unpaired_evidence}
        assert any(
            item.strike == Decimal("25050") and item.missing_side == "PE"
            for item in plan.unpaired_evidence
        )
        assert any(
            item.strike == Decimal("25300") and item.missing_side == "CE"
            for item in plan.unpaired_evidence
        )
        assert evidence

    def test_unpaired_strike_is_never_selected_into_window(self) -> None:
        rows = (
            fix.opt_row("24750", "CE"),
            fix.opt_row("24750", "PE"),
            fix.opt_row("25000", "CE"),
            fix.opt_row("25000", "PE"),
            fix.opt_row("25050", "CE"),
            fix.opt_row("25300", "CE"),
            fix.opt_row("25300", "PE"),
            fix.opt_row("25550", "CE"),
            fix.opt_row("25550", "PE"),
        )
        plan = window(rows=rows, window_size=1)
        assert all(item.strike != Decimal("25050") for item in plan.strikes)

    def test_insufficient_pairs_fail_closed(self) -> None:
        rows = (
            fix.opt_row("25000", "CE"),
            fix.opt_row("25000", "PE"),
            fix.opt_row("25050", "CE"),
            fix.opt_row("25050", "PE"),
        )
        with pytest.raises(StrikeWindowError) as error:
            window(rows=rows, window_size=2)
        assert error.value.code is StrikeWindowErrorCode.INSUFFICIENT_PAIRED_STRIKES

    def test_expiry_without_any_listing_fails_closed(self) -> None:
        from ats.market.derivatives.strike_window import StrikeWindowPolicy

        empty_expiry_policy = StrikeWindowPolicy(
            window_size=1,
            expiry="2026-09-01",
            maximum_master_age_ms=86_400_000,
        )
        other_expiry_rows = fix.rows_for(("25000",), expiry="2026-09-29")
        with pytest.raises(StrikeWindowError) as error:
            build_strike_window(
                master(other_expiry_rows),
                underlying=DerivativeUnderlying.NIFTY,
                underlying_price=Decimal("25010"),
                policy=empty_expiry_policy,
                evaluation_time=T0,
            )
        assert error.value.code is StrikeWindowErrorCode.NO_LISTED_STRIKES

    def test_duplicate_side_in_master_fails_closed(self) -> None:
        complete = master(fix.rows_for(("25000",)))
        instruments = tuple(complete.instruments) + (complete.instruments[0],)
        manifest_dump = complete.manifest.model_dump(mode="python")
        tampered = ContractMaster.model_validate(
            {
                "schema_version": "1.0",
                "manifest": {**manifest_dump, "row_count": len(instruments)},
                "instruments": instruments,
                "payload_hash": "0" * 64,
            }
        )
        tampered = tampered.model_copy(update={"payload_hash": compute_payload_hash(tampered)})
        with pytest.raises(StrikeWindowError) as error:
            build_strike_window(
                tampered,
                underlying=DerivativeUnderlying.NIFTY,
                underlying_price=Decimal("25010"),
                policy=policy(1),
                evaluation_time=T0,
            )
        assert error.value.code is StrikeWindowErrorCode.DUPLICATE_CONTRACT_SIDE


class TestPropagationAndSafety:
    def test_lot_freeze_and_tick_propagate_from_master(self) -> None:
        plan = window()
        atm = next(item for item in plan.strikes if item.strike == plan.atm_strike)
        assert isinstance(atm, PairedStrike)
        assert atm.ce.lot_size == 65
        assert atm.pe.lot_size == 65
        assert atm.ce.quantity_freeze_limit == 1800
        assert atm.ce.tick_size == Decimal("0.05")

    def test_expired_window_fails_closed(self) -> None:
        late = datetime(2026, 9, 2, 4, 0, tzinfo=UTC)
        expired_rows = fix.rows_for(("25000", "25050"), tradable="FALSE")
        with pytest.raises(StrikeWindowError) as error:
            build_strike_window(
                master(expired_rows, as_of=late),
                underlying=DerivativeUnderlying.NIFTY,
                underlying_price=Decimal("25010"),
                policy=policy(1),
                evaluation_time=late,
            )
        assert error.value.code is StrikeWindowErrorCode.EXPIRED_WINDOW

    def test_stale_master_maps_to_explicit_error(self) -> None:
        late = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)
        with pytest.raises(StrikeWindowError) as error:
            build_strike_window(
                master(rows_for(IRREGULAR_STRIKES), as_of=T0),
                underlying=DerivativeUnderlying.NIFTY,
                underlying_price=Decimal("25010"),
                policy=policy(1),
                evaluation_time=late,
            )
        assert error.value.code is StrikeWindowErrorCode.MASTER_VALIDATION_FAILED

    def test_calendar_flag_flows_through_without_moving_expiry(self) -> None:
        from datetime import date, time

        session = SessionCalendar(
            calendar_id="TEST_ONLY_D08_CALENDAR",
            calendar_version="1.0.0-test",
            timezone="Asia/Kolkata",
            trading_dates=(date(2026, 8, 24), date(2026, 9, 3)),
            preopen_start=time(9, 0),
            market_open=time(9, 15),
            market_close=time(15, 30),
            overrides=(),
        )
        plan = window(calendar=session)
        assert plan.expiry == EXPIRY
        assert plan.calendar_trading_day is False

    def test_invalid_underlying_price_rejected(self) -> None:
        with pytest.raises(ValueError):
            window(underlying_price="-5")


class TestDeterminism:
    def test_payload_hash_is_repeatable_and_sensitive(self) -> None:
        first = window()
        second = window()
        assert first.payload_hash == second.payload_hash
        expected = compute_payload_hash(first)
        assert first.payload_hash == expected
        shifted = window(underlying_price="25020")
        assert shifted.payload_hash != first.payload_hash

    def test_plan_survives_round_trip_serialization(self) -> None:
        plan = window()
        restored = StrikeWindowPlan.model_validate_json(plan.model_dump_json())
        assert restored == plan
