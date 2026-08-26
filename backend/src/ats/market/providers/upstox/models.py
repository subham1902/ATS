"""Typed, secret-free Upstox read-only capability and provenance records."""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveInt, Sha256


class AccessClass(StrEnum):
    PUBLIC_READ = "PUBLIC_READ"
    ANALYTICS_READ = "ANALYTICS_READ"
    ACCOUNT_READ_STATIC_IP = "ACCOUNT_READ_STATIC_IP"
    FORBIDDEN_IN_A2 = "FORBIDDEN_IN_A2"


class EntitlementClass(StrEnum):
    STANDARD = "STANDARD"
    PLUS_OPTIONAL = "PLUS_OPTIONAL"
    ACCOUNT_STATIC_IP = "ACCOUNT_STATIC_IP"
    FORBIDDEN = "FORBIDDEN"


class CapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ADAPTER_PENDING = "ADAPTER_PENDING"
    OUT_OF_SCOPE_FOR_A2 = "OUT_OF_SCOPE_FOR_A2"
    FORBIDDEN_IN_A2 = "FORBIDDEN_IN_A2"


class RateLimitClass(StrEnum):
    PUBLIC_FILES = "PUBLIC_FILES"
    STANDARD_MARKET_DATA = "STANDARD_MARKET_DATA"
    HISTORICAL_DATA = "HISTORICAL_DATA"
    WEBSOCKET_AUTHORIZATION = "WEBSOCKET_AUTHORIZATION"
    ACCOUNT_READ = "ACCOUNT_READ"
    NEVER_CALL = "NEVER_CALL"


class UpstoxCapability(StrEnum):
    INSTRUMENT_MASTER = "INSTRUMENT_MASTER"
    INSTRUMENT_SEARCH = "INSTRUMENT_SEARCH"
    HISTORICAL_DATA = "HISTORICAL_DATA"
    EXPIRED_INSTRUMENTS = "EXPIRED_INSTRUMENTS"
    BACKTESTING_ANALYTICS = "BACKTESTING_ANALYTICS"
    MARKET_QUOTE = "MARKET_QUOTE"
    OPTION_CHAIN = "OPTION_CHAIN"
    MARKET_INFORMATION = "MARKET_INFORMATION"
    CHARGES = "CHARGES"
    MARGINS = "MARGINS"
    FUNDAMENTALS = "FUNDAMENTALS"
    NEWS = "NEWS"
    WEBSOCKET_FEED = "WEBSOCKET_FEED"
    USER_PROFILE = "USER_PROFILE"
    PORTFOLIO = "PORTFOLIO"
    ORDER_HISTORY = "ORDER_HISTORY"
    TRADE_PNL = "TRADE_PNL"
    PAYMENTS = "PAYMENTS"
    GTT_READ = "GTT_READ"
    MUTUAL_FUND = "MUTUAL_FUND"
    REAL_ORDER_PLACEMENT = "REAL_ORDER_PLACEMENT"


class CapabilityDescriptor(ATSBaseModel):
    capability: UpstoxCapability
    api_category: NonEmptyStr
    endpoint_family: NonEmptyStr
    access_class: AccessClass
    analytics_token_supported: bool
    static_ip_required: bool
    entitlement: EntitlementClass
    rate_limit_class: RateLimitClass
    adapter: NonEmptyStr | None
    runtime_status: CapabilityStatus

    @model_validator(mode="after")
    def validate_authority(self) -> CapabilityDescriptor:
        if self.access_class is AccessClass.FORBIDDEN_IN_A2:
            if self.runtime_status is not CapabilityStatus.FORBIDDEN_IN_A2:
                raise ValueError("forbidden capability must remain forbidden at runtime")
            if self.adapter is not None:
                raise ValueError("forbidden capability cannot have an A2 adapter")
        if self.static_ip_required and self.access_class is not AccessClass.ACCOUNT_READ_STATIC_IP:
            raise ValueError("static-IP capability must be classified as account read")
        return self


class RateLimitPolicy(ATSBaseModel):
    rate_limit_class: RateLimitClass
    maximum_attempts: PositiveInt
    timeout_ms: PositiveInt
    base_backoff_ms: PositiveInt
    maximum_backoff_ms: PositiveInt

    @model_validator(mode="after")
    def validate_backoff(self) -> RateLimitPolicy:
        if self.maximum_backoff_ms < self.base_backoff_ms:
            raise ValueError("maximum_backoff_ms must be >= base_backoff_ms")
        return self


class ProviderResponseProvenance(ATSBaseModel):
    provider: NonEmptyStr
    endpoint_category: NonEmptyStr
    retrieved_at: UTCDateTime
    source_as_of: UTCDateTime | None
    raw_hash: Sha256
    entitlement_class: EntitlementClass
    normalizer_version: NonEmptyStr


def response_provenance(
    *,
    endpoint_category: str,
    retrieved_at: UTCDateTime,
    source_as_of: UTCDateTime | None,
    raw_body: bytes,
    entitlement_class: EntitlementClass,
    normalizer_version: str,
) -> ProviderResponseProvenance:
    return ProviderResponseProvenance(
        provider="UPSTOX",
        endpoint_category=endpoint_category,
        retrieved_at=retrieved_at,
        source_as_of=source_as_of,
        raw_hash=hashlib.sha256(raw_body).hexdigest(),
        entitlement_class=entitlement_class,
        normalizer_version=normalizer_version,
    )


__all__ = [
    "AccessClass",
    "CapabilityDescriptor",
    "CapabilityStatus",
    "EntitlementClass",
    "ProviderResponseProvenance",
    "RateLimitClass",
    "RateLimitPolicy",
    "UpstoxCapability",
    "response_provenance",
]
