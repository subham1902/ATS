"""The product domain. Broker suffixes never change internal identity."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime

CANONICAL_SYMBOL = "XAUUSD"


class UnsupportedInstrument(ValueError):
    pass


def require_xauusd(symbol: str) -> str:
    if symbol != CANONICAL_SYMBOL:
        raise UnsupportedInstrument(f"UNSUPPORTED_INSTRUMENT: {symbol!r}; supported: XAUUSD")
    return CANONICAL_SYMBOL


class InstrumentMetadata(ATSBaseModel):
    """Observed broker terms required by the paper execution seam."""

    instrument_id: Literal["XAUUSD"] = "XAUUSD"
    broker_symbol: str
    digits: int = Field(ge=0)
    point: Decimal = Field(gt=0)
    tick_size: Decimal = Field(gt=0)
    contract_size: Decimal = Field(gt=0)
    volume_min: Decimal = Field(gt=0)
    volume_max: Decimal = Field(gt=0)
    volume_step: Decimal = Field(gt=0)
    trade_mode: int
    as_of_time: UTCDateTime
    source: Literal["MT4", "MT5"]

    @model_validator(mode="after")
    def validate_terms(self) -> InstrumentMetadata:
        if not self.broker_symbol.strip() or self.volume_max < self.volume_min:
            raise ValueError("INVALID_BROKER_TERMS")
        if self.trade_mode not in {0, 1, 2, 3, 4}:
            raise ValueError("UNKNOWN_TRADE_MODE")
        return self

    @property
    def lot_size(self) -> Decimal:
        return self.volume_step

    @property
    def quantity_freeze_limit(self) -> Decimal:
        return self.volume_max

    @property
    def tradable(self) -> bool:
        return self.trade_mode in {1, 4}


@dataclass(frozen=True)
class XauUsdDomain:
    canonical_symbol: Literal["XAUUSD"] = "XAUUSD"
    quote_currency: Literal["USD"] = "USD"
    base: Literal["XAU"] = "XAU"
    asset_class: Literal["SPOT_METAL_BROKER_CFD"] = "SPOT_METAL_BROKER_CFD"
    provider: Literal["MT4", "MT5"] = "MT5"
    broker_symbol: str = "XAUUSD"
    stale_after_seconds: float = 15.0
    metadata: InstrumentMetadata | None = field(default=None)

    @classmethod
    def from_environment(cls) -> XauUsdDomain:
        provider = os.environ.get("ATS_METATRADER_VERSION", "MT5")
        if provider not in {"MT4", "MT5"}:
            raise ValueError("UNSUPPORTED_PROVIDER: expected MT4 or MT5")
        key = "ATS_MT5_SYMBOL" if provider == "MT5" else "ATS_MT4_SYMBOL"
        symbol = os.environ.get(key, "XAUUSD").strip()
        if not symbol:
            raise ValueError(f"{key} must not be empty")
        return cls(provider=provider, broker_symbol=symbol)  # type: ignore[arg-type]


def classify_session(moment: datetime) -> tuple[str, ...]:
    """Research labels only, never a claim about broker trading hours."""
    if moment.tzinfo is None:
        raise ValueError("session classification requires timezone-aware input")
    stamp = moment.astimezone(UTC)
    if stamp.weekday() == 5 or (stamp.weekday() == 6 and stamp.hour < 22):
        return ("WEEKEND_CLOSED_ESTIMATE",)
    if stamp.weekday() == 4 and stamp.hour >= 22:
        return ("WEEKEND_CLOSED_ESTIMATE",)
    labels = []
    if stamp.hour < 8:
        labels.append("ASIA")
    if 7 <= stamp.hour < 16:
        labels.append("LONDON")
    if 12 <= stamp.hour < 21:
        labels.append("NEW_YORK")
    if 12 <= stamp.hour < 16:
        labels.append("OVERLAP")
    if 21 <= stamp.hour < 23:
        labels.append("ROLLOVER_ESTIMATE")
    return tuple(labels) or ("OFF_PEAK",)
