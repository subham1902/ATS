"""Read-only terminal observations enter the unchanged deterministic paper path."""

from ats.market.domain import require_xauusd
from ats.market.metatrader.connector import MetaTraderConnector
from ats.trading_runtime.orchestrator import AutonomousPaperOrchestrator


class PaperForwardRunner:
    def __init__(
        self, connector: MetaTraderConnector, orchestrator: AutonomousPaperOrchestrator
    ) -> None:
        self.connector = connector
        self.orchestrator = orchestrator

    def observe(self) -> bool:
        tick = self.connector.latest_tick()
        if tick is None or self.connector.health()["state"] != "LIVE" or tick.chart_price is None:
            return False
        require_xauusd(tick.canonical_symbol)
        self.orchestrator.tick("XAUUSD", tick.chart_price, tick.timestamp)
        return True
