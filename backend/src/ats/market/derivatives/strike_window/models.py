"""Strict strike-window plan types derived only from actual listed contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveDecimal, PositiveInt, Sha256
from ats.market.derivatives.contract_master.models import ExpiryDate


class StrikeWindowPolicy(ATSBaseModel):
    """Caller-configured research-window bounds; no exchange rule is derived here."""

    window_size: PositiveInt
    expiry: ExpiryDate
    maximum_master_age_ms: PositiveInt


class StrikeLeg(ATSBaseModel):
    """One listed CE or PE contract selected inside the window."""

    instrument_id: NonEmptyStr
    trading_symbol: NonEmptyStr
    lot_size: PositiveInt
    quantity_freeze_limit: PositiveInt | None
    tick_size: PositiveDecimal


class PairedStrike(ATSBaseModel):
    """One listed strike with both CE and PE actually present in the master."""

    strike: PositiveDecimal
    ce: StrikeLeg
    pe: StrikeLeg

    @model_validator(mode="after")
    def validate_pair(self) -> PairedStrike:
        if self.ce.lot_size != self.pe.lot_size:
            raise ValueError("paired strike legs must share the source lot size")
        return self


class UnpairedStrikeEvidence(ATSBaseModel):
    """A listed strike excluded because one option side is missing from source data."""

    strike: PositiveDecimal
    missing_side: Literal["CE", "PE"]


class StrikeWindowPlan(ATSBaseModel):
    """Deterministic ATM-centered bounded universe built from genuine listings."""

    schema_version: Literal["1.0"]
    underlying_price: PositiveDecimal
    atm_strike: PositiveDecimal
    expiry: ExpiryDate
    window_size: PositiveInt
    as_of_time: UTCDateTime
    calendar_trading_day: bool | None
    strikes: tuple[PairedStrike, ...]
    unpaired_evidence: tuple[UnpairedStrikeEvidence, ...]
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_window(self) -> StrikeWindowPlan:
        if len(self.strikes) != self.window_size * 2 + 1:
            raise ValueError("window must contain exactly ATM +/- N paired strikes")
        ordered = tuple(item.strike for item in self.strikes)
        if ordered != tuple(sorted(ordered)) or len(set(ordered)) != len(ordered):
            raise ValueError("window strikes must be unique and ascending")
        if self.atm_strike not in ordered:
            raise ValueError("ATM strike must be present in the window")
        return self

    def moneyness_ordering_ce(self) -> tuple[tuple[Decimal, str], ...]:
        """ITM-first CE ordering relative to the underlying reference price."""

        return tuple(
            (item.strike, "ITM" if item.strike < self.underlying_price else "OTM")
            for item in self._atm_first()
        )

    def moneyness_ordering_pe(self) -> tuple[tuple[Decimal, str], ...]:
        """ITM-first PE ordering relative to the underlying reference price."""

        return tuple(
            (item.strike, "ITM" if item.strike > self.underlying_price else "OTM")
            for item in self._atm_first()
        )

    def _atm_first(self) -> tuple[PairedStrike, ...]:
        index = [item.strike for item in self.strikes].index(self.atm_strike)
        return (*self.strikes[index:], *reversed(self.strikes[:index]))


__all__ = [
    "PairedStrike",
    "StrikeLeg",
    "StrikeWindowPlan",
    "StrikeWindowPolicy",
    "UnpairedStrikeEvidence",
]
