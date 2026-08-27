"""Normalized provider-neutral feed update records.

Every record carries both the provider exchange timestamp and the local
receipt timestamp so downstream freshness logic can distinguish source time
from delivery time. Greeks carried on a normalized update are always
``SOURCE_PROVIDED``: ATS-computed Greeks can only enter the system through the
explicit deterministic calculator and its own method label.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, FiniteFloat, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, NonNegativeInt, PositiveDecimal

SourceGreeksMethod = Literal["SOURCE_PROVIDED", "UNAVAILABLE"]
_PROVIDER_GREEKS_VERSION = "UPSTOX-V3-FEED"

DeltaFloat = Annotated[FiniteFloat, Field(ge=-1.0, le=1.0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]


class UpdateKind(StrEnum):
    INDEX = "INDEX"
    OPTION = "OPTION"


class MarketDepthLevel(ATSBaseModel):
    price: PositiveDecimal
    quantity: NonNegativeInt
    orders: NonNegativeInt | None


class MarketDepth(ATSBaseModel):
    buy_levels: tuple[MarketDepthLevel, ...]
    sell_levels: tuple[MarketDepthLevel, ...]


class NormalizedFeedUpdate(ATSBaseModel):
    """One decoded instrument update; absent provider fields stay ``None``."""

    instrument_key: NonEmptyStr
    kind: UpdateKind
    received_at: UTCDateTime
    exchange_timestamp: UTCDateTime | None
    provider_timestamp: UTCDateTime | None = None
    price_source_timestamp: UTCDateTime | None = None
    depth_source_timestamp: UTCDateTime | None = None
    volume_source_timestamp: UTCDateTime | None = None
    oi_source_timestamp: UTCDateTime | None = None
    iv_source_timestamp: UTCDateTime | None = None
    greeks_source_timestamp: UTCDateTime | None = None
    last_traded_price: PositiveDecimal | None = None
    close_price: PositiveDecimal | None = None
    bid_price: PositiveDecimal | None = None
    ask_price: PositiveDecimal | None = None
    bid_quantity: NonNegativeInt | None = None
    ask_quantity: NonNegativeInt | None = None
    volume: NonNegativeInt | None = None
    open_interest: NonNegativeInt | None = None
    open_interest_change: int | None = None
    implied_volatility: NonNegativeFiniteFloat | None = None
    delta: DeltaFloat | None = None
    gamma: NonNegativeFiniteFloat | None = None
    theta: FiniteFloat | None = None
    vega: NonNegativeFiniteFloat | None = None
    rho: FiniteFloat | None = None
    market_depth: MarketDepth | None = None
    greeks_method: SourceGreeksMethod = "UNAVAILABLE"
    greeks_method_version: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_greeks_provenance(self) -> NormalizedFeedUpdate:
        greeks = (self.delta, self.gamma, self.theta, self.vega, self.rho)
        if any(value is not None for value in greeks):
            if self.greeks_method != "SOURCE_PROVIDED":
                raise ValueError("carried Greeks must be labelled SOURCE_PROVIDED")
            if self.greeks_method_version != _PROVIDER_GREEKS_VERSION:
                raise ValueError("source Greeks require the provider method version")
        elif self.greeks_method == "SOURCE_PROVIDED":
            raise ValueError("SOURCE_PROVIDED requires at least one Greek value")
        return self

    def decision_critical_timestamps(self) -> tuple[UTCDateTime | None, ...]:
        """Source times that must independently satisfy the trading freshness policy."""
        timestamps: list[UTCDateTime | None] = []
        if self.last_traded_price is not None:
            timestamps.append(self.price_source_timestamp or self.exchange_timestamp)
        if (
            self.bid_price is not None
            or self.ask_price is not None
            or self.market_depth is not None
        ):
            timestamps.append(self.depth_source_timestamp)
        if not timestamps:
            timestamps.append(self.exchange_timestamp)
        return tuple(timestamps)


def provider_greeks_version() -> str:
    """Version label stamped onto provider-carried Greeks for provenance audits."""

    return _PROVIDER_GREEKS_VERSION


__all__ = [
    "MarketDepth",
    "MarketDepthLevel",
    "NormalizedFeedUpdate",
    "UpdateKind",
    "provider_greeks_version",
]
