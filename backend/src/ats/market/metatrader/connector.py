"""Read-only terminal connector with injectable transports and explicit health."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from ats.market.domain import InstrumentMetadata, XauUsdDomain, require_xauusd
from ats.market.metatrader.clock import BrokerClockEvidence
from ats.market.observations import MarketObservation, VolumeProvenance


class FeedState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    LIVE = "LIVE"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class TerminalTransport(Protocol):
    def initialize(self) -> bool: ...
    def symbol_info(self, symbol: str) -> Mapping[str, Any] | None: ...
    def latest_tick(self, symbol: str) -> Mapping[str, Any] | None: ...
    def historical_ticks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]: ...
    def historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]: ...
    def shutdown(self) -> None: ...


class MetaTraderConnector:
    def __init__(
        self,
        domain: XauUsdDomain,
        transport: TerminalTransport,
        clock: Callable[[], datetime] | None = None,
        clock_evidence: BrokerClockEvidence | None = None,
    ) -> None:
        self.domain = domain
        self.transport = transport
        self.clock = clock or (lambda: datetime.now(UTC))
        self.clock_evidence = clock_evidence
        self.state = FeedState.DISCONNECTED
        self.reason = "TERMINAL_NOT_CONNECTED"
        self.metadata: InstrumentMetadata | None = None
        self.last_observation: MarketObservation | None = None
        self.reconnect_count = 0

    def initialize(self) -> bool:
        return self.connect()

    def connect(self) -> bool:
        self.state = FeedState.CONNECTING
        self.metadata = None
        self.last_observation = None
        try:
            if not self.transport.initialize():
                raise ValueError("TERMINAL_INITIALIZATION_FAILED")
            self.metadata = self.symbol_info()
            self.state = FeedState.DEGRADED
            self.reason = "AWAITING_OBSERVED_TICK"
            return True
        except Exception:
            # A vendor exception may contain credentials; never surface its text.
            self.state = FeedState.ERROR
            self.reason = "TERMINAL_UNAVAILABLE_OR_SYMBOL_METADATA_INVALID"
            try:
                self.transport.shutdown()
            except Exception:
                pass
            return False

    def symbol_info(self, symbol: str = "XAUUSD") -> InstrumentMetadata:
        require_xauusd(symbol)
        raw = self.transport.symbol_info(self.domain.broker_symbol)
        if raw is None or raw.get("name") != self.domain.broker_symbol:
            raise ValueError("BROKER_SYMBOL_UNAVAILABLE")
        if raw.get("currency_base") not in {None, "", "XAU"} or raw.get("currency_profit") not in {
            None,
            "",
            "USD",
        }:
            raise ValueError("BROKER_SYMBOL_IS_NOT_XAUUSD")
        return InstrumentMetadata(
            broker_symbol=self.domain.broker_symbol,
            digits=raw["digits"],
            point=Decimal(str(raw["point"])),
            tick_size=Decimal(str(raw["trade_tick_size"])),
            contract_size=Decimal(str(raw["trade_contract_size"])),
            volume_min=Decimal(str(raw["volume_min"])),
            volume_max=Decimal(str(raw["volume_max"])),
            volume_step=Decimal(str(raw["volume_step"])),
            trade_mode=raw["trade_mode"],
            as_of_time=self.clock(),
            source=self.domain.provider,
        )

    def normalize(
        self, raw: Mapping[str, Any], *, timeframe: str | None = None
    ) -> MarketObservation:
        if raw.get("symbol", self.domain.broker_symbol) != self.domain.broker_symbol:
            raise ValueError("BROKER_SYMBOL_MISMATCH")
        millis = raw.get("time_msc")
        seconds = raw.get("time")
        if millis is None and seconds is None:
            raise ValueError("SOURCE_TIMESTAMP_MISSING")
        raw_timestamp = millis if millis is not None else seconds
        assert raw_timestamp is not None
        stamp = datetime.fromtimestamp(
            float(raw_timestamp) / (1000 if millis is not None else 1), UTC
        )
        now = self.clock()
        evidence = self.clock_evidence
        if evidence is not None:
            if timeframe or raw.get("_historical"):
                raise ValueError("HISTORICAL_CLOCK_PROFILE_REQUIRED")
            stamp = evidence.normalize(
                int(float(raw_timestamp) * (1 if millis is not None else 1000)),
                raw.get("server"),
                now,
            )
        if stamp > now:
            raise ValueError("FUTURE_SOURCE_TIMESTAMP")
        fields: dict[str, Any] = {}
        for key in (
            "bid",
            "ask",
            "last",
            "volume",
            "tick_volume",
            "real_volume",
            "open",
            "high",
            "low",
            "close",
        ):
            val = raw.get(key)
            # MT terminal zero price/real-volume means unavailable, not an observed trade.
            if val is not None and not (key in {"bid", "ask", "last", "real_volume"} and val == 0):
                fields[key] = Decimal(str(val))
        volume_kind = VolumeProvenance.UNKNOWN
        if "volume" in fields:
            volume_kind = VolumeProvenance.BROKER_VOLUME
        elif "real_volume" in fields:
            volume_kind = VolumeProvenance.REAL_VOLUME
        elif "tick_volume" in fields:
            volume_kind = VolumeProvenance.TICK_VOLUME
        observation = MarketObservation(
            broker_symbol=self.domain.broker_symbol,
            timestamp=stamp,
            received_at=now,
            source=self.domain.provider,
            provenance="BROKER_BAR" if timeframe else "BROKER_TICK_PROXY",
            timestamp_provenance="VERIFIED_SERVER_WALL_LIVE_ONLY"
            if evidence
            else str(raw.get("timestamp_provenance", "SOURCE_UTC")),
            raw_source_epoch_ms=int(float(raw_timestamp) * (1 if millis is not None else 1000)),
            clock_evidence_hash=evidence.evidence_hash if evidence else None,
            flags=raw.get("flags"),
            timeframe=timeframe,
            volume_provenance=volume_kind,
            **fields,
        )
        if observation.available_at > now:
            raise ValueError("BAR_NOT_CLOSED")
        return observation

    def latest_tick(self, symbol: str = "XAUUSD") -> MarketObservation | None:
        require_xauusd(symbol)
        if self.state in {FeedState.DISCONNECTED, FeedState.ERROR, FeedState.CONNECTING}:
            return None
        try:
            raw = self.transport.latest_tick(self.domain.broker_symbol)
            if raw is None:
                self.state, self.reason = FeedState.DEGRADED, "NO_OBSERVED_TICK"
                return None
            observation = self.normalize(raw)
            self.last_observation = observation
            age = (self.clock() - observation.timestamp).total_seconds()
            self.state = (
                FeedState.STALE if age > self.domain.stale_after_seconds else FeedState.LIVE
            )
            self.reason = "TICK_STALE" if self.state == FeedState.STALE else "OBSERVED_BROKER_TICK"
            return observation
        except Exception as error:
            # Surface only a closed set of our own validation codes.
            code = str(error) if type(error) is ValueError else ""
            reason = (
                code
                if code
                in {
                    "FUTURE_SOURCE_TIMESTAMP",
                    "SOURCE_TIMESTAMP_MISSING",
                    "BROKER_SYMBOL_MISMATCH",
                    "BAR_NOT_CLOSED",
                    "CLOCK_SERVER_MISMATCH",
                    "CLOCK_EVIDENCE_EXPIRED",
                }
                else "MALFORMED_OR_UNAVAILABLE_TICK"
            )
            self.state, self.reason = FeedState.DEGRADED, reason
            return None

    def historical_ticks(self, start: datetime, end: datetime) -> tuple[MarketObservation, ...]:
        self._validate_range(start, end)
        return tuple(
            self.normalize({**row, "_historical": True})
            for row in self.transport.historical_ticks(self.domain.broker_symbol, start, end)
        )

    def historical_bars(
        self, timeframe: str, start: datetime, end: datetime
    ) -> tuple[MarketObservation, ...]:
        self._validate_range(start, end)
        return tuple(
            self.normalize(row, timeframe=timeframe)
            for row in self.transport.historical_bars(
                self.domain.broker_symbol, timeframe, start, end
            )
        )

    @staticmethod
    def _validate_range(start: datetime, end: datetime) -> None:
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("HISTORY_RANGE_REQUIRES_ORDERED_AWARE_TIMESTAMPS")

    def health(self) -> dict[str, Any]:
        last = self.last_observation
        age = (self.clock() - last.timestamp).total_seconds() if last else None
        state = self.state
        if state == FeedState.LIVE and age is not None and age > self.domain.stale_after_seconds:
            state = FeedState.STALE
        return {
            "provider": self.domain.provider,
            "state": state.value,
            "canonical_symbol": "XAUUSD",
            "source_symbol": self.domain.broker_symbol,
            "last_tick_timestamp": last.timestamp.isoformat() if last else None,
            "received_at": last.received_at.isoformat() if last else None,
            "feed_age_seconds": age,
            "spread": str(last.ask - last.bid)
            if last and last.ask is not None and last.bid is not None
            else None,
            "reason": "TICK_STALE" if state == FeedState.STALE else self.reason,
            "reconnect_count": self.reconnect_count,
        }

    def reconnect(self) -> bool:
        self.shutdown()
        self.reconnect_count += 1
        return self.connect()

    def shutdown(self) -> None:
        self.transport.shutdown()
        self.state, self.reason = FeedState.DISCONNECTED, "TERMINAL_DISCONNECTED"
