"""XAUUSD operator console; deterministic A04 retains all financial authority."""

from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from ats.agents.managed_router import router as managed_router
from ats.api.app import _register_exception_handlers, build_a05_router
from ats.api.providers import ControlPlaneReader
from ats.console.accounts_router import router as accounts_router
from ats.console.accounts_router import service_of
from ats.console.ai_router import router as ai_router
from ats.console.cors import resolve_cors_origins
from ats.console.datasets_router import router as datasets_router
from ats.console.market_router import router as market_router
from ats.console.providers import LiveControlPlaneReader
from ats.console.runtime_router import router as runtime_router
from ats.console.strategy_os_router import router as strategy_os_router
from ats.console.strategy_registry import router as strategy_router
from ats.market.domain import XauUsdDomain
from ats.market.fabric import MarketDataFabric
from ats.market.metatrader.account_service import AccountService
from ats.market.metatrader.clock import load_clock_evidence
from ats.market.metatrader.connector import MetaTraderConnector
from ats.market.metatrader.mt4 import Mt4Transport
from ats.market.metatrader.mt5 import Mt5Transport
from ats.market.metatrader.worker import MetaTraderWorker
from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

CONSOLE_ROUTERS = (
    accounts_router,
    runtime_router,
    market_router,
    datasets_router,
    strategy_router,
    strategy_os_router,
    managed_router,
    ai_router,
)


def create_console_app(
    reader: ControlPlaneReader | None = None,
    fabric: MarketDataFabric | None = None,
    connector: MetaTraderConnector | None = None,
    account_service: AccountService | None = None,
) -> FastAPI:
    domain = XauUsdDomain.from_environment()
    terminal = connector or MetaTraderConnector(
        domain,
        Mt5Transport() if domain.provider == "MT5" else Mt4Transport(),
        clock_evidence=load_clock_evidence(Path(os.environ["ATS_MT5_CLOCK_EVIDENCE_FILE"]))
        if os.environ.get("ATS_MT5_CLOCK_EVIDENCE_FILE")
        else None,
    )
    market_fabric = fabric or MarketDataFabric(
        source_label=domain.provider,
        authority_class="BROKER_TICK_PROXY",
        stale_after_seconds=domain.stale_after_seconds,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if os.environ.get("LIVE_MONEY", "FALSE").upper() != "FALSE":
            raise RuntimeError("PAPER_ONLY_VIOLATION")
        service_of(Request({"type": "http", "app": application}))
        worker = MetaTraderWorker(terminal, market_fabric)
        application.state.standalone_market_worker = worker

        async def poll_accounts() -> None:
            while True:
                accounts = await asyncio.to_thread(application.state.account_service.registry.list)
                await asyncio.gather(
                    *[
                        asyncio.to_thread(
                            application.state.account_service.poll, account.account_id
                        )
                        for account in accounts
                    ]
                )
                await asyncio.sleep(1)

        account_task = asyncio.create_task(poll_accounts())
        if os.environ.get("ATS_OFFLINE_RESEARCH", "0") != "1":
            worker.start()
        try:
            yield
        finally:
            account_task.cancel()
            try:
                await account_task
            except asyncio.CancelledError:
                pass
            await asyncio.to_thread(application.state.account_service.shutdown)
            await worker.stop()

    app = FastAPI(title="ATS XAUUSD Laboratory", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(os.environ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.account_service = account_service
    app.state.account_admin_lock = RLock()
    app.state.market_fabric = market_fabric
    app.state.metatrader_connector = terminal
    app.state.xauusd_domain = domain
    app.state.trading_runtime_provider = TradingRuntimeProvider()
    app.state.control_plane_reader = reader or LiveControlPlaneReader(
        app.state.trading_runtime_provider
    )
    _register_exception_handlers(app)
    prior_validation_handler = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> Response:
        if not request.url.path.startswith("/v1/accounts"):
            result = prior_validation_handler(request, error)
            if inspect.isawaitable(result):
                result = await result
            return result
        # Input values in Pydantic/FastAPI errors can expose login/password.
        return JSONResponse(status_code=422, content={"detail": "REQUEST_VALIDATION_FAILED"})

    app.include_router(build_a05_router())
    for router in CONSOLE_ROUTERS:
        app.include_router(router)
    return app


app = create_console_app()
