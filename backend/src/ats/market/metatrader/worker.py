"""Async lifecycle around blocking terminal reads; never controls paper authority."""

from __future__ import annotations

import asyncio

from ats.datasets.ingestion import data_root
from ats.market.fabric import MarketDataFabric
from ats.market.metatrader.connector import FeedState, MetaTraderConnector
from ats.market.metatrader.journal import ObservationJournal


class MetaTraderWorker:
    def __init__(self, connector: MetaTraderConnector, fabric: MarketDataFabric) -> None:
        self.connector = connector
        self.fabric = fabric
        self.journal = ObservationJournal(data_root() / "xauusd" / "live" / "standalone")
        self.task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self.task is not None and not self.task.done():
            return
        self._stopping.clear()
        self.task = asyncio.create_task(self._run())

    async def _pause(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stopping.wait(), seconds)
        except TimeoutError:
            pass

    async def _run(self) -> None:
        while not self._stopping.is_set():
            if self.connector.state in {FeedState.DISCONNECTED, FeedState.ERROR}:
                connected = await asyncio.to_thread(self.connector.connect)
                if not connected:
                    await self._pause(5)
                    continue
                if self.connector.metadata is not None:
                    self.fabric.tick_size = self.connector.metadata.tick_size
            observation = await asyncio.to_thread(self.connector.latest_tick)
            if observation is not None:
                try:
                    self.fabric.publish(observation, before_commit=self.journal.append)
                except Exception:
                    await asyncio.to_thread(self.connector.shutdown)
                    self.connector.state = FeedState.ERROR
                    self.connector.reason = "OBSERVATION_JOURNAL_OR_PUBLISH_FAILED"
                    return
            await self._pause(0.25)

    async def stop(self) -> None:
        self._stopping.set()
        if self.task:
            # Let bounded IPC complete before shutting down the shared terminal handle.
            await self.task
        await asyncio.to_thread(self.connector.shutdown)
