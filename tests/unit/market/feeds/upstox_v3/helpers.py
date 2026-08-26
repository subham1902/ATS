"""TEST_ONLY synthetic protocol fixtures for the Upstox V3 adapter.

Every frame in this module is an explicitly labelled TEST_ONLY message-shape
fixture. These bytes exist solely to exercise decoder and adapter logic and
must never be installed as historical trading data or shipped as a market
fixture (``ArtifactSourceClass.TEST_ONLY_SYNTHETIC``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ats.market.feeds.upstox_v3 import (
    FeedFreshnessBoard,
    FeedMode,
    JsonFeedPayloadDecoder,
    SubscriptionRegistry,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)

T0 = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)

INDEX_KEY = "NSE_INDEX|NIFTY 50"
OPTION_KEY = "NSE_FO|TEST_ONLY_TOKEN_1"
SECOND_OPTION_KEY = "NSE_FO|TEST_ONLY_TOKEN_2"
UNKNOWN_KEY = "NSE_FO|TEST_ONLY_UNKNOWN"

TEST_ONLY_SECRET = "test-only-not-a-real-token"


def configuration() -> UpstoxFeedConfiguration:
    return UpstoxFeedConfiguration(
        wire_format=WireFormat.JSON_TEXT,
        client_guid="d08-test-guid",
        limits=UpstoxFeedLimits(maximum_silence_ms=1_000, stale_after_ms=5_000),
    )


def authorization(*, with_token: bool = True) -> UpstoxFeedAuthorization:
    return UpstoxFeedAuthorization(
        bearer_token=TEST_ONLY_SECRET if with_token else None
    )


def decoder() -> JsonFeedPayloadDecoder:
    return JsonFeedPayloadDecoder(price_scale=Decimal("0.01"))


def registry() -> SubscriptionRegistry:
    registry = SubscriptionRegistry()
    registry.register(instrument_key=INDEX_KEY, ats_identity="UNDERLYING:NIFTY", mode=FeedMode.FULL)
    registry.register(
        instrument_key=OPTION_KEY, ats_identity="CONTRACT:TEST-ONLY-CE", mode=FeedMode.OPTION_GREEKS
    )
    registry.register(
        instrument_key=SECOND_OPTION_KEY,
        ats_identity="CONTRACT:TEST-ONLY-PE",
        mode=FeedMode.LTPC,
    )
    return registry


def freshness_board() -> FeedFreshnessBoard:
    board = FeedFreshnessBoard()
    for key in (INDEX_KEY, OPTION_KEY, SECOND_OPTION_KEY):
        board.register(instrument_key=key, stale_after_ms=5_000)
    return board


class FakeClock:
    """Deterministic clock advanced explicitly by tests."""

    def __init__(self, start: datetime = T0) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, *, milliseconds: int) -> datetime:
        self._now += timedelta(milliseconds=milliseconds)
        return self._now


class RecordingConnection:
    """TEST_ONLY connection seam capturing outbound text frames."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    def send_text(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.closed = True


def ltpc_frame(
    *,
    instrument_key: str,
    ltp: int,
    cp: int,
    ltt_ms: int,
    ts_ms: int,
) -> str:
    """TEST_ONLY JSON frame in the documented feeds-map shape."""

    return json.dumps(
        {
            "feeds": {
                instrument_key: {"ltpc": {"ltp": ltp, "cp": cp, "ltt": ltt_ms}},
            },
            "ts": ts_ms,
        }
    )


def full_option_frame(
    *,
    instrument_key: str,
    ltp: int,
    bid: int,
    ask: int,
    volume: int,
    oi: int,
    delta: float,
    iv: float,
    ts_ms: int,
) -> str:
    """TEST_ONLY option frame carrying market_data plus provider Greeks."""

    return json.dumps(
        {
            "feeds": {
                instrument_key: {
                    "ltpc": {"ltp": ltp, "cp": 10000, "ltt": ts_ms},
                    "market_data": {
                        "bid": bid,
                        "ask": ask,
                        "bid_qty": 500,
                        "ask_qty": 700,
                        "vol": volume,
                        "oi": oi,
                        "change_oi": 25,
                    },
                    "option_greeks": {"delta": delta, "iv": iv},
                }
            },
            "ts": ts_ms,
        }
    )
