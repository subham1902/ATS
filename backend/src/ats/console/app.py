"""Operator console application factory.

This is the **served** ATS application (``uvicorn ats.console.app:app``). It is a
different boundary from the A05 read-only control surface in :mod:`ats.api`:

* it mounts the operator workbench routers (market data, strategy registry,
  strategy lab, datasets, agents, optimizations, settings, broker manifest,
  AI/Laya bridge) on top of the A05 projection;
* it owns the process lifespan -- market journal, live feed worker, continuous
  optimization worker and the agents playground worker;
* it serves the market WebSocket channels.

It holds **no financial authority**. It cannot construct an ``OrderIntent``,
cannot mint an ``AutonomyToken`` and cannot route to a broker gateway; order
authorization remains exclusively in the A04 authority chain. That boundary is
enforced by ``tests/contract/api/test_console_boundary.py``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ats.api.app import _register_exception_handlers, build_a05_router
from ats.api.providers import ControlPlaneReader
from ats.market.fabric import MarketDataFabric

from .ai_router import router as ai_router
from .broker_router import router as broker_router
from .datasets_router import router as datasets_router
from .governance_router import router as governance_router
from .imported_strategies_router import router as imported_strategies_router
from .laya_router import router as laya_router
from .market_router import router as market_router
from .providers import LiveControlPlaneReader
from .runtime_router import router as runtime_router
from .settings_router import router as settings_router
from .strategy_lab_router import router as strategy_lab_router
from .strategy_registry import router as strategy_registry_router

CONSOLE_ROUTERS = (
    runtime_router,
    market_router,
    imported_strategies_router,
    strategy_registry_router,
    settings_router,
    broker_router,
    ai_router,
    governance_router,
    strategy_lab_router,
    laya_router,
    datasets_router,
)


def _seed_demo_fabric(fabric: MarketDataFabric) -> None:
    """Attach a single synthetic GOLDM tick so the console has a first paint.

    This is a DEMO seed only. It is published once at startup so an operator can
    see the console render without a broker session; it is not market data and
    must never be treated as a price signal. Live sessions overwrite it as soon
    as a provider attaches.
    """
    from datetime import datetime
    from decimal import Decimal

    from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate, UpdateKind

    now = datetime.now(UTC)
    fabric.publish(
        NormalizedFeedUpdate(
            instrument_key="MCX_FO|569003",
            kind=UpdateKind.OPTION,
            received_at=now,
            exchange_timestamp=now,
            last_traded_price=Decimal("75420.00"),
            close_price=Decimal("75250.00"),
            bid_price=Decimal("75418.00"),
            ask_price=Decimal("75422.00"),
            bid_quantity=10,
            ask_quantity=10,
            volume=14520,
            open_interest=3240,
        )
    )


def create_console_app(
    reader: ControlPlaneReader | None = None,
    fabric: MarketDataFabric | None = None,
) -> FastAPI:
    """Create the served operator console app (workbench + A05 projection)."""
    from ats.agents.managed_router import router as managed_agents_router
    from ats.agents.router import router as agents_router
    from ats.optimization.router import router as optimization_router
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        from ats.market.live.candle_builder import IncrementalCandleEngine
        from ats.market.live.journal import MarketJournal
        from ats.market.live.stream_hub import hub
        from ats.market.live.upstox_v3 import UpstoxV3LiveWorker

        journal = MarketJournal()
        journal.start()
        app_instance.state.market_journal = journal

        candle_engine = IncrementalCandleEngine(
            instrument_key="MCX_FO|569003",
            intervals=["1s", "5s", "15s", "1m", "3m", "5m", "15m", "30m", "1h", "1d"],
        )
        app_instance.state.candle_engine = candle_engine
        app_instance.state.stream_hub = hub

        token = (
            os.environ.get("ATS_UPSTOX_ANALYTICS_TOKEN")
            or os.environ.get("UPSTOX_ACCESS_TOKEN")
            or os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        )
        worker = None
        if token and token.strip():
            worker = UpstoxV3LiveWorker(
                token=token.strip(),
                fabric=app_instance.state.market_fabric,
                candle_engine=candle_engine,
                journal=journal,
                hub=hub,
                primary_instrument="MCX_FO|569003",
                mode="full",
            )
            worker.start()
        app_instance.state.upstox_worker = worker

        from ats.optimization.worker import OptimizationWorker

        opt_worker = OptimizationWorker(
            fabric=app_instance.state.market_fabric,
            candle_engine=candle_engine,
            journal=journal,
        )
        opt_worker.start()
        app_instance.state.opt_worker = opt_worker

        from ats.agents.worker import AgentsWorker

        agt_worker = AgentsWorker(fabric=app_instance.state.market_fabric)
        agt_worker.start()
        app_instance.state.agt_worker = agt_worker

        try:
            yield
        finally:
            if worker:
                await worker.stop()
            if opt_worker:
                await opt_worker.stop()
            if agt_worker:
                await agt_worker.stop()
            journal.stop()

    app = FastAPI(
        title="ATS Operator Console",
        version="2.0.0",
        description=(
            "ATS Operator Console — research workbench and market data. "
            "Holds no financial authority; A04 remains the sole order authority."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if fabric is None:
        fabric = MarketDataFabric(
            source_label="UPSTOX_V3", authority_class="LIVE_FEED_ATTACHED"
        )
        _seed_demo_fabric(fabric)
    app.state.market_fabric = fabric
    app.state.trading_runtime_provider = TradingRuntimeProvider()
    app.state.control_plane_reader = reader or LiveControlPlaneReader(
        app.state.trading_runtime_provider
    )

    _register_exception_handlers(app)
    app.include_router(build_a05_router())
    for router in CONSOLE_ROUTERS:
        app.include_router(router)
    app.include_router(optimization_router)
    app.include_router(agents_router)
    app.include_router(managed_agents_router)

    @app.websocket("/v1/stream/market")
    async def stream_market_ws(websocket: WebSocket) -> None:
        """ATS live market stream WebSocket endpoint."""
        await websocket.accept()
        from ats.market.live.stream_hub import hub

        await hub.register(websocket)
        try:
            while True:
                text = await websocket.receive_text()
                await hub.handle_client_message(websocket, text)
        except WebSocketDisconnect:
            pass
        finally:
            await hub.unregister(websocket)

    @app.websocket("/v1/market/ws")
    async def market_ws_alias(websocket: WebSocket) -> None:
        """Alias for market stream WebSocket."""
        await stream_market_ws(websocket)

    return app


app = create_console_app()

__all__ = ["CONSOLE_ROUTERS", "app", "create_console_app"]
