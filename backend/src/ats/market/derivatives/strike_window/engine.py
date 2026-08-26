"""Deterministic ATM-centered strike-window selection from the canonical master.

The engine uses only strikes actually listed in the supplied contract master:
strike spacing is never assumed, missing sides are surfaced as evidence instead
of being interpolated, and an incomplete bounded universe fails closed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import PositiveDecimal
from ats.market.calendar import SessionCalendar
from ats.market.derivatives.contract_master import (
    ContractMaster,
    DerivativeInstrument,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    classify_expiry,
    parse_expiry_date,
    validate_master_for_use,
)
from ats.market.derivatives.contract_master.errors import ContractMasterError

from .errors import StrikeWindowError, StrikeWindowErrorCode
from .models import (
    PairedStrike,
    StrikeLeg,
    StrikeWindowPlan,
    StrikeWindowPolicy,
    UnpairedStrikeEvidence,
)


def build_strike_window(
    contract_master: ContractMaster,
    *,
    underlying: DerivativeUnderlying,
    underlying_price: PositiveDecimal,
    policy: StrikeWindowPolicy,
    evaluation_time: UTCDateTime,
    calendar: SessionCalendar | None = None,
) -> StrikeWindowPlan:
    if not isinstance(underlying_price, Decimal) or not underlying_price.is_finite():
        raise ValueError("underlying_price must be a finite Decimal")
    if underlying_price <= 0:
        raise ValueError("underlying_price must be positive")
    try:
        validate_master_for_use(
            contract_master,
            evaluation_time=evaluation_time,
            maximum_age_ms=policy.maximum_master_age_ms,
        )
    except ContractMasterError as exc:
        raise StrikeWindowError(
            StrikeWindowErrorCode.MASTER_VALIDATION_FAILED,
            f"contract master rejected: {exc.code.value}",
        ) from exc
    if classify_expiry(expiry=policy.expiry, evaluation_time=evaluation_time).value == "EXPIRED":
        raise StrikeWindowError(
            StrikeWindowErrorCode.EXPIRED_WINDOW,
            f"{policy.expiry} is expired at evaluation time",
        )

    by_strike: dict[Decimal, dict[OptionType, DerivativeInstrument]] = {}
    for instrument in contract_master.instruments:
        if (
            instrument.underlying is not underlying
            or instrument.instrument_type is not DerivativeInstrumentType.OPTIDX
            or instrument.expiry != policy.expiry
            or not instrument.tradable
            or instrument.strike is None
            or instrument.option_type is None
        ):
            continue
        sides = by_strike.setdefault(instrument.strike, {})
        if instrument.option_type in sides:
            raise StrikeWindowError(
                StrikeWindowErrorCode.DUPLICATE_CONTRACT_SIDE,
                f"duplicate {instrument.option_type.value} listing at strike {instrument.strike}",
            )
        sides[instrument.option_type] = instrument

    if not by_strike:
        raise StrikeWindowError(
            StrikeWindowErrorCode.NO_LISTED_STRIKES,
            f"no listed {underlying.value} OPTIDX strikes for expiry {policy.expiry}",
        )

    paired: list[PairedStrike] = []
    unpaired: list[UnpairedStrikeEvidence] = []
    for strike in sorted(by_strike):
        sides = by_strike[strike]
        ce = sides.get(OptionType.CE)
        pe = sides.get(OptionType.PE)
        if ce is not None and pe is not None:
            paired.append(PairedStrike(strike=strike, ce=_leg(ce), pe=_leg(pe)))
        else:
            unpaired.append(
                UnpairedStrikeEvidence(strike=strike, missing_side="CE" if ce is None else "PE")
            )

    required = policy.window_size * 2 + 1
    if len(paired) < required:
        raise StrikeWindowError(
            StrikeWindowErrorCode.INSUFFICIENT_PAIRED_STRIKES,
            f"listed paired strikes {len(paired)} < required {required}; "
            f"unpaired evidence {len(unpaired)}",
        )

    atm_strike = min(paired, key=lambda item: (abs(item.strike - underlying_price), item.strike))
    atm_index = paired.index(atm_strike)
    selected = tuple(paired[atm_index - policy.window_size : atm_index + policy.window_size + 1])
    calendar_trading_day = (
        None
        if calendar is None
        else _as_date(policy.expiry) in frozenset(calendar.trading_dates)
    )
    values: dict[str, object] = {
        "schema_version": "1.0",
        "underlying_price": underlying_price,
        "atm_strike": atm_strike.strike,
        "expiry": policy.expiry,
        "window_size": policy.window_size,
        "as_of_time": evaluation_time,
        "calendar_trading_day": calendar_trading_day,
        "strikes": selected,
        "unpaired_evidence": tuple(unpaired),
    }
    plan = StrikeWindowPlan.model_validate({**values, "payload_hash": "0" * 64})
    return plan.model_copy(update={"payload_hash": compute_payload_hash(plan)})


def _leg(instrument: DerivativeInstrument) -> StrikeLeg:
    assert instrument.strike is not None and instrument.option_type is not None
    return StrikeLeg(
        instrument_id=instrument.instrument_id,
        trading_symbol=instrument.trading_symbol,
        lot_size=instrument.lot_size,
        quantity_freeze_limit=instrument.quantity_freeze_limit,
        tick_size=instrument.tick_size,
    )


def _as_date(expiry: str) -> date:
    return parse_expiry_date(expiry)


__all__ = ["build_strike_window"]
