"""Deterministic selection of symmetric CE/PE pairs from actual listed contracts."""

from __future__ import annotations

from datetime import timedelta, timezone
from decimal import Decimal

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.types import PositiveDecimal
from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.normalization import NormalizedDerivativeContract

from .models import (
    ActiveOptionPair,
    ActiveOptionWindow,
    ActiveWindowError,
    ActiveWindowErrorCode,
    ActiveWindowPolicy,
)

_IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def build_active_option_window(
    *,
    contracts: tuple[NormalizedDerivativeContract, ...],
    underlying: DerivativeUnderlying,
    underlying_price: PositiveDecimal,
    as_of_time: UTCDateTime,
    policy: ActiveWindowPolicy,
) -> ActiveOptionWindow:
    if as_of_time.tzinfo is None or as_of_time.utcoffset() is None:
        raise ValueError("as_of_time must be timezone-aware")
    if (
        not isinstance(underlying_price, Decimal)
        or not underlying_price.is_finite()
        or underlying_price <= 0
    ):
        raise ValueError("underlying_price must be a positive finite Decimal")
    local_date = as_of_time.astimezone(_IST).date()
    if policy.expiry < local_date.isoformat():
        raise ActiveWindowError(ActiveWindowErrorCode.EXPIRY_NOT_ELIGIBLE)
    candidates = tuple(
        item
        for item in contracts
        if item.underlying is underlying
        and item.instrument_type is DerivativeInstrumentType.OPTIDX
        and item.expiry == policy.expiry
        and item.tradable
    )
    if not candidates:
        raise ActiveWindowError(ActiveWindowErrorCode.EXPIRY_NOT_ELIGIBLE)
    maximum_age = max(as_of_time - item.source_as_of for item in candidates)
    if maximum_age.total_seconds() * 1000 > policy.maximum_master_age_ms:
        raise ActiveWindowError(ActiveWindowErrorCode.CONTRACT_MASTER_STALE)
    if any(item.source_as_of > as_of_time for item in candidates):
        raise ActiveWindowError(ActiveWindowErrorCode.TIMESTAMP_REGRESSION)

    by_strike: dict[Decimal, dict[OptionType, NormalizedDerivativeContract]] = {}
    for item in candidates:
        if item.strike is None or item.option_type is None:
            continue
        sides = by_strike.setdefault(item.strike, {})
        if item.option_type in sides:
            raise ActiveWindowError(ActiveWindowErrorCode.DUPLICATE_CONTRACT_SIDE)
        sides[item.option_type] = item
    paired_strikes = sorted(
        strike
        for strike, sides in by_strike.items()
        if OptionType.CE in sides and OptionType.PE in sides
    )
    required = policy.window_size * 2 + 1
    if len(paired_strikes) < required:
        raise ActiveWindowError(ActiveWindowErrorCode.INSUFFICIENT_PAIRED_STRIKES)
    atm_strike = min(paired_strikes, key=lambda strike: (abs(strike - underlying_price), strike))
    atm_index = paired_strikes.index(atm_strike)
    start = atm_index - policy.window_size
    end = atm_index + policy.window_size + 1
    if start < 0 or end > len(paired_strikes):
        raise ActiveWindowError(ActiveWindowErrorCode.INSUFFICIENT_PAIRED_STRIKES)
    selected = paired_strikes[start:end]
    pairs = tuple(
        ActiveOptionPair(
            strike=strike,
            ce_contract_id=by_strike[strike][OptionType.CE].instrument_id,
            pe_contract_id=by_strike[strike][OptionType.PE].instrument_id,
            ce_provider_instrument_key=by_strike[strike][OptionType.CE].provider_instrument_key,
            pe_provider_instrument_key=by_strike[strike][OptionType.PE].provider_instrument_key,
        )
        for strike in selected
    )
    values = {
        "schema_version": "1.0",
        "underlying": underlying,
        "expiry": policy.expiry,
        "underlying_price": underlying_price,
        "atm_strike": atm_strike,
        "as_of_time": as_of_time,
        "window_size": policy.window_size,
        "pairs": pairs,
    }
    return ActiveOptionWindow.model_validate({**values, "payload_hash": canonical_sha256(values)})


__all__ = ["build_active_option_window"]
