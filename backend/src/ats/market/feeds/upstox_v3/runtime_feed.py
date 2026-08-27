"""Runtime feed wrapper binding the Upstox V3 transport into the A2 pipeline.

Owns the read-only :class:`UpstoxV3FeedAdapter`, its freshness board and
subscription registry, and exposes canonical runtime telemetry. The wrapper is
transport-agnostic: a live websocket or a deterministic replay source feed the
same ``ingest_frame`` seam, so the full decode -> normalize -> freshness ->
runtime chain is provable offline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from ats.contracts.common import ClockProtocol, SystemClock, UTCDateTime
from ats.market.derivatives.providers.models import SourceFreshness
from ats.market.feeds.upstox_v3.adapter import ConnectionState, UpstoxV3FeedAdapter
from ats.market.feeds.upstox_v3.codec import FeedPayloadDecoder
from ats.market.feeds.upstox_v3.config import (
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
)
from ats.market.feeds.upstox_v3.freshness import FeedFreshnessBoard
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate
from ats.market.feeds.upstox_v3.protobuf_codec import UpstoxV3ProtobufDecoder
from ats.market.feeds.upstox_v3.subscription import SubscriptionRegistry
from ats.market.feeds.upstox_v3.transport import UpstoxV3Transport

NormalizedHandler = Callable[[NormalizedFeedUpdate, SourceFreshness], None]


@dataclass
class UpstoxV3RuntimeCounters:
    upstox_raw_messages: int = 0
    protobuf_frames_decoded: int = 0
    normalized_updates: int = 0
    fresh_updates: int = 0
    stale_updates: int = 0
    unknown_updates: int = 0
    malformed_frames: int = 0
    by_key: dict[str, dict[str, int]] = field(default_factory=dict)
    by_underlying: dict[str, dict[str, int]] = field(default_factory=dict)


class NoopFeedConnection:
    """FeedConnection that records (and ignores) outbound control frames."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_text(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        return None


class UpstoxV3RuntimeFeed:
    """Binds a read-only Upstox V3 feed into the A2 runtime with truthful counters."""

    def __init__(
        self,
        *,
        authorization: UpstoxFeedAuthorization,
        configuration: UpstoxFeedConfiguration,
        decoder: Any | None = None,
        clock: ClockProtocol | None = None,
        on_normalized: NormalizedHandler | None = None,
    ) -> None:
        self._authorization = authorization
        self._configuration = configuration
        self._decoder = cast(
            "FeedPayloadDecoder", decoder if decoder is not None else UpstoxV3ProtobufDecoder()
        )
        self._clock = clock or SystemClock()
        self._registry = SubscriptionRegistry()
        self._board = FeedFreshnessBoard()
        self._adapter = UpstoxV3FeedAdapter(
            configuration=configuration,
            authorization=authorization,
            registry=self._registry,
            freshness_board=self._board,
            decoder=self._decoder,
            clock=self._clock,
        )
        self._transport: UpstoxV3Transport | None = None
        self._counters = UpstoxV3RuntimeCounters()
        self._on_normalized = on_normalized
        self._stale_after_ms = configuration.limits.stale_after_ms

    @property
    def adapter(self) -> UpstoxV3FeedAdapter:
        return self._adapter

    @property
    def registry(self) -> SubscriptionRegistry:
        return self._registry

    @property
    def board(self) -> FeedFreshnessBoard:
        return self._board

    @property
    def counters(self) -> UpstoxV3RuntimeCounters:
        return self._counters

    @property
    def connection_state(self) -> ConnectionState:
        return self._adapter.state

    def register_universe(self, subscriptions: tuple[Any, ...]) -> None:
        from ats.market.derivatives.option_universe import OptionUniverseSubscription

        for sub in subscriptions:
            if isinstance(sub, OptionUniverseSubscription):
                self._registry.register(
                    instrument_key=sub.instrument_key,
                    ats_identity=sub.ats_identity,
                    mode=sub.mode,
                )
            else:
                self._registry.register(
                    instrument_key=sub.instrument_key,
                    ats_identity=sub.ats_identity,
                    mode=sub.mode,
                )
            self._board.register(
                instrument_key=sub.instrument_key, stale_after_ms=self._stale_after_ms
            )
            self._counters.by_key.setdefault(sub.instrument_key, {})
            bucket = self._counters.by_underlying.setdefault(sub.underlying, {})
            bucket["subscriptions"] = bucket.get("subscriptions", 0) + 1

    def attach_transport(self, transport: UpstoxV3Transport) -> None:
        self._transport = transport

    def connect_live(self) -> None:
        if self._transport is None:
            raise RuntimeError("attach_transport must be called before connect_live")
        connection = self._transport.connect()
        self._adapter.connect(connection)

    def receive_live(self) -> int:
        """Receive and ingest one frame from the attached read-only transport."""

        if self._transport is None:
            raise RuntimeError("attach_transport must be called before receive_live")
        return self.ingest_frame(self._transport.receive())

    def disconnect_live(self) -> None:
        """Close the live market-data transport and fail freshness closed."""

        self._adapter.disconnect()
        if self._transport is not None:
            self._transport.close()

    def connect_replay(self) -> None:
        """Enter LIVE state without a socket for deterministic offline ingestion."""

        connection = NoopFeedConnection()
        self._adapter.connect(connection)
        self._state_for_replay = ConnectionState.LIVE

    def ingest_frame(self, frame: bytes | str, *, received_at: UTCDateTime | None = None) -> int:
        """Decode one binary/JSON frame and update runtime telemetry.

        Returns the number of normalized updates applied from this frame.
        """

        now = received_at or self._clock.now()
        self._counters.upstox_raw_messages += 1
        try:
            outcome = self._adapter.handle_frame(frame, received_at=now)
        except Exception:
            self._counters.malformed_frames += 1
            return 0

        self._counters.protobuf_frames_decoded += 1
        applied = 0
        for key in outcome.applied_updates:
            self._counters.normalized_updates += 1
            applied += 1
            self._bump(self._counters.by_key.setdefault(key, {}), "normalized")
            freshness = self._board.latch(key).evaluate(now)
            if freshness is SourceFreshness.FRESH:
                self._counters.fresh_updates += 1
                self._bump(self._counters.by_key[key], "fresh")
            else:
                self._counters.stale_updates += 1
                self._bump(self._counters.by_key[key], "stale")
            if self._on_normalized is not None:
                update = self._adapter.latest(key)
                if update is not None:
                    self._on_normalized(update, freshness)
        for _key in outcome.unknown_keys:
            self._counters.unknown_updates += 1
        return applied

    def freshness_summary(self, *, now: UTCDateTime | None = None) -> dict[str, str]:
        stamp = now or self._clock.now()
        return {key: state.value for key, state in self._board.evaluate(stamp).items()}

    def telemetry(self) -> dict[str, Any]:
        return {
            "upstox_raw_messages": self._counters.upstox_raw_messages,
            "protobuf_frames_decoded": self._counters.protobuf_frames_decoded,
            "normalized_updates": self._counters.normalized_updates,
            "fresh_updates": self._counters.fresh_updates,
            "stale_updates": self._counters.stale_updates,
            "unknown_updates": self._counters.unknown_updates,
            "malformed_frames": self._counters.malformed_frames,
            "subscription_count": len(self._registry),
            "connection_state": self._adapter.state.value,
            "by_key": {k: dict(v) for k, v in self._counters.by_key.items()},
            "by_underlying": {k: dict(v) for k, v in self._counters.by_underlying.items()},
        }

    @staticmethod
    def _bump(counter: dict[str, int], field: str) -> None:
        counter[field] = counter.get(field, 0) + 1


__all__ = [
    "NoopFeedConnection",
    "UpstoxV3RuntimeCounters",
    "UpstoxV3RuntimeFeed",
]
