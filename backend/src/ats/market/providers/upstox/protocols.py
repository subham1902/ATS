"""Small read-only provider ports; none conveys financial authority."""

from __future__ import annotations

from typing import Protocol

from ats.market.derivatives.contract_master import ContractMaster
from ats.market.derivatives.option_chain import OptionQuoteInput

from .models import ProviderResponseProvenance


class ProvenancedPayload(Protocol):
    @property
    def provenance(self) -> ProviderResponseProvenance: ...


class InstrumentReferenceProvider(Protocol):
    def contract_master(self) -> ContractMaster: ...


class HistoricalMarketDataProvider(Protocol):
    def historical_data(self, instrument_key: str) -> ProvenancedPayload: ...


class OptionChainProvider(Protocol):
    def option_chain(self, underlying_key: str) -> tuple[OptionQuoteInput, ...]: ...


class MarketInformationProvider(Protocol):
    def market_information(self, segment: str) -> ProvenancedPayload: ...


class NewsProvider(Protocol):
    def news(self, instrument_keys: tuple[str, ...]) -> ProvenancedPayload: ...


class FundamentalsProvider(Protocol):
    def fundamentals(self, instrument_key: str) -> ProvenancedPayload: ...


class ChargesProvider(Protocol):
    def estimate_charges(self, request: ProvenancedPayload) -> ProvenancedPayload: ...


class MarginEstimateProvider(Protocol):
    def estimate_margin(self, request: ProvenancedPayload) -> ProvenancedPayload: ...


class LiveMarketFeed(Protocol):
    def connect(self) -> None: ...

    def close(self) -> None: ...


__all__ = [
    "ChargesProvider",
    "FundamentalsProvider",
    "HistoricalMarketDataProvider",
    "InstrumentReferenceProvider",
    "LiveMarketFeed",
    "MarginEstimateProvider",
    "MarketInformationProvider",
    "NewsProvider",
    "OptionChainProvider",
    "ProvenancedPayload",
]
