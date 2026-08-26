"""A2-safe runtime command router — no live trading, no direct ledger mutation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ats.trading_runtime.modes import TradingMode

from .runtime_models import RuntimeCommandRequest, RuntimeCommandResult, RuntimeStatusReadModel

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


def _runtime_provider(request: Request) -> object | None:
    return getattr(request.app.state, "trading_runtime_provider", None)


ProviderDep = Annotated[object | None, Depends(_runtime_provider)]


@router.get("/status", response_model=RuntimeStatusReadModel)
def get_runtime_status(request: Request, provider: ProviderDep) -> RuntimeStatusReadModel:
    _ = request
    if provider is None:
        raise RuntimeError("runtime status requires injected provider")
    from ats.api.runtime_models import (
        RuntimeCapitalView,
        RuntimePnLView,
        RuntimeSessionView,
        RuntimeTradingMode,
    )
    from ats.contracts.common import SystemClock
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

    assert isinstance(provider, TradingRuntimeProvider)
    state = provider.get_state()
    now = SystemClock().now()

    return RuntimeStatusReadModel(
        session=RuntimeSessionView(
            phase=state.phase.value,
            can_enter=state.can_enter,
            can_reduce=state.can_reduce,
            must_flatten=state.must_flatten,
            is_halted=state.is_halted,
        ),
        trading_mode=RuntimeTradingMode(
            user_selected=state.user_mode.value,
            effective=state.effective_mode.value,
            deescalation_reason=state.deescalation_reason,
        ),
        capital=RuntimeCapitalView(
            available=state.available,
            reserved=state.reserved,
            inflight=state.inflight,
            used=state.used,
            total=state.total,
        ),
        pnl=RuntimePnLView(
            realized=state.realized,
            unrealized=state.unrealized,
            session_peak=state.peak_equity,
            drawdown_fraction=state.drawdown_fraction,
        ),
        loss_state=state.loss_state,
        open_positions=tuple(state.open_positions),  # type: ignore[arg-type]
        recent_decisions=tuple(state.recent_decisions),
        feed_healthy=state.feed_healthy,
        broker_healthy=state.broker_healthy,
        halted=state.is_halted,
        paused_new_entries=state.paused,
        updated_at=now,
    )


_ALLOWED = frozenset(
    {
        "SET_MODE",
        "PAUSE_NEW_ENTRIES",
        "RESUME_NEW_ENTRIES",
        "EXIT_POSITION",
        "FLATTEN_PORTFOLIO",
        "HALT_SYSTEM",
    }
)


@router.post("/command", response_model=RuntimeCommandResult)
def post_runtime_command(
    body: RuntimeCommandRequest, request: Request, provider: ProviderDep
) -> RuntimeCommandResult:
    _ = request
    if provider is None:
        raise RuntimeError("runtime command requires injected provider")
    if body.command not in _ALLOWED:
        return RuntimeCommandResult(accepted=False, reason_codes=("COMMAND_NOT_ALLOWED",))
    from ats.trading_runtime.runtime_provider import TradingRuntimeProvider

    assert isinstance(provider, TradingRuntimeProvider)
    if body.command == "SET_MODE":
        if body.mode is None:
            return RuntimeCommandResult(accepted=False, reason_codes=("MODE_REQUIRED",))
        try:
            mode = TradingMode(body.mode)
        except ValueError:
            return RuntimeCommandResult(accepted=False, reason_codes=("INVALID_MODE",))
        provider.set_mode(mode)
        state = provider.get_state()
        return RuntimeCommandResult(
            accepted=True, reason_codes=("MODE_UPDATED",), effective_mode=state.effective_mode.value
        )
    if body.command == "PAUSE_NEW_ENTRIES":
        provider.pause()
        return RuntimeCommandResult(accepted=True, reason_codes=("PAUSED",))
    if body.command == "RESUME_NEW_ENTRIES":
        provider.resume()
        return RuntimeCommandResult(accepted=True, reason_codes=("RESUMED",))
    if body.command == "HALT_SYSTEM":
        provider.halt()
        return RuntimeCommandResult(
            accepted=True, reason_codes=("HALTED",), effective_mode="HALTED"
        )
    if body.command in ("EXIT_POSITION", "FLATTEN_PORTFOLIO"):
        engine = getattr(request.app.state, "trading_runtime_engine", None)
        if engine is not None:
            flattens = ["FLATTEN_PORTFOLIO"]
            if body.command in flattens:
                from ats.contracts.common import SystemClock

                engine.request_flatten(
                    SystemClock().now(),
                    reason_code="DASHBOARD_FLATTEN_REQUESTED",
                    source="DASHBOARD",
                )
                return RuntimeCommandResult(accepted=True, reason_codes=("FLATTEN_QUEUED",))
            if body.position_id is not None:
                from ats.contracts.common import SystemClock

                pid = str(body.position_id)
                if pid in getattr(engine.state, "open_positions", {}):
                    engine.request_exit(
                        pid,
                        SystemClock().now(),
                        reason_codes=("DASHBOARD_EXIT_REQUESTED",),
                        source="DASHBOARD",
                    )
                    return RuntimeCommandResult(accepted=True, reason_codes=("EXIT_QUEUED",))
                return RuntimeCommandResult(accepted=False, reason_codes=("POSITION_NOT_FOUND",))
        return RuntimeCommandResult(
            accepted=True, reason_codes=("COMMAND_ACCEPTED_AWAITING_ENGINE",)
        )
    return RuntimeCommandResult(accepted=False, reason_codes=("UNKNOWN_COMMAND",))


__all__ = ["router"]
