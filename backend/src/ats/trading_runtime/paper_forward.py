"""PAPER_FORWARD bridge from Upstox V3 read-only data to the frozen A2 runtime."""

from __future__ import annotations

from decimal import Decimal

from ats.contracts.common import SystemClock
from ats.market.feeds.upstox_v3 import ReconciliationSource, UpstoxV3FeedAdapter, UpstoxV3Transport
from ats.market.feeds.upstox_v3.errors import UpstoxFeedError
from ats.trading_runtime.forward_validation import require_paper_only
from ats.trading_runtime.orchestrator import AutonomousPaperOrchestrator


class PaperForwardRunner:
    """Owns a read-only feed lifecycle and forwards normalized marks to A2.

    The runner has no live execution adapter or order-write dependency. Orders
    remain exclusively inside ``AutonomousPaperOrchestrator``'s canonical paper
    broker path.
    """

    def __init__(
        self,
        *,
        execution_mode: str | None,
        transport: UpstoxV3Transport,
        feed: UpstoxV3FeedAdapter,
        orchestrator: AutonomousPaperOrchestrator,
        reconciliation_source: ReconciliationSource,
    ) -> None:
        require_paper_only(execution_mode)
        self._transport = transport
        self._feed = feed
        self._orchestrator = orchestrator
        self._reconciliation_source = reconciliation_source
        self._clock = SystemClock()

    def run(self, *, maximum_frames: int | None = None) -> None:
        """Run until interrupted, then flatten/reconcile through A2 unchanged."""
        connection = self._transport.connect()
        self._feed.connect(connection)
        self._orchestrator.start(self._clock.now())
        handled = 0
        try:
            while maximum_frames is None or handled < maximum_frames:
                try:
                    payload = self._transport.receive()
                    outcome = self._feed.handle_frame(payload, received_at=self._clock.now())
                except UpstoxFeedError:
                    self._feed.disconnect()
                    connection = self._transport.reconnect()
                    self._feed.reconnect(connection)
                    self._feed.complete_resync(self._reconciliation_source, now=self._clock.now())
                    continue
                for key in outcome.applied_updates:
                    update = self._feed.latest(key)
                    if update is None or update.last_traded_price is None:
                        continue
                    identity = self._feed.canonical_identity(key)
                    self._orchestrator.bar(
                        identity,
                        close=Decimal(update.last_traded_price),
                        at=update.received_at,
                    )
                handled += 1
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Close market data then force existing paper flatten/reconciliation."""
        self._feed.disconnect()
        self._transport.close()
        self._orchestrator.request_shutdown(self._clock.now())


__all__ = ["PaperForwardRunner"]
