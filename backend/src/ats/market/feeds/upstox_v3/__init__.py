"""Credential-injected Upstox Market Data Feed V3 adapter architecture.

No component here performs an authenticated network call or embeds a secret.
The websocket transport and compiled Protobuf decoder arrive later through the
declared seams (:class:`FeedConnection`, :class:`BinaryFeedDecoder`).
"""

from .adapter import (
    ConnectionState,
    FeedConnection,
    FeedDiagnostics,
    FrameOutcome,
    ReconciliationSource,
    UpstoxV3FeedAdapter,
    build_handshake_headers,
)
from .codec import (
    BinaryFeedDecoder,
    FeedPayloadDecoder,
    JsonFeedPayloadDecoder,
    ProtobufDecodingSeam,
)
from .config import (
    MARKET_DATA_AUTHORIZE_URL,
    MARKET_DATA_FEED_URL,
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)
from .errors import UpstoxFeedError, UpstoxFeedErrorCode
from .frames import (
    change_mode_frame,
    parse_control_acknowledgement,
    subscribe_frame,
    unsubscribe_frame,
)
from .freshness import FeedFreshnessBoard, KeyFreshnessLatch, LatchDecision
from .instrument_keys import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
    index_feed_key,
    segment_of,
    validate_feed_key,
)
from .messages import (
    MarketDepth,
    MarketDepthLevel,
    NormalizedFeedUpdate,
    UpdateKind,
    provider_greeks_version,
)
from .protobuf_codec import UpstoxV3ProtobufDecoder
from .subscription import SubscriptionEntry, SubscriptionRegistry
from .transport import (
    FeedAuthorizer,
    UpstoxV3FeedAuthorizer,
    UpstoxV3Transport,
    UpstoxV3WebSocketConnection,
)

__all__ = [
    "BANKNIFTY_INDEX_FEED_KEY",
    "BinaryFeedDecoder",
    "ConnectionState",
    "FeedConnection",
    "FeedDiagnostics",
    "FeedFreshnessBoard",
    "FeedMode",
    "FeedAuthorizer",
    "FeedPayloadDecoder",
    "FrameOutcome",
    "JsonFeedPayloadDecoder",
    "KeyFreshnessLatch",
    "MARKET_DATA_FEED_URL",
    "MARKET_DATA_AUTHORIZE_URL",
    "LatchDecision",
    "MarketDepth",
    "MarketDepthLevel",
    "NIFTY_INDEX_FEED_KEY",
    "NormalizedFeedUpdate",
    "ProtobufDecodingSeam",
    "ReconciliationSource",
    "SubscriptionEntry",
    "SubscriptionRegistry",
    "UpdateKind",
    "UpstoxFeedAuthorization",
    "UpstoxFeedConfiguration",
    "UpstoxFeedError",
    "UpstoxFeedErrorCode",
    "UpstoxFeedLimits",
    "UpstoxV3FeedAdapter",
    "UpstoxV3FeedAuthorizer",
    "UpstoxV3ProtobufDecoder",
    "UpstoxV3Transport",
    "UpstoxV3WebSocketConnection",
    "WireFormat",
    "build_handshake_headers",
    "change_mode_frame",
    "index_feed_key",
    "parse_control_acknowledgement",
    "provider_greeks_version",
    "segment_of",
    "subscribe_frame",
    "validate_feed_key",
    "unsubscribe_frame",
]
