"""XAUUSD research definitions are distinct from performance authority."""

from typing import Any

from fastapi import APIRouter, HTTPException

from ats.strategies.catalog import strategy_catalog

router = APIRouter(prefix="/v1/strategies/registry", tags=["strategies"])


@router.get("")
def get_registry() -> dict[str, Any]:
    return {"strategies": strategy_catalog(), "canonical_symbol": "XAUUSD"}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str) -> dict[str, Any]:
    found = next((item for item in strategy_catalog() if item["strategy_id"] == strategy_id), None)
    if found is None:
        raise HTTPException(404, "STRATEGY_NOT_FOUND")
    return found
