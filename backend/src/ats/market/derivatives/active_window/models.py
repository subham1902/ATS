"""Strict active-window, hot quote, and bounded market-state types."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import (
    DataQualityState,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    Sha256,
)
from ats.contracts.intelligence.types import NonNegativeFiniteFloat
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.derivatives.contract_master.models import ExpiryDate

DeltaFloat = Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]


class MarketStateFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"


class ActiveWindowErrorCode(StrEnum):
    CONTRACT_MASTER_STALE = "CONTRACT_MASTER_STALE"
    EXPIRY_NOT_ELIGIBLE = "EXPIRY_NOT_ELIGIBLE"
    INSUFFICIENT_PAIRED_STRIKES = "INSUFFICIENT_PAIRED_STRIKES"
    DUPLICATE_CONTRACT_SIDE = "DUPLICATE_CONTRACT_SIDE"
    CONTRACT_NOT_ACTIVE = "CONTRACT_NOT_ACTIVE"
    TIMESTAMP_REGRESSION = "TIMESTAMP_REGRESSION"
    SEQUENCE_GAP = "SEQUENCE_GAP"


class ActiveWindowError(RuntimeError):
    def __init__(self, code: ActiveWindowErrorCode) -> None:
        self.code = code
        super().__init__(f"active option window failed: {code.value}")


class ActiveWindowPolicy(ATSBaseModel):
    window_size: PositiveInt
    expiry: ExpiryDate
    maximum_master_age_ms: PositiveInt
    maximum_quote_age_ms: PositiveInt


class ActiveOptionPair(ATSBaseModel):
    strike: PositiveDecimal
    ce_contract_id: UUID
    pe_contract_id: UUID
    ce_provider_instrument_key: NonEmptyStr
    pe_provider_instrument_key: NonEmptyStr


class ActiveOptionWindow(ATSBaseModel):
    schema_version: Literal["1.0"]
    underlying: DerivativeUnderlying
    expiry: ExpiryDate
    underlying_price: PositiveDecimal
    atm_strike: PositiveDecimal
    as_of_time: UTCDateTime
    window_size: PositiveInt
    pairs: tuple[ActiveOptionPair, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_pair_count(self) -> ActiveOptionWindow:
        if len(self.pairs) != self.window_size * 2 + 1:
            raise ValueError("active window must contain a symmetric paired strike set")
        strikes = tuple(item.strike for item in self.pairs)
        if strikes != tuple(sorted(strikes)) or len(set(strikes)) != len(strikes):
            raise ValueError("active window strikes must be unique and ordered")
        if self.atm_strike not in strikes:
            raise ValueError("ATM strike must be present in active window")
        return self

    def contract_ids(self) -> tuple[UUID, ...]:
        return tuple(
            contract_id
            for pair in self.pairs
            for contract_id in (pair.ce_contract_id, pair.pe_contract_id)
        )


class HotOptionQuoteInput(ATSBaseModel):
    contract_id: UUID
    quote_time: UTCDateTime
    received_at: UTCDateTime
    bid: NonNegativeDecimal | None
    ask: NonNegativeDecimal | None
    bid_quantity: NonNegativeInt | None
    ask_quantity: NonNegativeInt | None
    last_price: NonNegativeDecimal | None
    volume: NonNegativeInt | None
    open_interest: NonNegativeInt | None
    implied_volatility: NonNegativeFiniteFloat | None
    delta: DeltaFloat | None
    gamma: NonNegativeFiniteFloat | None
    theta: FiniteFloat | None
    vega: NonNegativeFiniteFloat | None
    quality: DataQualityState

    @model_validator(mode="after")
    def validate_quote(self) -> HotOptionQuoteInput:
        if self.received_at < self.quote_time:
            raise ValueError("received_at must be >= quote_time")
        if self.bid is not None and self.ask is not None and self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        return self


class HotOptionQuoteView(ATSBaseModel):
    contract_id: UUID
    quote_time: UTCDateTime
    bid: NonNegativeDecimal | None
    ask: NonNegativeDecimal | None
    bid_quantity: NonNegativeInt | None
    ask_quantity: NonNegativeInt | None
    last_price: NonNegativeDecimal | None
    volume: NonNegativeInt | None
    open_interest: NonNegativeInt | None
    implied_volatility: NonNegativeFiniteFloat | None
    delta: DeltaFloat | None
    gamma: NonNegativeFiniteFloat | None
    theta: FiniteFloat | None
    vega: NonNegativeFiniteFloat | None
    spread: NonNegativeDecimal | None
    quote_age_ms: NonNegativeInt
    quality: DataQualityState


class HotWindowSnapshot(ATSBaseModel):
    window: ActiveOptionWindow
    as_of_time: UTCDateTime
    freshness: MarketStateFreshness
    quotes: tuple[HotOptionQuoteView, ...]
    missing_contract_ids: tuple[UUID, ...]


class UnderlyingObservation(ATSBaseModel):
    underlying: DerivativeUnderlying
    sequence: PositiveInt
    event_time: UTCDateTime
    received_at: UTCDateTime
    price: PositiveDecimal
    quality: DataQualityState

    @model_validator(mode="after")
    def validate_received_time(self) -> UnderlyingObservation:
        if self.received_at < self.event_time:
            raise ValueError("received_at must be >= event_time")
        return self


class IncrementalUnderlyingSnapshot(ATSBaseModel):
    underlying: DerivativeUnderlying
    freshness: MarketStateFreshness
    observations: tuple[UnderlyingObservation, ...]
    rolling_price_sum: PositiveDecimal | None


ZERO = Decimal("0")


__all__ = [
    "ActiveOptionPair",
    "ActiveOptionWindow",
    "ActiveWindowError",
    "ActiveWindowErrorCode",
    "ActiveWindowPolicy",
    "HotOptionQuoteInput",
    "HotOptionQuoteView",
    "HotWindowSnapshot",
    "IncrementalUnderlyingSnapshot",
    "MarketStateFreshness",
    "UnderlyingObservation",
]
