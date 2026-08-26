"""Credential-injected feed configuration; nothing here may embed a secret.

The access token arrives as a :class:`pydantic.SecretStr` from the operator's
secret store at construction time. It is never serialized, hashed, logged, or
committed. The websocket URL and provider identifiers below are public,
documented endpoint facts, not market data.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import SecretStr, model_validator

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, PositiveInt

MARKET_DATA_FEED_URL: Final[Literal["wss://api.upstox.com/v3/feed/market-data-feed"]] = (
    "wss://api.upstox.com/v3/feed/market-data-feed"
)


class FeedMode(StrEnum):
    """Subscription modes supported by the current adapter architecture."""

    LTPC = "ltpc"
    FULL = "full"
    OPTION_GREEKS = "option_greeks"


class WireFormat(StrEnum):
    JSON_TEXT = "JSON_TEXT"
    PROTOBUF_BINARY = "PROTOBUF_BINARY"


class UpstoxFeedAuthorization(ATSBaseModel):
    """Bearer credential injected from the environment; absent until approved."""

    bearer_token: SecretStr | None = None

    @model_validator(mode="after")
    def reject_placeholder(self) -> UpstoxFeedAuthorization:
        if self.bearer_token is not None:
            value = self.bearer_token.get_secret_value()
            if not value.strip():
                raise ValueError("bearer_token must be a non-empty secret when supplied")
        return self

    def require_token(self) -> SecretStr:
        if self.bearer_token is None:
            raise ValueError("Upstox authorization has not been injected")
        return self.bearer_token


class UpstoxFeedLimits(ATSBaseModel):
    """Conservative silence and freshness thresholds; silence never implies price."""

    maximum_silence_ms: PositiveInt
    stale_after_ms: PositiveInt

    @model_validator(mode="after")
    def validate_ordering(self) -> UpstoxFeedLimits:
        if self.stale_after_ms < self.maximum_silence_ms:
            raise ValueError("stale_after_ms must be >= maximum_silence_ms")
        return self


class UpstoxFeedConfiguration(ATSBaseModel):
    """Complete credential-free description of one feed session."""

    feed_url: NonEmptyStr = MARKET_DATA_FEED_URL
    wire_format: WireFormat
    client_guid: NonEmptyStr
    limits: UpstoxFeedLimits

    @model_validator(mode="after")
    def pin_documented_endpoint(self) -> UpstoxFeedConfiguration:
        if self.feed_url != MARKET_DATA_FEED_URL:
            raise ValueError("feed_url must reference the documented V3 endpoint")
        return self


__all__ = [
    "FeedMode",
    "MARKET_DATA_FEED_URL",
    "UpstoxFeedAuthorization",
    "UpstoxFeedConfiguration",
    "UpstoxFeedLimits",
    "WireFormat",
]
