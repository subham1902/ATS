"""FastAPI application factory for the read-only A05 control surface."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from ats.contracts.domain.models import StrategyPolicy
from ats.contracts.governance.types import SystemState
from ats.intelligence.agent_chat import AgentChatAnswer, EvidenceBackedChatService
from ats.intelligence.agent_governance import RuntimeChangeProposal
from ats.kernel.policy import validate_strategy_policy
from ats.observability.operator_intelligence import OperatorIntelligenceSnapshot
from ats.observability.operator_provider import OperatorIntelligenceProvider

from .chat import AgentChatHttpRequest, build_control_plane_chat
from .forensics_router import router as forensics_router
from .harness_router import router as harness_router
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
from .pipeline_router import router as pipeline_router
from .providers import ControlPlaneReader, EmptyControlPlaneReader
from .runtime_router import router as runtime_router
from .stream import iter_operator_sse, iter_sse

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
    *,
    chat_service: EvidenceBackedChatService | None = None,
    trading_runtime_provider: object | None = None,
    operator_intelligence_provider: OperatorIntelligenceProvider | None = None,
    trading_runtime_engine: object | None = None,
    operator_order_service: object | None = None,
) -> FastAPI:
    """Create an A05 app over an injected read provider; no runtime is fabricated."""
    app = FastAPI(
        title="ATS Typed Control API",
        version="1.0.0",
        description="Read-only A2 paper control surface. SSE replay is not implemented.",
    )
    resolved_reader = reader or EmptyControlPlaneReader()
    app.state.control_plane_reader = resolved_reader
    app.state.trading_runtime_provider = trading_runtime_provider
    app.state.operator_intelligence_provider = (
        operator_intelligence_provider or OperatorIntelligenceProvider()
    )
    app.state.trading_runtime_engine = trading_runtime_engine
    app.state.operator_order_service = operator_order_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=("http://127.0.0.1:3000", "http://localhost:3000"),
        allow_methods=("GET", "POST", "OPTIONS"),
        allow_headers=("Accept", "Content-Type", "X-Correlation-ID"),
    )
    proposal_log: list[RuntimeChangeProposal] = []
    app.state.runtime_change_proposals = proposal_log
    app.state.chat_service = chat_service or build_control_plane_chat(resolved_reader, proposal_log)
    app.include_router(runtime_router)
    app.include_router(harness_router)
    app.include_router(pipeline_router)
    app.include_router(forensics_router)

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
        "/v1/operator-intelligence",
        response_model=OperatorIntelligenceSnapshot,
        tags=["observability"],
    )
    def get_operator_intelligence(request: Request) -> OperatorIntelligenceSnapshot:
        provider = cast(
            OperatorIntelligenceProvider,
            request.app.state.operator_intelligence_provider,
        )
        bridge = getattr(request.app.state, "live_pipeline_bridge", None)
        if bridge is not None:
            provider._source = bridge.build_projection_input()
        runtime_provider = request.app.state.trading_runtime_provider
        runtime_state = runtime_provider.get_state() if runtime_provider is not None else None
        return provider.snapshot(runtime_state)

    @app.get(
        "/v1/operator-intelligence/stream",
        response_class=StreamingResponse,
        tags=["observability"],
    )
    def operator_intelligence_stream(request: Request) -> StreamingResponse:
        provider = cast(
            OperatorIntelligenceProvider,
            request.app.state.operator_intelligence_provider,
        )
        return StreamingResponse(
            iter_operator_sse(request, provider),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-ATS-Replay-Supported": "false"},
        )

    @app.post("/v1/agent-chat", response_model=AgentChatAnswer, tags=["agents"])
    def agent_chat(body: AgentChatHttpRequest, request: Request) -> AgentChatAnswer:
        service = cast(EvidenceBackedChatService, request.app.state.chat_service)
        return service.respond(body.to_domain())

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

    return app


app = create_app()

__all__ = ["ResourceNotFound", "app", "create_app"]
