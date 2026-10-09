"""One immutable observation for terminal feeds and versioned historical replay."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime


class VolumeProvenance(StrEnum):
    BROKER_VOLUME = "BROKER_VOLUME"
    TICK_VOLUME = "TICK_VOLUME"
    REAL_VOLUME = "REAL_VOLUME"
    UNKNOWN = "UNKNOWN"


class MarketObservation(ATSBaseModel):
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    broker_symbol: str
    timestamp: UTCDateTime
    received_at: UTCDateTime
    source: str
    dataset_id: str | None = None
    provenance: Literal["BROKER_TICK_PROXY", "BROKER_BAR", "UNKNOWN"] = "UNKNOWN"
    timestamp_provenance: str = "SOURCE_UTC"
    raw_source_epoch_ms: int | None = Field(default=None, ge=0)
    clock_evidence_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    bid: Decimal | None = Field(default=None, gt=0)
    ask: Decimal | None = Field(default=None, gt=0)
    last: Decimal | None = Field(default=None, gt=0)
    volume: Decimal | None = Field(default=None, ge=0)
    tick_volume: Decimal | None = Field(default=None, ge=0)
    real_volume: Decimal | None = Field(default=None, ge=0)
    flags: int | None = Field(default=None, ge=0)
    volume_provenance: VolumeProvenance = VolumeProvenance.UNKNOWN
    open: Decimal | None = Field(default=None, gt=0)
    high: Decimal | None = Field(default=None, gt=0)
    low: Decimal | None = Field(default=None, gt=0)
    close: Decimal | None = Field(default=None, gt=0)
    timeframe: str | None = None

    @property
    def available_at(self) -> UTCDateTime:
        if self.timeframe is None:
            return self.timestamp
        seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}
        if self.timeframe not in seconds:
            raise ValueError("UNSUPPORTED_TIMEFRAME")
        return self.timestamp + timedelta(seconds=seconds[self.timeframe])

    @model_validator(mode="after")
    def validate_observation(self) -> MarketObservation:
        values = (
            self.bid,
            self.ask,
            self.last,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.tick_volume,
            self.real_volume,
        )
        if any(value is not None and not value.is_finite() for value in values):
            raise ValueError("NONFINITE_MARKET_VALUE")
        if self.bid is not None and self.ask is not None and self.ask < self.bid:
            raise ValueError("CROSSED_QUOTE")
        if self.volume is not None and self.volume_provenance != VolumeProvenance.BROKER_VOLUME:
            raise ValueError("volume requires explicit BROKER_VOLUME provenance")
        if self.volume_provenance == VolumeProvenance.REAL_VOLUME and self.real_volume is None:
            raise ValueError("REAL_VOLUME requires observed real_volume")
        if self.volume_provenance == VolumeProvenance.TICK_VOLUME and self.tick_volume is None:
            raise ValueError("TICK_VOLUME requires observed tick_volume")
        bar = (self.open, self.high, self.low, self.close)
        if any(value is not None for value in bar):
            if any(value is None for value in bar) or not self.timeframe:
                raise ValueError("BAR_SCHEMA_INCOMPLETE")
            assert self.low is not None and self.high is not None
            assert self.open is not None and self.close is not None
            if (
                not self.low
                <= min(self.open, self.close)
                <= max(self.open, self.close)
                <= self.high
            ):
                raise ValueError("IMPOSSIBLE_OHLC")
            duration = (self.available_at - self.timestamp).total_seconds()
            if self.timestamp.timestamp() % duration:
                raise ValueError("MISALIGNED_BAR_OPEN")
        elif self.timeframe is not None:
            raise ValueError("TIMEFRAME_REQUIRES_OHLC")
        elif all(value is None for value in (self.bid, self.ask, self.last)):
            raise ValueError("NO_OBSERVED_PRICE")
        return self

    @property
    def instrument_key(self) -> str:
        """Compatibility at the generic fabric seam; always canonical."""
        return self.canonical_symbol

    @property
    def exchange_timestamp(self) -> UTCDateTime:
        return self.timestamp

    @property
    def last_traded_price(self) -> Decimal | None:
        return self.last

    @property
    def bid_price(self) -> Decimal | None:
        return self.bid

    @property
    def ask_price(self) -> Decimal | None:
        return self.ask

    @property
    def chart_price(self) -> Decimal | None:
        return self.last if self.last is not None else self.bid

    @property
    def price_provenance(self) -> str:
        return "BROKER_LAST" if self.last is not None else "QUOTE_DERIVED_BID"

    @property
    def open_interest(self) -> None:
        return None

    @property
    def bid_quantity(self) -> None:
        return None

    @property
    def ask_quantity(self) -> None:
        return None
