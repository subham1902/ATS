"""Strict D02 inputs and normalized provider-neutral derivative records."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveDecimal, PositiveInt, Sha256
from ats.contracts.intelligence.types import RegisteredCode
from ats.market.derivatives.contract_master import (
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
)
from ats.market.derivatives.contract_master.models import ExpiryDate


class ReferenceCheckCode(StrEnum):
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    REFERENCE_CONTRACT_MISSING = "REFERENCE_CONTRACT_MISSING"


class UnderlyingAlias(ATSBaseModel):
    provider_underlying: NonEmptyStr
    canonical_underlying: DerivativeUnderlying


class ProviderInstrumentRecord(ATSBaseModel):
    provider: RegisteredCode
    provider_instrument_key: NonEmptyStr
    provider_exchange_token: NonEmptyStr | None
    provider_underlying: NonEmptyStr
    exchange: RegisteredCode
    segment: RegisteredCode
    trading_symbol: NonEmptyStr
    instrument_type: DerivativeInstrumentType
    expiry: ExpiryDate
    strike: PositiveDecimal | None
    option_type: OptionType | None
    lot_size: PositiveInt
    tick_size: PositiveDecimal
    freeze_quantity: PositiveInt | None
    weekly: bool | None
    tradable: bool
    source_as_of: UTCDateTime
    source_hash: Sha256

    @model_validator(mode="after")
    def validate_shape(self) -> ProviderInstrumentRecord:
        if self.instrument_type is DerivativeInstrumentType.OPTIDX:
            if self.strike is None or self.option_type is None:
                raise ValueError("OPTIDX requires strike and option_type")
        elif self.strike is not None or self.option_type is not None:
            raise ValueError("FUTIDX cannot contain option fields")
        return self


class ReferenceInstrumentRecord(ATSBaseModel):
    reference_id: NonEmptyStr
    exchange: RegisteredCode
    segment: RegisteredCode
    underlying: DerivativeUnderlying
    instrument_type: DerivativeInstrumentType
    expiry: ExpiryDate
    strike: PositiveDecimal | None
    option_type: OptionType | None
    lot_size: PositiveInt
    freeze_quantity: PositiveInt | None
    effective_at: UTCDateTime
    source_hash: Sha256

    @model_validator(mode="after")
    def validate_shape(self) -> ReferenceInstrumentRecord:
        if self.instrument_type is DerivativeInstrumentType.OPTIDX:
            if self.strike is None or self.option_type is None:
                raise ValueError("OPTIDX requires strike and option_type")
        elif self.strike is not None or self.option_type is not None:
            raise ValueError("FUTIDX cannot contain option fields")
        return self


class ReferenceIssue(ATSBaseModel):
    code: ReferenceCheckCode
    provider_instrument_key: NonEmptyStr
    fields: tuple[RegisteredCode, ...]


class NormalizedDerivativeContract(ATSBaseModel):
    schema_version: Literal["1.0"]
    instrument_id: UUID
    exchange: RegisteredCode
    segment: RegisteredCode
    underlying: DerivativeUnderlying
    instrument_type: DerivativeInstrumentType
    expiry: ExpiryDate
    strike: PositiveDecimal | None
    option_type: OptionType | None
    lot_size: PositiveInt
    tick_size: PositiveDecimal
    freeze_quantity: PositiveInt | None
    weekly: bool | None
    tradable: bool
    provider: RegisteredCode
    provider_underlying: NonEmptyStr
    provider_instrument_key: NonEmptyStr
    provider_exchange_token: NonEmptyStr | None
    provider_trading_symbol: NonEmptyStr
    source_as_of: UTCDateTime
    provider_source_hash: Sha256
    reference_source_hash: Sha256
    contract_hash: Sha256


class ContractNormalizationResult(ATSBaseModel):
    contracts: tuple[NormalizedDerivativeContract, ...]
    issues: tuple[ReferenceIssue, ...]


__all__ = [
    "ContractNormalizationResult",
    "NormalizedDerivativeContract",
    "ProviderInstrumentRecord",
    "ReferenceCheckCode",
    "ReferenceInstrumentRecord",
    "ReferenceIssue",
    "UnderlyingAlias",
]
