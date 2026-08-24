"""Strict option-chain input, state, and evidence models."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import (
    DataQualityState,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    Sha256,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.intelligence.types import NonNegativeFiniteFloat, RegisteredCode

from ..contract_master import DerivativeUnderlying, OptionType

DeltaFloat = Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]


class GreeksMethod(ATSStringEnum):
    SOURCE_PROVIDED = "SOURCE_PROVIDED"
    UNAVAILABLE = "UNAVAILABLE"


class Moneyness(ATSStringEnum):
    ITM = "ITM"
    ATM = "ATM"
    OTM = "OTM"


class OptionChainQualityPolicy(ATSBaseModel):
    maximum_master_age_ms: PositiveInt
    maximum_quote_age_ms: PositiveInt
    maximum_spread_fraction: NonNegativeDecimal
    minimum_top_quantity: NonNegativeInt
    minimum_volume: NonNegativeInt
    minimum_open_interest: NonNegativeInt
    atm_tolerance_fraction: NonNegativeDecimal

    @model_validator(mode="after")
    def validate_policy(self) -> OptionChainQualityPolicy:
        if self.atm_tolerance_fraction > Decimal("1"):
            raise ValueError("atm_tolerance_fraction must be <= 1")
        return self


class OptionChainBuildContext(ATSBaseModel):
    chain_id: UUID
    underlying: DerivativeUnderlying
    expiry: NonEmptyStr
    underlying_price: PositiveDecimal
    atm_strike: PositiveDecimal
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    expiry_time: UTCDateTime
    source_id: RegisteredCode
    source_version: NonEmptyStr
    policy: OptionChainQualityPolicy

    @model_validator(mode="after")
    def validate_time_boundary(self) -> OptionChainBuildContext:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        if self.expiry_time.date().isoformat() != self.expiry:
            raise ValueError("expiry_time date must match expiry")
        if self.expiry_time <= self.as_of_time:
            raise ValueError("expiry_time must be after as_of_time")
        return self


class OptionQuoteInput(ATSBaseModel):
    instrument_id: RegisteredCode
    quote_time: UTCDateTime
    bid: NonNegativeDecimal | None
    ask: NonNegativeDecimal | None
    bid_qty: NonNegativeInt | None
    ask_qty: NonNegativeInt | None
    last_price: NonNegativeDecimal | None
    volume: NonNegativeInt | None
    open_interest: NonNegativeInt | None
    change_in_oi: int | None
    implied_volatility: NonNegativeFiniteFloat | None
    delta: DeltaFloat | None
    gamma: NonNegativeFiniteFloat | None
    theta: FiniteFloat | None
    vega: NonNegativeFiniteFloat | None
    greeks_method: GreeksMethod
    greeks_method_version: NonEmptyStr | None
    source_quality_state: DataQualityState

    @model_validator(mode="after")
    def validate_greeks_provenance(self) -> OptionQuoteInput:
        greeks = (self.delta, self.gamma, self.theta, self.vega)
        if self.greeks_method is GreeksMethod.UNAVAILABLE:
            if any(value is not None for value in greeks) or self.greeks_method_version is not None:
                raise ValueError("unavailable Greeks cannot contain values/version")
        elif self.greeks_method_version is None:
            raise ValueError("source-provided Greeks require method version")
        return self


class OptionQuote(ATSBaseModel):
    instrument_id: RegisteredCode
    underlying: DerivativeUnderlying
    expiry: NonEmptyStr
    strike: PositiveDecimal
    option_type: OptionType
    bid: NonNegativeDecimal | None
    ask: NonNegativeDecimal | None
    bid_qty: NonNegativeInt | None
    ask_qty: NonNegativeInt | None
    last_price: NonNegativeDecimal | None
    volume: NonNegativeInt | None
    open_interest: NonNegativeInt | None
    change_in_oi: int | None
    implied_volatility: NonNegativeFiniteFloat | None
    delta: DeltaFloat | None
    gamma: NonNegativeFiniteFloat | None
    theta: FiniteFloat | None
    vega: NonNegativeFiniteFloat | None
    greeks_method: GreeksMethod
    greeks_method_version: NonEmptyStr | None
    spread: NonNegativeDecimal | None
    spread_fraction: NonNegativeDecimal | None
    moneyness: Moneyness
    distance_from_atm: FiniteDecimal
    time_to_expiry: NonNegativeFiniteFloat
    quote_time: UTCDateTime
    data_cutoff: UTCDateTime
    quality_state: DataQualityState
    quality_flags: tuple[RegisteredCode, ...]


class OptionChainState(ATSBaseModel):
    schema_version: Literal["1.0"]
    chain_id: UUID
    underlying: DerivativeUnderlying
    expiry: NonEmptyStr
    underlying_price: PositiveDecimal
    atm_strike: PositiveDecimal
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    expiry_time: UTCDateTime
    source_id: RegisteredCode
    source_version: NonEmptyStr
    quotes: tuple[OptionQuote, ...]
    quality_state: DataQualityState
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_chain(self) -> OptionChainState:
        if not self.quotes:
            raise ValueError("option chain cannot be empty")
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        return self


class OptionChainEvidence(ATSBaseModel):
    schema_version: Literal["1.0"]
    evidence_id: UUID
    chain_id: UUID
    method_version: NonEmptyStr
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    atm_iv: NonNegativeFiniteFloat | None
    put_call_iv_difference: FiniteFloat | None
    put_call_open_interest_ratio: NonNegativeFiniteFloat | None
    put_call_volume_ratio: NonNegativeFiniteFloat | None
    atm_straddle_premium: NonNegativeDecimal | None
    implied_expected_move: NonNegativeDecimal | None
    call_put_volume_imbalance: FiniteFloat | None
    mean_spread_fraction: NonNegativeFiniteFloat | None
    gamma_concentration: NonNegativeFiniteFloat | None
    theta_decay_intensity: NonNegativeFiniteFloat | None
    quality_state: DataQualityState
    reason_codes: tuple[RegisteredCode, ...]
    payload_hash: Sha256


__all__ = [
    "GreeksMethod",
    "Moneyness",
    "OptionChainBuildContext",
    "OptionChainEvidence",
    "OptionChainQualityPolicy",
    "OptionChainState",
    "OptionQuote",
    "OptionQuoteInput",
]
