from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from ats.market.feeds.upstox_v3 import (
    UpstoxFeedError,
    UpstoxFeedErrorCode,
    UpstoxV3ProtobufDecoder,
)
from ats.market.feeds.upstox_v3.proto.MarketDataFeedV3_pb2 import FeedResponse

from .helpers import INDEX_KEY, OPTION_KEY

NOW = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)


def test_ltpc_binary_frame_normalizes_exact_prices_and_timestamps() -> None:
    frame = FeedResponse(type=1, currentTs=NOW_MS)
    frame.feeds[INDEX_KEY].ltpc.ltp = 24207.75
    frame.feeds[INDEX_KEY].ltpc.cp = 24100.5
    frame.feeds[INDEX_KEY].ltpc.ltt = NOW_MS - 20
    (update,) = UpstoxV3ProtobufDecoder().decode(
        frame.SerializeToString(), received_at=NOW
    )
    assert update.instrument_key == INDEX_KEY
    assert update.last_traded_price == Decimal("24207.75")
    assert update.close_price == Decimal("24100.5")
    assert update.exchange_timestamp is not None


def test_full_option_frame_carries_depth_oi_iv_and_all_provider_greeks() -> None:
    frame = FeedResponse(type=1, currentTs=NOW_MS)
    feed = frame.feeds[OPTION_KEY].fullFeed.marketFF
    feed.ltpc.ltp = 181.85
    feed.ltpc.cp = 170.0
    feed.ltpc.ltt = NOW_MS
    quote = feed.marketLevel.bidAskQuote.add()
    quote.bidP = 180.55
    quote.bidQ = 65
    quote.askP = 181.5
    quote.askQ = 130
    feed.vtt = 1000
    feed.oi = 3699605
    feed.iv = 0.13
    feed.optionGreeks.delta = 0.5
    feed.optionGreeks.gamma = 0.001
    feed.optionGreeks.theta = -5.0
    feed.optionGreeks.vega = 8.0
    feed.optionGreeks.rho = 2.0
    (update,) = UpstoxV3ProtobufDecoder().decode(
        frame.SerializeToString(), received_at=NOW
    )
    assert update.bid_price == Decimal("180.55")
    assert update.ask_price == Decimal("181.5")
    assert update.open_interest == 3699605
    assert update.implied_volatility == pytest.approx(0.13)
    assert update.rho == pytest.approx(2.0)
    assert update.greeks_method == "SOURCE_PROVIDED"
    assert update.market_depth is not None


def test_market_status_is_retained_without_inventing_instrument_update() -> None:
    frame = FeedResponse(type=2, currentTs=NOW_MS)
    frame.marketInfo.segmentStatus["NSE_FO"] = 2
    decoder = UpstoxV3ProtobufDecoder()
    assert decoder.decode(frame.SerializeToString(), received_at=NOW) == ()
    assert decoder.last_message_type == "market_info"
    assert decoder.last_market_status == {"NSE_FO": "NORMAL_OPEN"}


def test_missing_provider_timestamp_remains_explicitly_unknown() -> None:
    frame = FeedResponse(type=1)
    frame.feeds[INDEX_KEY].ltpc.ltp = 1
    (update,) = UpstoxV3ProtobufDecoder().decode(
        frame.SerializeToString(), received_at=NOW
    )
    assert update.exchange_timestamp is None


def test_malformed_and_non_finite_protobuf_fail_closed() -> None:
    decoder = UpstoxV3ProtobufDecoder()
    with pytest.raises(UpstoxFeedError) as malformed:
        decoder.decode(b"\xff", received_at=NOW)
    assert malformed.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME

    frame = FeedResponse(type=1, currentTs=NOW_MS)
    frame.feeds[OPTION_KEY].ltpc.ltp = float("nan")
    with pytest.raises(UpstoxFeedError) as non_finite:
        decoder.decode(frame.SerializeToString(), received_at=NOW)
    assert non_finite.value.code is UpstoxFeedErrorCode.MALFORMED_FRAME
