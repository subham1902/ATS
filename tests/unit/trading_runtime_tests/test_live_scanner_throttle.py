"""Regression coverage for bounded scanner work on the live feed reader."""

from datetime import timedelta
from decimal import Decimal

from ats.contracts.common import SystemClock
from ats.market.feeds.upstox_v3.config import (
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    WireFormat,
)
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed
from ats.observability.live_pipeline_bridge import LivePipelineBridge
from ats.trading_runtime.a2_runner import (
    A2PaperSessionController,
    UpstoxMarketFeedAdapter,
)
from pydantic import SecretStr


def test_live_scanner_is_bounded_to_configured_loop_interval() -> None:
    market_feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=market_feed)
    runtime_feed = UpstoxV3RuntimeFeed(
        authorization=UpstoxFeedAuthorization(
            bearer_token=SecretStr("REPLAY_PLACEHOLDER")
        ),
        configuration=UpstoxFeedConfiguration(
            wire_format=WireFormat.PROTOBUF_BINARY,
            client_guid="scanner-throttle-test",
            limits=UpstoxFeedLimits(
                maximum_silence_ms=5_000,
                stale_after_ms=10_000,
            ),
        ),
    )
    controller.attach_upstox_runtime_feed(runtime_feed)
    controller.start(require_token=False)

    now = SystemClock().now()
    controller.process_tick("NIFTY", Decimal("24500"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("57000"), at=now)
    assert controller.pipeline_counters().scanner_observations == 1

    controller.process_tick(
        "NIFTY", Decimal("24501"), at=now + timedelta(milliseconds=100)
    )
    assert controller.pipeline_counters().scanner_observations == 1

    controller.process_tick(
        "NIFTY", Decimal("24502"), at=now + timedelta(milliseconds=1100)
    )
    assert controller.pipeline_counters().scanner_observations == 2
    controller.stop()


def test_feed_freshness_does_not_mutate_autonomous_scanner_count() -> None:
    bridge = LivePipelineBridge()
    bridge.counters.scanner_observations = 7

    bridge.record_freshness(fresh_count=1)

    assert bridge.counters.scanner_observations == 7
    assert bridge.counters.fresh_messages == 1
