"""Read-side paper state and non-financial safety controls."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from ats.console.runtime_models import RuntimeCommandRequest, RuntimeCommandResult
from ats.trading_runtime.modes import TradingMode

router = APIRouter(prefix="/v1/runtime", tags=["paper"])


@router.get("/status")
def get_runtime_status(request: Request) -> dict[str, Any]:
    state = request.app.state.trading_runtime_provider.to_status_dict()
    return {
        **state,
        "execution_context": "PAPER",
        "live_ready": False,
        "live_money": False,
        "execution_destination": "PaperBroker",
        "canonical_symbol": "XAUUSD",
        "authority": "A04_REQUIRED",
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/command", response_model=RuntimeCommandResult)
def post_runtime_command(request: Request, body: RuntimeCommandRequest) -> RuntimeCommandResult:
    provider = request.app.state.trading_runtime_provider
    if body.command == "HALT_SYSTEM":
        provider.halt()
    elif body.command == "PAUSE_NEW_ENTRIES":
        provider.pause()
    elif body.command == "SET_MODE" and body.mode:
        provider.set_mode(TradingMode(body.mode))
    else:
        return RuntimeCommandResult(accepted=False, reason_codes=("A04_EVIDENCE_REQUIRED",))
    return RuntimeCommandResult(accepted=True, reason_codes=("SAFETY_CONTROL_APPLIED",))


@router.get("/paper/session")
def get_paper_session() -> dict[str, Any]:
    return {
        "state": "RESEARCH_ONLY",
        "authority": "A04_REQUIRED",
        "reason_codes": ["XAUUSD_VALIDATION_REQUIRED"],
        "live_money": False,
    }
