"""Frozen A2 view of current Upstox read-only API capabilities."""

from __future__ import annotations

from .models import (
    AccessClass,
    CapabilityDescriptor,
    CapabilityStatus,
    EntitlementClass,
    RateLimitClass,
    UpstoxCapability,
)


def _read(
    capability: UpstoxCapability,
    category: str,
    endpoint: str,
    adapter: str | None,
    *,
    public: bool = False,
    plus_optional: bool = False,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability=capability,
        api_category=category,
        endpoint_family=endpoint,
        access_class=AccessClass.PUBLIC_READ if public else AccessClass.ANALYTICS_READ,
        analytics_token_supported=True,
        static_ip_required=False,
        entitlement=(
            EntitlementClass.PLUS_OPTIONAL if plus_optional else EntitlementClass.STANDARD
        ),
        rate_limit_class=(
            RateLimitClass.PUBLIC_FILES
            if public
            else RateLimitClass.WEBSOCKET_AUTHORIZATION
            if capability is UpstoxCapability.WEBSOCKET_FEED
            else RateLimitClass.HISTORICAL_DATA
            if capability
            in {
                UpstoxCapability.HISTORICAL_DATA,
                UpstoxCapability.EXPIRED_INSTRUMENTS,
                UpstoxCapability.BACKTESTING_ANALYTICS,
            }
            else RateLimitClass.STANDARD_MARKET_DATA
        ),
        adapter=adapter,
        runtime_status=(
            CapabilityStatus.AVAILABLE if adapter else CapabilityStatus.ADAPTER_PENDING
        ),
    )


def _account(capability: UpstoxCapability, category: str, endpoint: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability=capability,
        api_category=category,
        endpoint_family=endpoint,
        access_class=AccessClass.ACCOUNT_READ_STATIC_IP,
        analytics_token_supported=True,
        static_ip_required=True,
        entitlement=EntitlementClass.ACCOUNT_STATIC_IP,
        rate_limit_class=RateLimitClass.ACCOUNT_READ,
        adapter=None,
        runtime_status=CapabilityStatus.OUT_OF_SCOPE_FOR_A2,
    )


UPSTOX_CAPABILITIES: tuple[CapabilityDescriptor, ...] = (
    _read(
        UpstoxCapability.INSTRUMENT_MASTER,
        "Instruments",
        "BOD instrument files",
        "DerivativeReferenceProvider",
        public=True,
    ),
    _read(
        UpstoxCapability.INSTRUMENT_SEARCH,
        "Instruments",
        "instrument search",
        "InstrumentReferenceProvider",
    ),
    _read(
        UpstoxCapability.HISTORICAL_DATA,
        "Historical Data",
        "historical candle",
        "HistoricalMarketDataProvider",
    ),
    _read(
        UpstoxCapability.EXPIRED_INSTRUMENTS,
        "Expired Instruments",
        "expired instruments",
        "HistoricalMarketDataProvider",
        plus_optional=True,
    ),
    _read(
        UpstoxCapability.BACKTESTING_ANALYTICS,
        "Historical Data",
        "backtesting/read-only analytics",
        None,
        plus_optional=True,
    ),
    _read(
        UpstoxCapability.MARKET_QUOTE,
        "Market Quote",
        "market quote V3",
        "MarketInformationProvider",
    ),
    _read(
        UpstoxCapability.OPTION_CHAIN,
        "Option Chain",
        "put/call option chain",
        "OptionChainProvider",
    ),
    _read(
        UpstoxCapability.MARKET_INFORMATION,
        "Market Information",
        "exchange/market status",
        "MarketInformationProvider",
    ),
    _read(UpstoxCapability.CHARGES, "Charges", "brokerage and charges", "ChargesProvider"),
    _read(UpstoxCapability.MARGINS, "Margins", "margin estimate", "MarginEstimateProvider"),
    _read(UpstoxCapability.FUNDAMENTALS, "Fundamentals", "fundamentals", "FundamentalsProvider"),
    _read(UpstoxCapability.NEWS, "News", "market news", "NewsProvider"),
    _read(
        UpstoxCapability.WEBSOCKET_FEED,
        "Websocket",
        "market data feed V3",
        "LiveMarketFeed",
        plus_optional=True,
    ),
    _account(UpstoxCapability.USER_PROFILE, "User", "profile/funds"),
    _account(UpstoxCapability.PORTFOLIO, "Portfolio", "positions/holdings"),
    _account(UpstoxCapability.ORDER_HISTORY, "Orders", "order book/history"),
    _account(UpstoxCapability.TRADE_PNL, "Trade Profit And Loss", "trade P&L"),
    _account(UpstoxCapability.PAYMENTS, "Payments", "pay-ins/payouts"),
    _account(UpstoxCapability.GTT_READ, "GTT Orders", "GTT details"),
    _account(UpstoxCapability.MUTUAL_FUND, "Mutual Fund", "orders/SIPs/holdings"),
    CapabilityDescriptor(
        capability=UpstoxCapability.REAL_ORDER_PLACEMENT,
        api_category="Orders & Trading",
        endpoint_family="place/modify/cancel order",
        access_class=AccessClass.FORBIDDEN_IN_A2,
        analytics_token_supported=False,
        static_ip_required=False,
        entitlement=EntitlementClass.FORBIDDEN,
        rate_limit_class=RateLimitClass.NEVER_CALL,
        adapter=None,
        runtime_status=CapabilityStatus.FORBIDDEN_IN_A2,
    ),
)


def capability_catalogue() -> dict[UpstoxCapability, CapabilityDescriptor]:
    catalogue = {item.capability: item for item in UPSTOX_CAPABILITIES}
    if len(catalogue) != len(UPSTOX_CAPABILITIES):
        raise RuntimeError("duplicate Upstox capability registration")
    return catalogue


__all__ = ["UPSTOX_CAPABILITIES", "capability_catalogue"]
