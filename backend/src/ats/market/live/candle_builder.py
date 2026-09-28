"""Incremental Multi-Timeframe Candle Engine for Live Market Data.

Enforces:
1. Bucket-based aggregation for 1s, 5s, 15s, 1m, 3m, 5m, 15m, 30m, 1h, 1d.
2. Invariant verification: high >= max(open, close), low <= min(open, close), high >= low.
3. True mutable current candle vs finalized closed candle.
4. Cumulative volume delta calculation without double-counting across reconnects.
5. Non-accumulative Open Interest state observation.
6. Clear labelling of sub-minute candles as ATS-DERIVED.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("ats.market.live.candle_builder")

# Supported intervals in seconds
INTERVAL_SECONDS: dict[str, int] = {
    "1s": 1,
    "5s": 5,
    "15s": 15,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "1d": 86400,
}


@dataclass
class LiveCandle:
    instrument_key: str
    interval: str
    bucket_start_epoch: int
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    open_interest: int | None = None
    final: bool = False
    is_derived: bool = False
    source: str = "BROKER"
    tick_count: int = 0
    volume_status: str = "EXACT"  # "EXACT", "PARTIAL", "UNKNOWN"
    created_at_epoch: float = field(default_factory=lambda: datetime.now(UTC).timestamp())
    updated_at_epoch: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

    @property
    def time_iso(self) -> str:
        return datetime.fromtimestamp(self.bucket_start_epoch, tz=UTC).isoformat()

    def validate_invariants(self) -> bool:
        """Enforces OHLC mathematical invariants."""
        return (
            self.high >= self.open
            and self.high >= self.close
            and self.low <= self.open
            and self.low <= self.close
            and self.high >= self.low
            and self.volume >= 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_key": self.instrument_key,
            "interval": self.interval,
            "time": self.time_iso,
            "bucket_start_epoch": self.bucket_start_epoch,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "open_interest": self.open_interest,
            "final": self.final,
            "is_derived": self.is_derived,
            "source": self.source,
            "tick_count": self.tick_count,
            "volume_status": self.volume_status,
            "updated_at_epoch": self.updated_at_epoch,
        }


class IncrementalCandleEngine:
    """Manages mutable working candles and finalized closed candles across intervals."""

    def __init__(
        self,
        instrument_key: str,
        intervals: list[str] | None = None,
        on_candle_update: Callable[[LiveCandle], None] | None = None,
        on_candle_closed: Callable[[LiveCandle], None] | None = None,
    ):
        self.instrument_key = instrument_key
        self.intervals = intervals or [
            "1s", "5s", "15s", "1m", "3m", "5m", "15m", "30m", "1h", "1d"
        ]
        self.on_candle_update = on_candle_update
        self.on_candle_closed = on_candle_closed

        # Active forming candles: interval -> LiveCandle
        self.active_candles: dict[str, LiveCandle] = {}
        # History of finalized candles: interval -> List[LiveCandle] (bounded)
        self.closed_candles: dict[str, list[LiveCandle]] = {itv: [] for itv in self.intervals}
        self.max_history_per_interval = 500

        # Volume state tracking to avoid double counting across reconnects
        self.last_vtt: int | None = None
        self.last_oi: int | None = None
        self.last_tick_epoch: float = 0.0

    def reset_volume_tracking(self) -> None:
        """Call on reconnect or instrument change to ensure volume deltas are re-anchored safely."""
        self.last_vtt = None

    def _get_bucket_epoch(self, timestamp_epoch: float, interval_seconds: int) -> int:
        return int(timestamp_epoch // interval_seconds) * interval_seconds

    def on_observation(
        self,
        ltp: float,
        timestamp_epoch: float,
        vtt: int | None = None,
        oi: int | None = None,
        source: str = "BROKER",
    ) -> list[tuple[str, LiveCandle]]:
        """Processes an incoming market observation (trade or quote with LTP).

        Returns list of (event_type, candle) where event_type is 'update' or 'closed'.
        """
        if ltp <= 0:
            return []

        events: list[tuple[str, LiveCandle]] = []
        now_epoch = datetime.now(UTC).timestamp()
        obs_epoch = timestamp_epoch if timestamp_epoch > 0 else now_epoch
        self.last_tick_epoch = obs_epoch

        # Compute volume delta if cumulative VTT is provided
        volume_delta = 0
        volume_status = "EXACT"
        if vtt is not None:
            if self.last_vtt is None:
                # First observation: anchor without synthesizing volume
                self.last_vtt = vtt
                volume_delta = 0
            elif vtt >= self.last_vtt:
                volume_delta = vtt - self.last_vtt
                self.last_vtt = vtt
            else:
                # Counter reset, session rollover or out-of-order VTT
                logger.warning(
                    "Cumulative volume dropped from %s to %s for %s. Marking partial.",
                    self.last_vtt,
                    vtt,
                    self.instrument_key,
                )
                self.last_vtt = vtt
                volume_delta = 0
                volume_status = "PARTIAL"
        else:
            volume_status = "UNKNOWN"

        if oi is not None:
            self.last_oi = oi

        # Process each configured interval
        for interval in self.intervals:
            sec = INTERVAL_SECONDS.get(interval, 60)
            bucket_epoch = self._get_bucket_epoch(obs_epoch, sec)
            is_sub_minute = sec < 60
            active = self.active_candles.get(interval)

            if active is None:
                # First candle for this interval
                new_candle = LiveCandle(
                    instrument_key=self.instrument_key,
                    interval=interval,
                    bucket_start_epoch=bucket_epoch,
                    open=ltp,
                    high=ltp,
                    low=ltp,
                    close=ltp,
                    volume=volume_delta,
                    open_interest=self.last_oi,
                    final=False,
                    is_derived=is_sub_minute,
                    source="ATS-DERIVED" if is_sub_minute else source,
                    tick_count=1,
                    volume_status=volume_status,
                    created_at_epoch=now_epoch,
                    updated_at_epoch=now_epoch,
                )
                self.active_candles[interval] = new_candle
                events.append(("update", new_candle))
                if self.on_candle_update:
                    self.on_candle_update(new_candle)

            elif bucket_epoch == active.bucket_start_epoch:
                # Same bucket: mutate current working candle
                active.high = max(active.high, ltp)
                active.low = min(active.low, ltp)
                active.close = ltp
                active.volume += volume_delta
                active.open_interest = self.last_oi
                active.tick_count += 1
                active.updated_at_epoch = now_epoch
                if volume_status != "EXACT":
                    active.volume_status = volume_status

                # Invariant sanity check
                if not active.validate_invariants():
                    logger.error("Candle invariant violation in %s: %s", interval, active)

                events.append(("update", active))
                if self.on_candle_update:
                    self.on_candle_update(active)

            elif bucket_epoch > active.bucket_start_epoch:
                # Interval boundary crossed: finalize active candle
                active.final = True
                active.updated_at_epoch = now_epoch
                self.closed_candles[interval].append(active)
                if len(self.closed_candles[interval]) > self.max_history_per_interval:
                    self.closed_candles[interval].pop(0)

                events.append(("closed", active))
                if self.on_candle_closed:
                    self.on_candle_closed(active)

                # Open brand new candle for new bucket
                new_candle = LiveCandle(
                    instrument_key=self.instrument_key,
                    interval=interval,
                    bucket_start_epoch=bucket_epoch,
                    open=ltp,
                    high=ltp,
                    low=ltp,
                    close=ltp,
                    volume=volume_delta,
                    open_interest=self.last_oi,
                    final=False,
                    is_derived=is_sub_minute,
                    source="ATS-DERIVED" if is_sub_minute else source,
                    tick_count=1,
                    volume_status=volume_status,
                    created_at_epoch=now_epoch,
                    updated_at_epoch=now_epoch,
                )
                self.active_candles[interval] = new_candle
                events.append(("update", new_candle))
                if self.on_candle_update:
                    self.on_candle_update(new_candle)
            else:
                # Late out-of-order event for an already finalized bucket
                logger.debug(
                    "Late observation for past bucket %s < active %s on %s (ignored)",
                    bucket_epoch,
                    active.bucket_start_epoch,
                    interval,
                )

        return events

    def get_active_candle(self, interval: str) -> LiveCandle | None:
        return self.active_candles.get(interval)

    def get_closed_candles(self, interval: str, limit: int = 100) -> list[LiveCandle]:
        history = self.closed_candles.get(interval, [])
        return history[-limit:]
