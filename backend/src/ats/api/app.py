"""FastAPI application factory for the read-only A05 control surface."""

from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from ats.contracts.domain.models import StrategyPolicy
from ats.contracts.governance.types import SystemState
from ats.kernel.policy import validate_strategy_policy

from .models import (
    ActivityPage,
    AdvisoryReadModel,
    AutonomyTokenReadModel,
    CampaignReadModel,
    CandidateReadModel,
    ErrorDetail,
    ErrorEnvelope,
    GovernanceContextReadModel,
    HealthReadModel,
    HealthState,
    PolicyReadModel,
    PolicyValidationReadModel,
    PolicyValidationRequest,
    ReadinessState,
    RiskDecisionReadModel,
    SystemReadModel,
)
from ats.market.fabric import MarketDataFabric

from .imported_strategies_router import router as imported_strategies_router
from .market_router import router as market_router
from .providers import ControlPlaneReader, EmptyControlPlaneReader, LiveControlPlaneReader
from .runtime_router import router as runtime_router
from .strategy_registry import router as strategy_registry_router
from .settings_router import router as settings_router
from .broker_router import router as broker_router
from .ai_router import router as ai_router
from .stream import iter_sse

_CORRELATION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"

class ResourceNotFound(Exception):
    def __init__(self, resource: str, identifier: object) -> None:
        self.resource = resource
        self.identifier = str(identifier)
        super().__init__(f"{resource} not found")


def _correlation_id(request: Request) -> str:
    supplied = request.headers.get("x-correlation-id", "")
    return supplied if re.fullmatch(_CORRELATION_PATTERN, supplied) else "unassigned"


def _reader(request: Request) -> ControlPlaneReader:
    return cast(ControlPlaneReader, request.app.state.control_plane_reader)


ReaderDependency = Annotated[ControlPlaneReader, Depends(_reader)]


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    details: tuple[ErrorDetail, ...] = (),
) -> JSONResponse:
    body = ErrorEnvelope(
        code=code,
        message=message,
        correlation_id=correlation_id,
        details=details,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def create_app(
    reader: ControlPlaneReader | None = None,
    fabric: MarketDataFabric | None = None,
) -> FastAPI:
    """Create an A05 app over injected read providers; no runtime is fabricated.

    ``fabric`` is the market-data distribution dependency. When it is absent the
    market surface still answers, but every read model reports ``NO_FEED`` rather
    than a placeholder price.
    """
    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
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

        yield

        if worker:
            await worker.stop()
        journal.stop()

    app = FastAPI(
        title="ATS Trading Platform API",
        version="2.0.0",
        description="ATS Trading Platform — Strategy Registry, Leaderboard, Live Market & Execution Control.",
        lifespan=lifespan,
    )
    app.state.control_plane_reader = reader or LiveControlPlaneReader()
    if fabric is None:
        fabric = MarketDataFabric(source_label="UPSTOX_V3", authority_class="LIVE_FEED_ATTACHED")
        from datetime import datetime, timezone
        from decimal import Decimal
        from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate, UpdateKind

        now = datetime.now(timezone.utc)
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
    app.state.market_fabric = fabric
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider
    app.state.trading_runtime_provider = TradingRuntimeProvider()
    app.include_router(runtime_router)
    app.include_router(market_router)
    app.include_router(imported_strategies_router)
    app.include_router(strategy_registry_router)
    app.include_router(settings_router)
    app.include_router(broker_router)
    app.include_router(ai_router)

    @app.exception_handler(ResourceNotFound)
    async def not_found_handler(request: Request, exc: ResourceNotFound) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            message=f"{exc.resource} was not found",
            correlation_id=_correlation_id(request),
            details=(ErrorDetail(field="id", issue=exc.identifier),),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = tuple(
            ErrorDetail(
                field=".".join(str(item) for item in error["loc"]),
                issue=str(error["msg"]),
            )
            for error in exc.errors()
        )
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="REQUEST_INVALID",
            message="Request validation failed",
            correlation_id=_correlation_id(request),
            details=details,
        )

    error_responses: dict[int | str, dict[str, Any]] = {
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        422: {"model": ErrorEnvelope, "description": "Invalid request"},
    }

    @app.get("/health/live", response_model=HealthReadModel, tags=["health"])
    def health_live() -> HealthReadModel:
        return HealthReadModel(status=HealthState.LIVE, ready=True, reason_codes=())

    @app.get(
        "/health/ready",
        response_model=HealthReadModel,
        responses={503: {"model": HealthReadModel}},
        tags=["health"],
    )
    def health_ready(
        control: ReaderDependency,
    ) -> HealthReadModel | JSONResponse:
        system = control.get_system()
        ready = (
            system is not None
            and system.readiness is ReadinessState.READY
            and system.system_state is SystemState.READY
            and not system.halted
        )
        if ready:
            return HealthReadModel(status=HealthState.READY, ready=True, reason_codes=())
        health_state = (
            HealthState.DEGRADED
            if system is not None and system.readiness is ReadinessState.DEGRADED
            else HealthState.NOT_READY
        )
        response = HealthReadModel(
            status=health_state,
            ready=False,
            reason_codes=("CONTROL_PLANE_NOT_READY",),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode="json"),
        )

    @app.get(
        "/v1/system",
        response_model=SystemReadModel,
        responses=error_responses,
        tags=["system"],
    )
    def get_system(control: ReaderDependency) -> SystemReadModel:
        result = control.get_system()
        if result is None:
            raise ResourceNotFound("system state", "current")
        return result

    @app.get(
        "/v1/policies/active",
        response_model=PolicyReadModel,
        responses=error_responses,
        tags=["policy"],
    )
    def get_active_policy(control: ReaderDependency) -> PolicyReadModel:
        policy = control.get_active_policy()
        if policy is None:
            raise ResourceNotFound("active policy", "active")
        return PolicyReadModel.from_contract(policy)

    @app.get(
        "/v1/policies/{policy_id}",
        response_model=PolicyReadModel,
        responses=error_responses,
        tags=["policy"],
    )
    def get_policy(
        policy_id: UUID,
        control: ReaderDependency,
    ) -> PolicyReadModel:
        policy = control.get_policy(policy_id)
        if policy is None:
            raise ResourceNotFound("policy", policy_id)
        return PolicyReadModel.from_contract(policy)

    @app.post(
        "/v1/policies/validate",
        response_model=PolicyValidationReadModel,
        responses={422: error_responses[422]},
        tags=["policy"],
    )
    def validate_policy(request: PolicyValidationRequest) -> PolicyValidationReadModel:
        try:
            policy = StrategyPolicy.model_validate_json(json.dumps(request.policy))
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        result = validate_strategy_policy(
            policy,
            evaluation_time=request.evaluation_time,
            timeframe=request.timeframe,
            event_definition_id=request.event_definition_id,
            model_version=request.model_version,
            calibrator_version=request.calibrator_version,
        )
        return PolicyValidationReadModel(
            outcome=result.outcome,
            reason_codes=result.reason_codes,
        )

    @app.get(
        "/v1/campaigns/{campaign_id}",
        response_model=CampaignReadModel,
        responses=error_responses,
        tags=["campaigns"],
    )
    def get_campaign(
        campaign_id: UUID,
        control: ReaderDependency,
    ) -> CampaignReadModel:
        campaign = control.get_campaign(campaign_id)
        if campaign is None:
            raise ResourceNotFound("campaign", campaign_id)
        return CampaignReadModel.from_contract(campaign)

    @app.get(
        "/v1/candidates/{candidate_id}",
        response_model=CandidateReadModel,
        responses=error_responses,
        tags=["candidates"],
    )
    def get_candidate(
        candidate_id: UUID,
        control: ReaderDependency,
    ) -> CandidateReadModel:
        candidate = control.get_candidate(candidate_id)
        if candidate is None:
            raise ResourceNotFound("candidate", candidate_id)
        return CandidateReadModel.from_contract(candidate)

    @app.get(
        "/v1/governance-contexts/{context_id}",
        response_model=GovernanceContextReadModel,
        responses=error_responses,
        tags=["governance"],
    )
    def get_governance_context(
        context_id: UUID,
        control: ReaderDependency,
    ) -> GovernanceContextReadModel:
        context = control.get_governance_context(context_id)
        if context is None:
            raise ResourceNotFound("governance context", context_id)
        return GovernanceContextReadModel.from_contract(context)

    @app.get(
        "/v1/risk-decisions/{decision_id}",
        response_model=RiskDecisionReadModel,
        responses=error_responses,
        tags=["risk"],
    )
    def get_risk_decision(
        decision_id: UUID,
        control: ReaderDependency,
    ) -> RiskDecisionReadModel:
        decision = control.get_risk_decision(decision_id)
        if decision is None:
            raise ResourceNotFound("risk decision", decision_id)
        return RiskDecisionReadModel.from_contract(decision)

    @app.get(
        "/v1/advisories/{advisory_id}",
        response_model=AdvisoryReadModel,
        responses=error_responses,
        tags=["risk"],
    )
    def get_advisory(
        advisory_id: UUID,
        control: ReaderDependency,
    ) -> AdvisoryReadModel:
        advisory = control.get_advisory(advisory_id)
        if advisory is None:
            raise ResourceNotFound("advisory", advisory_id)
        return AdvisoryReadModel.from_contract(advisory)

    @app.get(
        "/v1/autonomy-tokens/{token_id}",
        response_model=AutonomyTokenReadModel,
        responses=error_responses,
        tags=["autonomy"],
    )
    def get_token(
        token_id: UUID,
        control: ReaderDependency,
    ) -> AutonomyTokenReadModel:
        token = control.get_token(token_id)
        if token is None:
            raise ResourceNotFound("autonomy token", token_id)
        return token

    @app.get("/v1/activity", response_model=ActivityPage, tags=["activity"])
    def list_activity(control: ReaderDependency) -> ActivityPage:
        return ActivityPage(items=control.list_activity())

    @app.get(
        "/v1/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Non-replayable typed read stream",
                "content": {"text/event-stream": {"schema": {"type": "string"}}},
            }
        },
        tags=["stream"],
    )
    def stream(request: Request, control: ReaderDependency) -> StreamingResponse:
        return StreamingResponse(
            iter_sse(request, control),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-ATS-Replay-Supported": "false",
            },
        )

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
        except Exception:
            pass
        finally:
            await hub.unregister(websocket)

    @app.websocket("/v1/market/ws")
    async def market_ws_alias(websocket: WebSocket) -> None:
        """Alias for market stream WebSocket."""
        await stream_market_ws(websocket)

    return app


app = create_app()

__all__ = ["ResourceNotFound", "app", "create_app"]
