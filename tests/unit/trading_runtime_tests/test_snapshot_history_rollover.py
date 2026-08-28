"""Regression coverage for live intraday feature-history rollover."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from ats.contracts.common import SystemClock
from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.trading_runtime.a2_runner import (
    A2PaperSessionController,
    UpstoxMarketFeedAdapter,
)


def test_scanner_rehashes_snapshot_history_when_warmup_window_rolls() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)

    now = SystemClock().now()
    bar_time = now - timedelta(
        minutes=now.minute % 5,
        seconds=now.second,
        microseconds=now.microsecond,
    )
    snapshots: list[MarketSnapshot] = []
    for index in range(20):
        stamp = bar_time - timedelta(minutes=5 * (20 - index))
        snapshot = MarketSnapshot(
            schema_version="1.0",
            snapshot_id=uuid4(),
            instrument_id="NIFTY",
            exchange="NSE",
            segment="CASH",
            timeframe="5m",
            sequence=index + 1,
            bar_timestamp=stamp,
            received_at=stamp,
            open=Decimal("24500"),
            high=Decimal("24510"),
            low=Decimal("24490"),
            close=Decimal("24500"),
            volume=Decimal("1000"),
            quality_state=DataQualityState.GOOD,
            quality_flags=(),
            source="UPSTOX_INTRADAY_V3",
            source_version="3.0.0",
            session_state=SessionState.OPEN,
            payload_hash="0" * 64,
        )
        snapshots.append(
            snapshot.model_copy(update={"payload_hash": compute_payload_hash(snapshot)})
        )

    controller.seed_snapshot_history("NIFTY", snapshots)
    feed.set_mark("NIFTY", Decimal("24501"), at=now)

    controller.scan_market_for_candidates(now=now)

    assert not any(
        code.startswith("FEATURE_ERROR_")
        for code in controller.pipeline_counters().rejection_reason_codes
    )
    assert all(
        snapshot.payload_hash == compute_payload_hash(snapshot)
        for snapshot in controller._snapshot_history["NIFTY"]
    )
    controller.stop()
