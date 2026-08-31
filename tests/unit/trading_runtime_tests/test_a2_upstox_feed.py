"""C1 acceptance: real Upstox V3 runtime feed attached to the A2 runtime.

Proves the decoded normalized updates flow from the feed into the A2 session
controller's deterministic pipeline (marks, telemetry, engine) using a
deterministic replay source. No live session, no real orders.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

from ats.market.derivatives.option_universe import (
    build_dynamic_option_universe,
    fixture_contract_master,
)
from ats.market.feeds.upstox_v3.config import (
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)
from ats.market.feeds.upstox_v3.proto import FeedResponse
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    create_a2_paper_app,
)
from fastapi.testclient import TestClient


def _config():
    return UpstoxFeedConfiguration(
        wire_format=WireFormat.PROTOBUF_BINARY,
        client_guid="ats-c1-int",
        limits=UpstoxFeedLimits(maximum_silence_ms=3_000, stale_after_ms=5_000),
    )


def _auth():
    from pydantic import SecretStr

    return UpstoxFeedAuthorization(bearer_token=SecretStr("REPLAY_PLACEHOLDER"))


def _universe():
    from ats.contracts.common import SystemClock

    as_of = SystemClock().now()
    nifty = fixture_contract_master(
        underlying="NIFTY",
        spot=Decimal("25000"),
        expiry="2026-09-24",
        strike_step=Decimal("50"),
        lot_size=25,
        tick_size=Decimal("0.05"),
        half_width_strikes=10,
        as_of=as_of,
    )
    bank = fixture_contract_master(
        underlying="BANKNIFTY",
        spot=Decimal("57000"),
        expiry="2026-09-24",
        strike_step=Decimal("100"),
        lot_size=15,
        tick_size=Decimal("0.05"),
        half_width_strikes=10,
        as_of=as_of,
    )
    return build_dynamic_option_universe(
        contracts=nifty + bank,
        spots={"NIFTY": Decimal("25000"), "BANKNIFTY": Decimal("57000")},
        as_of=as_of,
    )


def _frame(quotes, ts_ms):
    response = FeedResponse()
    response.type = 1
    response.currentTs = ts_ms
    for k, v in quotes.items():
        response.feeds[k].ltpc.ltp = float(v)
        response.feeds[k].ltpc.cp = float(v)
        response.feeds[k].ltpc.ltt = ts_ms
    return response.SerializeToString()


def test_c1_feed_attached_to_a2_runtime():
    controller = A2PaperSessionController(
        config=A2PaperSessionConfig(require_live_instrument_evidence=True)
    )
    assert controller.start(require_token=False) is True

    universe = _universe()
    feed = UpstoxV3RuntimeFeed(authorization=_auth(), configuration=_config())
    feed.register_universe(universe)
    feed.connect_replay()
    controller.attach_upstox_runtime_feed(feed)
    assert controller.market_open_data_ready() is False

    now_ms = int(time.time() * 1000)
    frame_time = datetime.fromtimestamp(now_ms / 1000, UTC)
    quotes = {
        "NSE_INDEX|Nifty 50": 25012.5,
        "NSE_INDEX|Nifty Bank": 57103.25,
        universe[2].instrument_key: 120.5,
    }
    feed.ingest_frame(_frame(quotes, now_ms), received_at=frame_time)
    assert controller.market_open_data_ready() is False

    # Stage 2 becomes ready only when every key in the 22-key universe is fresh.
    complete_quotes = {item.instrument_key: Decimal("100") for item in universe}
    complete_quotes.update(
        {
            "NSE_INDEX|Nifty 50": Decimal("25012.5"),
            "NSE_INDEX|Nifty Bank": Decimal("57103.25"),
            universe[2].instrument_key: Decimal("120.5"),
        }
    )
    feed.ingest_frame(_frame(complete_quotes, now_ms), received_at=frame_time)
    assert controller.market_open_data_ready(now=frame_time) is True

    # Marks reached the A2 runtime feed adapter keyed by provider instrument key.
    assert controller.market_feed.latest_mark("NSE_INDEX|Nifty 50") == Decimal("25012.5")
    assert controller.market_feed.latest_mark("NSE_INDEX|Nifty Bank") == Decimal("57103.25")
    assert controller.market_feed.latest_mark(universe[2].instrument_key) == Decimal("120.5")

    # Telemetry truthfully reflects the decoded frames.
    tel = feed.telemetry()
    assert tel["upstox_raw_messages"] == 2
    assert tel["normalized_updates"] == 22
    assert tel["subscription_count"] == 22

    # Bridge captured the index updates under canonical identities.
    snap = controller._live_pipeline_bridge.snapshot_dict()
    assert snap["nifty_last"] == "25012.5"
    assert snap["banknifty_last"] == "57103.25"

    with TestClient(create_a2_paper_app(controller)) as client:
        telemetry = client.get("/v1/pipeline/counters").json()
    assert telemetry["subscription_count"] == 22
    assert telemetry["connection_state"] == "LIVE"
    assert telemetry["upstox_raw_messages"] == 2
    assert telemetry["normalized_messages"] == 22
