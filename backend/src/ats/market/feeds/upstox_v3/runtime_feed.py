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
        self._underlying_by_key: dict[str, str] = {}
        self._subscriptions_by_key: dict[str, Any] = {}
        self._reference_contracts_by_key: dict[str, Any] = {}
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
            self._subscriptions_by_key[sub.instrument_key] = sub
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
            self._underlying_by_key[sub.instrument_key] = str(sub.underlying)
            bucket = self._counters.by_underlying.setdefault(sub.underlying, {})
            bucket["subscriptions"] = bucket.get("subscriptions", 0) + 1

    def register_reference_contracts(self, contracts: tuple[Any, ...]) -> None:
        """Retain provider-normalized reference evidence for subscribed options."""

        self._reference_contracts_by_key = {
            item.provider_instrument_key: item
            for item in contracts
            if item.provider_instrument_key in self._subscriptions_by_key
        }

    @property
    def subscription_specs(self) -> tuple[Any, ...]:
        return tuple(self._subscriptions_by_key.values())

    @property
    def reference_contracts(self) -> tuple[Any, ...]:
        return tuple(self._reference_contracts_by_key.values())

    def latest(self, instrument_key: str) -> NormalizedFeedUpdate | None:
        return self._adapter.latest(instrument_key)

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
            underlying_bucket = self._counters.by_underlying.setdefault(
                self._underlying_by_key.get(key, "UNKNOWN"), {}
            )
            self._bump(underlying_bucket, "normalized")
            freshness = self._board.latch(key).evaluate(now)
            if freshness is SourceFreshness.FRESH:
                self._counters.fresh_updates += 1
                self._bump(self._counters.by_key[key], "fresh")
                self._bump(underlying_bucket, "fresh")
            else:
                self._counters.stale_updates += 1
                self._bump(self._counters.by_key[key], "stale")
                self._bump(underlying_bucket, "stale")
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
        now = self._clock.now()
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
            "freshness": self.freshness_summary(),
            "by_key": {k: dict(v) for k, v in self._counters.by_key.items()},
            "by_underlying": {k: dict(v) for k, v in self._counters.by_underlying.items()},
            "option_evidence": self._option_evidence_telemetry(now),
        }

    def _option_evidence_telemetry(self, now: UTCDateTime) -> list[dict[str, Any]]:
        freshness = self._board.evaluate(now)
        result: list[dict[str, Any]] = []
        for key, spec in self._subscriptions_by_key.items():
            if getattr(spec, "instrument_kind", None) != "OPTION":
                continue
            update = self._adapter.latest(key)
            provider_time = update.provider_timestamp if update is not None else None
            freshness_state = freshness.get(key)
            result.append(
                {
                    "instrument_key": key,
                    "underlying": spec.underlying,
                    "expiry": spec.expiry,
                    "strike": str(spec.strike),
                    "option_type": spec.option_type,
                    "lot_size": spec.lot_size,
                    "tick_size": str(spec.tick_size),
                    "freshness": (
                        freshness_state.value
                        if freshness_state is not None
                        else "UNKNOWN"
                    ),
                    "provider_timestamp": (
                        provider_time.isoformat() if provider_time is not None else None
                    ),
                    "ingest_timestamp": (
                        update.received_at.isoformat() if update is not None else None
                    ),
                    "provider_age_ms": (
                        int((now - provider_time).total_seconds() * 1000)
                        if provider_time is not None
                        else None
                    ),
                    "bid": str(update.bid_price) if update and update.bid_price else None,
                    "ask": str(update.ask_price) if update and update.ask_price else None,
                    "bid_quantity": update.bid_quantity if update else None,
                    "ask_quantity": update.ask_quantity if update else None,
                    "depth_buy_levels": (
                        len(update.market_depth.buy_levels)
                        if update and update.market_depth
                        else 0
                    ),
                    "depth_sell_levels": (
                        len(update.market_depth.sell_levels)
                        if update and update.market_depth
                        else 0
                    ),
                    "volume": update.volume if update else None,
                    "open_interest": update.open_interest if update else None,
                    "implied_volatility": (
                        update.implied_volatility if update else None
                    ),
                    "delta": update.delta if update else None,
                    "gamma": update.gamma if update else None,
                    "theta": update.theta if update else None,
                    "vega": update.vega if update else None,
                    "greeks_method": update.greeks_method if update else "UNAVAILABLE",
                }
            )
        return result

    @staticmethod
    def _bump(counter: dict[str, int], field: str) -> None:
        counter[field] = counter.get(field, 0) + 1


__all__ = [
    "NoopFeedConnection",
    "UpstoxV3RuntimeCounters",
    "UpstoxV3RuntimeFeed",
]
