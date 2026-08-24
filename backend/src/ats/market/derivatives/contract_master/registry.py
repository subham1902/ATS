"""Pure freshness and lookup operations over a normalized contract master."""

from __future__ import annotations

from datetime import date, timedelta

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash

from .errors import ContractMasterError, ContractMasterErrorCode
from .models import (
    ContractMaster,
    DerivativeInstrument,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)


def validate_master_for_use(
    master: ContractMaster, *, evaluation_time: UTCDateTime, maximum_age_ms: int
) -> None:
    """Fail closed for tampering, future-dated evidence, or stale reference data."""

    if maximum_age_ms <= 0 or isinstance(maximum_age_ms, bool):
        raise ValueError("maximum_age_ms must be a positive integer")
    if compute_payload_hash(master) != master.payload_hash:
        raise ContractMasterError(
            ContractMasterErrorCode.PAYLOAD_HASH_MISMATCH,
            "normalized master payload was modified",
        )
    if master.manifest.as_of_time > evaluation_time:
        raise ContractMasterError(
            ContractMasterErrorCode.FUTURE_MASTER,
            "reference data is newer than evaluation time",
        )
    if evaluation_time - master.manifest.as_of_time > timedelta(milliseconds=maximum_age_ms):
        raise ContractMasterError(
            ContractMasterErrorCode.STALE_MASTER,
            "reference data exceeded configured maximum age",
        )


def select_tradable_contracts(
    master: ContractMaster,
    *,
    evaluation_time: UTCDateTime,
    maximum_age_ms: int,
    underlying: DerivativeUnderlying,
    instrument_type: DerivativeInstrumentType,
    option_type: OptionType | None = None,
) -> tuple[DerivativeInstrument, ...]:
    """Return deterministic eligible contracts without deriving exchange rules."""

    validate_master_for_use(
        master,
        evaluation_time=evaluation_time,
        maximum_age_ms=maximum_age_ms,
    )
    if instrument_type is DerivativeInstrumentType.FUTIDX and option_type is not None:
        raise ValueError("FUTIDX query cannot specify option_type")
    return tuple(
        instrument
        for instrument in master.instruments
        if instrument.underlying is underlying
        and instrument.instrument_type is instrument_type
        and (option_type is None or instrument.option_type is option_type)
        and instrument.tradable
        and date.fromisoformat(instrument.expiry) >= evaluation_time.date()
    )


__all__ = ["select_tradable_contracts", "validate_master_for_use"]
