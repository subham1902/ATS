"""FastAPI Router for Strategy Lab & Dynamic Store."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ats.strategies.lab_service import get_lab_service

router = APIRouter(prefix="/v1/strategies/lab", tags=["strategy-lab"])


class IntroduceStrategyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Strategy Name")
    archetype: str = Field("Breakout", description="Strategy Archetype / Family")
    description: str = Field("", description="Detailed quantitative strategy description")
    hypothesis: str = Field("", description="Initial quantitative test hypothesis")
    params: dict[str, Any] = Field(default_factory=dict, description="Custom parameters")


class StrategyActionRequest(BaseModel):
    strategy_id: str = Field(..., description="Target Strategy ID")
    action: str = Field("retest", description="Action: 'retest', 'retire', 'force_promote'")


@router.get("")
def get_strategy_lab_state() -> dict[str, Any]:
    """Return the complete state of the Strategy Lab, Best Store, Testing queue,
    Untested incubator, and Ledger.
    """
    service = get_lab_service()
    return service.get_lab_state()


@router.post("/introduce", status_code=status.HTTP_201_CREATED)
def introduce_strategy(req: IntroduceStrategyRequest) -> dict[str, Any]:
    """Introduce a brand new strategy into the Strategy Lab incubator for
    immediate agent testing.
    """
    service = get_lab_service()
    entry = service.introduce_strategy(
        name=req.name,
        archetype=req.archetype,
        description=req.description,
        hypothesis=req.hypothesis,
        params=req.params,
    )
    return {
        "status": "SUCCESS",
        "message": f"Strategy '{req.name}' successfully introduced to incubator",
        "strategy": entry,
    }


@router.post("/action")
def perform_strategy_action(req: StrategyActionRequest) -> dict[str, Any]:
    """Perform action on a strategy (e.g. retest an eliminated strategy)."""
    service = get_lab_service()
    if req.action == "retest":
        ok = service.retest_strategy(req.strategy_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {
            "status": "SUCCESS",
            "message": f"Strategy {req.strategy_id} re-incubated into UNTESTED queue",
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {req.action}")
