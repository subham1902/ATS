"""A2-safe runtime command router — no live trading, no direct ledger mutation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from .runtime_models import RuntimeCommandRequest, RuntimeCommandResult, RuntimeStatusReadModel

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


def _runtime_state(request: Request) -> dict[str, object]:
    state: dict[str, object] = getattr(request.app.state, "runtime_command_state", {})
    return state


RuntimeStateDep = Annotated[dict[str, object], Depends(_runtime_state)]


@router.get("/status", response_model=RuntimeStatusReadModel)
def get_runtime_status(request: Request, state: RuntimeStateDep) -> RuntimeStatusReadModel:
    _ = state
    _ = request
    raise RuntimeError("runtime status requires injected provider")


@router.post("/command", response_model=RuntimeCommandResult)
def post_runtime_command(
    body: RuntimeCommandRequest, request: Request, state: RuntimeStateDep
) -> RuntimeCommandResult:
    _ = body
    _ = request
    _ = state
    raise RuntimeError("runtime command requires injected provider")


__all__ = ["router"]
