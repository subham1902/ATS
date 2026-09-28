"""FastAPI Router for the ATS AI Service & Live Coach."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from ats.ai.live_coach import CoachAlert, ManualPosition, SessionContext
from ats.ai.service import AIQueryRequest, AIQueryResponse, ATSAIService
from ats.ai.tools import ToolDefinition

router = APIRouter(prefix="/v1/ai", tags=["ai"])

# Singleton service instance
_ai_service = ATSAIService()


@router.post("/query", response_model=AIQueryResponse)
async def query_ai(request: AIQueryRequest) -> AIQueryResponse:
    """Submit a query to the ATS AI Service (read-only advisory & calculations)."""
    return await _ai_service.process_query(request)


@router.get("/tools", response_model=list[ToolDefinition])
async def list_tools() -> list[ToolDefinition]:
    """List all strictly read-only tools registered in the ATS AI Service."""
    return _ai_service.tool_registry.get_definitions()


@router.get("/session", response_model=SessionContext)
async def get_session_context() -> SessionContext:
    """Get the active Live Coach trading session context and positions."""
    return _ai_service.live_coach.context


@router.post("/alerts/simulate", response_model=list[CoachAlert])
async def simulate_event(
    instrument: str = "MCX_FO|569003",
    price: Decimal = Decimal("75420.00"),
    spread: Decimal = Decimal("4.00"),
) -> list[CoachAlert]:
    """Deterministically simulate a tick or event to trigger Live Coach monitoring alerts."""
    return _ai_service.live_coach.evaluate_tick(instrument=instrument, price=price, spread=spread)


@router.post("/positions/declare", response_model=ManualPosition)
async def declare_manual_position(position: ManualPosition) -> ManualPosition:
    """Declare a manual or paper position to be monitored by the Live Coach."""
    _ai_service.live_coach.context.positions.append(position)
    return position
