"""Strict immutable derivative contract-master models."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, StringConstraints, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveDecimal, PositiveInt, Sha256
from ats.contracts.enums import ATSStringEnum
from ats.contracts.intelligence.types import RegisteredCode


class DerivativeUnderlying(ATSStringEnum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"


class DerivativeInstrumentType(ATSStringEnum):
    OPTIDX = "OPTIDX"
    FUTIDX = "FUTIDX"


class OptionType(ATSStringEnum):
    CE = "CE"
    PE = "PE"


def _valid_expiry(value: str) -> str:
    date.fromisoformat(value)
    return value


ExpiryDate = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    AfterValidator(_valid_expiry),
]


class DerivativeInstrument(ATSBaseModel):
    """One normalized exchange contract; all authority values come from source data."""

    exchange: RegisteredCode
    segment: RegisteredCode
    underlying: DerivativeUnderlying
    instrument_type: DerivativeInstrumentType
    trading_symbol: NonEmptyStr
    instrument_id: RegisteredCode
    expiry: ExpiryDate
    strike: PositiveDecimal | None
    option_type: OptionType | None
    lot_size: PositiveInt
    tick_size: PositiveDecimal
    quantity_freeze_limit: PositiveInt | None
    tradable: bool
    contract_version: NonEmptyStr
    source: NonEmptyStr
    as_of_time: UTCDateTime

    @model_validator(mode="after")
    def validate_instrument_shape(self) -> DerivativeInstrument:
        if self.exchange != "NSE":
            raise ValueError("current derivative scope accepts NSE contracts only")
        if self.instrument_type is DerivativeInstrumentType.OPTIDX:
            if self.strike is None or self.option_type is None:
                raise ValueError("OPTIDX requires strike and option_type")
        elif self.strike is not None or self.option_type is not None:
            raise ValueError("FUTIDX must not contain option strike/type")
        if self.tradable and date.fromisoformat(self.expiry) < self.as_of_time.date():
            raise ValueError("expired contract cannot be marked tradable")
        return self

    def semantic_key(self) -> tuple[object, ...]:
        return (
            self.exchange,
            self.segment,
            self.underlying,
            self.instrument_type,
            self.expiry,
            self.strike,
            self.option_type,
        )


class ContractMasterManifest(ATSBaseModel):
    """Caller-supplied integrity and provenance for one authoritative export."""

    schema_version: Literal["1.0"]
    master_id: UUID
    master_version: NonEmptyStr
    source: NonEmptyStr
    as_of_time: UTCDateTime
    row_count: PositiveInt
    content_sha256: Sha256


class ContractMaster(ATSBaseModel):
    """Deterministically ordered normalized contract-master evidence."""

    schema_version: Literal["1.0"]
    manifest: ContractMasterManifest
    instruments: tuple[DerivativeInstrument, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_inventory(self) -> ContractMaster:
        if len(self.instruments) != self.manifest.row_count:
            raise ValueError("instrument count must equal manifest row_count")
        if not self.instruments:
            raise ValueError("contract master must be non-empty")
        return self


__all__ = [
    "ContractMaster",
    "ContractMasterManifest",
    "DerivativeInstrument",
    "DerivativeInstrumentType",
    "DerivativeUnderlying",
    "OptionType",
]
