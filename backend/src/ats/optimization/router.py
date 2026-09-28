from typing import Any

from fastapi import APIRouter

from ats.optimization.worker import optimization_state

router = APIRouter(prefix="/v1/optimization", tags=["optimization"])

@router.get("/status")
def get_optimization_status() -> dict[str, Any]:
    return optimization_state
