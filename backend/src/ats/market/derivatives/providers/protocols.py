"""Provider protocols. Implementations receive injected credentials only outside this package."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ats.market.derivatives.contract_master import ContractMaster
from ats.market.derivatives.option_chain import OptionQuoteInput

from .models import MarketFeedHealth


class DerivativeReferenceProvider(Protocol):
    def contract_master(self) -> ContractMaster: ...


class DerivativeInstrumentProvider(Protocol):
    def instruments(self) -> ContractMaster: ...


class DerivativeHistoricalDataProvider(Protocol):
    def approved_fixture_bytes(self, fixture_id: str) -> bytes: ...


class DerivativeMarketFeed(Protocol):
    def option_quotes(self) -> Iterable[OptionQuoteInput]: ...

    def health(self) -> MarketFeedHealth: ...


__all__ = [
    "DerivativeHistoricalDataProvider",
    "DerivativeInstrumentProvider",
    "DerivativeMarketFeed",
    "DerivativeReferenceProvider",
]
