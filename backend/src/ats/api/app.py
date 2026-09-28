"""FastAPI application factory for the read-only A05 control surface.

This module is the **A05 read-only control surface** and nothing else. Its shape is
pinned by the repository constitution
(``ATS_QUANT_RESEARCH_CONSTITUTION_v1.0.md`` §1.2 and Principle VI) and enforced by
``tests/contract/api``:

* the surface is a pure projection of the A04 control plane,
* it exposes exactly one mutating operation -- ``POST /v1/policies/validate``,
  which is a pure evaluation and persists nothing,
* it constructs, authorizes and routes no order, and holds no broker authority,
* it never synthesises a value: an absent field stays ``null``.

The operator workbench (datasets, strategy lab, agents, optimizations, market data)
is a *different* boundary and lives in :mod:`ats.console`. It is served by
``ats.console.app:app`` and is separately constrained by
``tests/contract/api/test_console_boundary.py`` -- it must expose no financial
authority. Keeping the two surfaces in separate modules is what makes the A05
guarantee mechanically checkable rather than aspirational.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Request, status
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
from .providers import ControlPlaneReader, EmptyControlPlaneReader
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


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Resource not found"},
    422: {"model": ErrorEnvelope, "description": "Invalid request"},
}


def build_a05_router() -> APIRouter:
    """Build the read-only A05 projection router.

    Every operation here is a pure read except ``POST /v1/policies/validate``,
    which evaluates a candidate policy against the kernel and persists nothing.
    """
    router = APIRouter()

    @router.get("/health/live", response_model=HealthReadModel, tags=["health"])
    def health_live() -> HealthReadModel:
        return HealthReadModel(status=HealthState.LIVE, ready=True, reason_codes=())

    @router.get(
        "/health/ready",
        response_model=HealthReadModel,
        responses={503: {"model": HealthReadModel}},
        tags=["health"],
    )
    def health_ready(control: ReaderDependency) -> HealthReadModel | JSONResponse:
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

    @router.get(
        "/v1/system",
        response_model=SystemReadModel,
        responses=ERROR_RESPONSES,
        tags=["system"],
    )
    def get_system(control: ReaderDependency) -> SystemReadModel:
        result = control.get_system()
        if result is None:
            raise ResourceNotFound("system state", "current")
        return result

    @router.get(
        "/v1/policies/active",
        response_model=PolicyReadModel | None,
        responses=ERROR_RESPONSES,
        tags=["policy"],
    )
    def get_active_policy(control: ReaderDependency) -> PolicyReadModel | None:
        policy = control.get_active_policy()
        if policy is None:
            return None
        return PolicyReadModel.from_contract(policy)

    @router.get(
        "/v1/policies/{policy_id}",
        response_model=PolicyReadModel,
        responses=ERROR_RESPONSES,
        tags=["policy"],
    )
    def get_policy(policy_id: UUID, control: ReaderDependency) -> PolicyReadModel:
        policy = control.get_policy(policy_id)
        if policy is None:
            raise ResourceNotFound("policy", policy_id)
        return PolicyReadModel.from_contract(policy)

    @router.post(
        "/v1/policies/validate",
        response_model=PolicyValidationReadModel,
        responses={422: ERROR_RESPONSES[422]},
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

    @router.get(
        "/v1/campaigns/{campaign_id}",
        response_model=CampaignReadModel,
        responses=ERROR_RESPONSES,
        tags=["campaigns"],
    )
    def get_campaign(campaign_id: UUID, control: ReaderDependency) -> CampaignReadModel:
        campaign = control.get_campaign(campaign_id)
        if campaign is None:
            raise ResourceNotFound("campaign", campaign_id)
        return CampaignReadModel.from_contract(campaign)

    @router.get(
        "/v1/candidates/{candidate_id}",
        response_model=CandidateReadModel,
        responses=ERROR_RESPONSES,
        tags=["candidates"],
    )
    def get_candidate(candidate_id: UUID, control: ReaderDependency) -> CandidateReadModel:
        candidate = control.get_candidate(candidate_id)
        if candidate is None:
            raise ResourceNotFound("candidate", candidate_id)
        return CandidateReadModel.from_contract(candidate)

    @router.get(
        "/v1/governance-contexts/{context_id}",
        response_model=GovernanceContextReadModel,
        responses=ERROR_RESPONSES,
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

    @router.get(
        "/v1/risk-decisions/{decision_id}",
        response_model=RiskDecisionReadModel,
        responses=ERROR_RESPONSES,
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

    @router.get(
        "/v1/advisories/{advisory_id}",
        response_model=AdvisoryReadModel,
        responses=ERROR_RESPONSES,
        tags=["risk"],
    )
    def get_advisory(advisory_id: UUID, control: ReaderDependency) -> AdvisoryReadModel:
        advisory = control.get_advisory(advisory_id)
        if advisory is None:
            raise ResourceNotFound("advisory", advisory_id)
        return AdvisoryReadModel.from_contract(advisory)

    @router.get(
        "/v1/autonomy-tokens/{token_id}",
        response_model=AutonomyTokenReadModel,
        responses=ERROR_RESPONSES,
        tags=["autonomy"],
    )
    def get_token(token_id: UUID, control: ReaderDependency) -> AutonomyTokenReadModel:
        token = control.get_token(token_id)
        if token is None:
            raise ResourceNotFound("autonomy token", token_id)
        return token

    @router.get("/v1/activity", response_model=ActivityPage, tags=["activity"])
    def list_activity(control: ReaderDependency) -> ActivityPage:
        from ats.trading_runtime.paper_tournament import get_system_activity_items

        base_items = list(control.list_activity())
        runtime_items = get_system_activity_items()
        combined = tuple(
            sorted(base_items + runtime_items, key=lambda x: x.occurred_at, reverse=True)
        )
        return ActivityPage(items=combined)

    @router.get(
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
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-ATS-Replay-Supported": "false",
            },
        )

    return router


def _register_exception_handlers(app: FastAPI) -> None:
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


def create_app(reader: ControlPlaneReader | None = None) -> FastAPI:
    """Create the read-only A05 app over an injected read provider.

    No runtime is fabricated, no worker is started and no market feed is
    synthesised: this app answers from the injected reader alone.
    """
    app = FastAPI(
        title="ATS A05 Read-Only Control Surface",
        version="2.0.0",
        description=(
            "ATS A05 — read-only projection of the A04 control plane. "
            "Exposes no execution, broker or token authority."
        ),
    )
    app.state.control_plane_reader = reader or EmptyControlPlaneReader()
    _register_exception_handlers(app)
    app.include_router(build_a05_router())
    return app


app = create_app()

__all__ = [
    "ERROR_RESPONSES",
    "ReaderDependency",
    "ResourceNotFound",
    "app",
    "build_a05_router",
    "create_app",
]
