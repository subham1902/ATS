"""Advisory-only Harness observability + advisory router.

Exposes HEALTHY/DEGRADED/STOPPED, authority ADVISORY_ONLY, local Ollama
provider identity, agent registry, and a bounded advisory round-trip.

No endpoint can place orders, mutate risk, or bypass A04. All outputs are
sanitized — no prompt/content beyond bounded echo, no credential leakage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import Field

from ats.contracts.common import ATSBaseModel

if TYPE_CHECKING:
    from .harness_bridge import HarnessBridge


class HarnessHealthView(ATSBaseModel):
    state: str
    authority: str = "ADVISORY_ONLY"
    version: str = "0.1.1-rc.2"
    checked_at: str
    active_sessions: int
    reason_codes: tuple[str, ...] = ()
    live_money: str = "DISABLED"
    execution_target: str = "PAPER"
    real_orders_placed: int = 0


class LlmProviderView(ATSBaseModel):
    provider: str
    primary_model: str
    fallback_model: str | None = None
    endpoint: str
    health: str
    availability: str | None = None
    last_latency_ms: int | None = None
    last_error_code: str | None = None
    requests: int
    successes: int
    failures: int
    retries: int
    fallback_count: int


class AgentHealthView(ATSBaseModel):
    agent_type: str
    status: str
    last_trigger_at: str | None = None
    last_latency_ms: int | None = None
    model: str | None = None


class HarnessStatusView(ATSBaseModel):
    harness: HarnessHealthView
    llm: LlmProviderView | None = None
    agents: tuple[AgentHealthView, ...] = ()
    advisory_recent: tuple[dict[str, Any], ...] = ()
    safety: dict[str, str] = Field(default_factory=dict)


class AdvisoryRequest(ATSBaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    evidence_summary: str = Field(default="", max_length=6000)
    evidence_refs: list[str] = Field(default_factory=list)
    as_of: str | None = None
    data_cutoff: str | None = None


class AdvisoryResponse(ATSBaseModel):
    provider: str
    model: str | None = None
    latency_ms: int | None = None
    answer: str
    authority: str = "ADVISORY_ONLY"


router = APIRouter(prefix="/v1/harness", tags=["harness"])


def _harness_bridge(request: Request) -> Any:
    return getattr(request.app.state, "harness_bridge", None)


@router.get("/status", response_model=HarnessStatusView)
def get_harness_status(request: Request) -> HarnessStatusView:
    bridge = _harness_bridge(request)
    if bridge is None:
        from ats.contracts.common import SystemClock

        now = SystemClock().now().isoformat()
        return HarnessStatusView(
            harness=HarnessHealthView(
                state="STOPPED",
                checked_at=now,
                active_sessions=0,
                reason_codes=("HARNESS_BRIDGE_NOT_ATTACHED",),
            ),
            llm=None,
            agents=(),
            advisory_recent=(),
            safety={
                "HARNESS_AUTHORITY": "ADVISORY_ONLY",
                "REAL_ORDER_AUTHORITY": "NONE",
                "LIVE_MONEY": "DISABLED",
                "EXECUTION_TARGET": "PAPER",
                "REAL_ORDERS_PLACED": "0",
            },
        )
    return cast("HarnessBridge", bridge).status_view()


@router.post("/advisory", response_model=AdvisoryResponse)
def post_harness_advisory(body: AdvisoryRequest, request: Request) -> AdvisoryResponse:
    bridge = _harness_bridge(request)
    if bridge is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="harness bridge not attached"
        )
    try:
        return cast("HarnessBridge", bridge).advisory(
            prompt=body.prompt,
            evidence_summary=body.evidence_summary,
            evidence_refs=tuple(body.evidence_refs),
            as_of=body.as_of,
            data_cutoff=body.data_cutoff,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"HARNESS_UNAVAILABLE: {type(error).__name__}",
        ) from error


@router.get("/agents", response_model=tuple[AgentHealthView, ...])
def get_harness_agents(request: Request) -> tuple[AgentHealthView, ...]:
    bridge = _harness_bridge(request)
    if bridge is None:
        return ()
    return cast("HarnessBridge", bridge).status_view().agents


__all__ = ["router"]
