"""Deterministic expiry selection from actual supplied contract metadata.

Every selected expiry originates from the normalized contract master. This
engine never synthesizes, interpolates, or holiday-shifts an expiry date: when
the exchange supplies a holiday-adjusted expiry it is surfaced exactly as
listed and flagged against an explicitly supplied calendar. Missing or
malformed metadata fails closed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.enums import ATSStringEnum
from ats.market.calendar import SessionCalendar

from .errors import ContractMasterError, ContractMasterErrorCode
from .models import (
    ContractMaster,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    ExpiryDate,
    OptionType,
)
from .registry import validate_master_for_use

_ISO_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ExpiryLifecycle(ATSStringEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class ExpirySelection(ATSBaseModel):
    """One deterministic expiry outcome with its source-derived classification."""

    schema_version: Literal["1.0"]
    underlying: DerivativeUnderlying
    instrument_type: DerivativeInstrumentType
    option_type: OptionType | None
    expiry: ExpiryDate
    lifecycle: ExpiryLifecycle
    calendar_trading_day: bool | None
    evaluated_at: UTCDateTime

    @model_validator(mode="after")
    def validate_expiry_text(self) -> ExpirySelection:
        _require_iso_date(self.expiry)
        return self


def parse_expiry_date(expiry: str) -> date:
    """Strictly parse a source-supplied ISO expiry; never adjust it."""

    _require_iso_date(expiry)
    try:
        return date.fromisoformat(expiry)
    except ValueError as exc:
        raise ContractMasterError(
            ContractMasterErrorCode.MALFORMED_EXPIRY, f"invalid expiry {expiry!r}"
        ) from exc


def classify_expiry(*, expiry: str, evaluation_time: UTCDateTime) -> ExpiryLifecycle:
    """Classify against the UTC evaluation date; expiry day stays active all IST session."""

    parsed = parse_expiry_date(expiry)
    if parsed < evaluation_time.date():
        return ExpiryLifecycle.EXPIRED
    return ExpiryLifecycle.ACTIVE


def calendar_trading_day(expiry: str, calendar: SessionCalendar | None) -> bool | None:
    """Report the supplied-calendar view of the source-provided expiry date.

    ``None`` means no calendar was supplied. A non-trading-day result is a
    flag on the source-provided date, never permission to move the date.
    """

    if calendar is None:
        return None
    return parse_expiry_date(expiry) in calendar.trading_dates


def available_expiries(
    master: ContractMaster,
    *,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None = None,
    evaluation_time: UTCDateTime,
    maximum_age_ms: int,
) -> tuple[str, ...]:
    """Unique ascending expiries actually listed for the requested contract family."""

    validate_master_for_use(
        master, evaluation_time=evaluation_time, maximum_age_ms=maximum_age_ms
    )
    if instrument_type is DerivativeInstrumentType.FUTIDX and option_type is not None:
        raise ValueError("FUTIDX query cannot specify option_type")
    expiries = {
        instrument.expiry
        for instrument in master.instruments
        if instrument.underlying is underlying
        and instrument.instrument_type is instrument_type
        and (option_type is None or instrument.option_type is option_type)
        and instrument.tradable
    }
    for expiry in expiries:
        parse_expiry_date(expiry)
    return tuple(sorted(expiries))


def select_nearest_expiry(
    master: ContractMaster,
    *,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None = None,
    evaluation_time: UTCDateTime,
    maximum_age_ms: int,
    calendar: SessionCalendar | None = None,
) -> ExpirySelection:
    """Earliest active expiry from actual listed contracts; fail closed when none exists."""

    expiries = available_expiries(
        master,
        underlying=underlying,
        instrument_type=instrument_type,
        option_type=option_type,
        evaluation_time=evaluation_time,
        maximum_age_ms=maximum_age_ms,
    )
    for expiry in expiries:
        lifecycle = classify_expiry(expiry=expiry, evaluation_time=evaluation_time)
        if lifecycle is ExpiryLifecycle.ACTIVE:
            return _selection(
                underlying=underlying,
                instrument_type=instrument_type,
                option_type=option_type,
                expiry=expiry,
                evaluation_time=evaluation_time,
                calendar=calendar,
            )
    raise ContractMasterError(
        ContractMasterErrorCode.NO_ACTIVE_EXPIRY,
        f"no active {underlying.value} {instrument_type.value} expiry is listed",
    )


def select_next_expiry(
    master: ContractMaster,
    *,
    anchor_expiry: str,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None = None,
    evaluation_time: UTCDateTime,
    maximum_age_ms: int,
    calendar: SessionCalendar | None = None,
) -> ExpirySelection:
    """Earliest active listed expiry strictly after the anchor; anchor need not be active."""

    parse_expiry_date(anchor_expiry)
    expiries = available_expiries(
        master,
        underlying=underlying,
        instrument_type=instrument_type,
        option_type=option_type,
        evaluation_time=evaluation_time,
        maximum_age_ms=maximum_age_ms,
    )
    for expiry in expiries:
        if (
            expiry > anchor_expiry
            and classify_expiry(expiry=expiry, evaluation_time=evaluation_time)
            is ExpiryLifecycle.ACTIVE
        ):
            return _selection(
                underlying=underlying,
                instrument_type=instrument_type,
                option_type=option_type,
                expiry=expiry,
                evaluation_time=evaluation_time,
                calendar=calendar,
            )
    raise ContractMasterError(
        ContractMasterErrorCode.EXPIRY_NOT_AFTER_ANCHOR,
        f"no active listed expiry after {anchor_expiry}",
    )


def select_explicit_expiry(
    master: ContractMaster,
    *,
    requested_expiry: str,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None = None,
    evaluation_time: UTCDateTime,
    maximum_age_ms: int,
    calendar: SessionCalendar | None = None,
) -> ExpirySelection:
    """Select only an expiry actually present in source data; never invent one."""

    parse_expiry_date(requested_expiry)
    expiries = available_expiries(
        master,
        underlying=underlying,
        instrument_type=instrument_type,
        option_type=option_type,
        evaluation_time=evaluation_time,
        maximum_age_ms=maximum_age_ms,
    )
    if requested_expiry not in expiries:
        raise ContractMasterError(
            ContractMasterErrorCode.EXPIRY_NOT_AVAILABLE,
            f"{requested_expiry} is not listed for {underlying.value} "
            f"{instrument_type.value} in the supplied master",
        )
    return _selection(
        underlying=underlying,
        instrument_type=instrument_type,
        option_type=option_type,
        expiry=requested_expiry,
        evaluation_time=evaluation_time,
        calendar=calendar,
    )


def _selection(
    *,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None,
    expiry: str,
    evaluation_time: UTCDateTime,
    calendar: SessionCalendar | None,
) -> ExpirySelection:
    return ExpirySelection(
        schema_version="1.0",
        underlying=underlying,
        instrument_type=instrument_type,
        option_type=option_type,
        expiry=expiry,
        lifecycle=classify_expiry(expiry=expiry, evaluation_time=evaluation_time),
        calendar_trading_day=calendar_trading_day(expiry, calendar),
        evaluated_at=evaluation_time,
    )


def _require_iso_date(expiry: str) -> None:
    if not isinstance(expiry, str) or _ISO_DATE.fullmatch(expiry) is None:
        raise ContractMasterError(
            ContractMasterErrorCode.MALFORMED_EXPIRY, f"expiry {expiry!r} is not ISO YYYY-MM-DD"
        )


__all__ = [
    "ExpiryLifecycle",
    "ExpirySelection",
    "available_expiries",
    "calendar_trading_day",
    "classify_expiry",
    "parse_expiry_date",
    "select_explicit_expiry",
    "select_nearest_expiry",
    "select_next_expiry",
]
