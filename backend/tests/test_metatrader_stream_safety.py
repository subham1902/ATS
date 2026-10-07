import asyncio
from datetime import timedelta

from ats.market.domain import XauUsdDomain
from ats.market.fabric import MarketDataFabric, PublishOutcome
from ats.market.metatrader.connector import FeedState, MetaTraderConnector
from ats.market.metatrader.worker import MetaTraderWorker

from backend.tests.test_xauusd_foundation import NOW, Clock, FakeTransport


def test_poll_thread_delivers_to_event_loop_and_slow_subscriber_is_bounded():
    async def run():
        asyncio.get_running_loop().set_debug(True)
        fabric = MarketDataFabric(clock=Clock())
        subscriber = fabric.subscribe(maxsize=1)
        connector = MetaTraderConnector(XauUsdDomain(), FakeTransport(), clock=lambda: NOW)
        assert connector.connect()
        tick = connector.latest_tick()
        waiting = asyncio.create_task(subscriber.get(timeout=1))
        await asyncio.sleep(0)
        assert await asyncio.to_thread(fabric.publish, tick) == PublishOutcome.ACCEPTED
        assert await waiting == tick
        updates = [
            tick.model_copy(update={"timestamp": NOW - timedelta(seconds=i)})
            for i in range(3, 0, -1)
        ]
        # Use a new fabric so ordered synthetic observations are accepted.
        fabric = MarketDataFabric(clock=Clock())
        subscriber.close()
        subscriber = fabric.subscribe(maxsize=1)
        await asyncio.to_thread(fabric.publish_many, updates)
        await asyncio.sleep(0)
        assert await subscriber.get(timeout=1) == updates[-1]
        subscriber.close()
        assert fabric.subscriber_count() == 0

    asyncio.run(run())


def test_standalone_journal_failure_blocks_fanout_and_reports_error():
    async def run():
        connector = MetaTraderConnector(XauUsdDomain(), FakeTransport(), clock=lambda: NOW)
        fabric = MarketDataFabric(clock=Clock())
        worker = MetaTraderWorker(connector, fabric)

        def fail(_observation):
            raise OSError("synthetic disk failure")

        worker.journal.append = fail
        worker.start()
        await asyncio.wait_for(worker.task, 2)
        assert connector.health()["state"] == FeedState.ERROR
        assert connector.health()["reason"] == "OBSERVATION_JOURNAL_OR_PUBLISH_FAILED"
        assert fabric.latest("XAUUSD") is None
        assert fabric.counters().accepted == 0
        await worker.stop()

    asyncio.run(run())
