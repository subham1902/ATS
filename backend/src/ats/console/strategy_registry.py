"""FastAPI router for Strategy Performance Registry and Leaderboard."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from .strategy_registry_models import (
    LeaderboardResponse,
    StrategyPerformanceReport,
    StrategyRegistryEntry,
    StrategyRegistryOverview,
)
from .strategy_registry_service import get_registry_service

router = APIRouter(prefix="/v1/strategies/registry", tags=["strategy-registry"])


@router.get("", response_model=StrategyRegistryOverview)
def get_registry() -> StrategyRegistryOverview:
    """Return the full strategy registry with all strategies, ratings, and badges."""
    service = get_registry_service()
    return service.get_registry()


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    timeframe: Annotated[
        str | None,
        Query(description="Filter by timeframe: 5m, 15m, 1h, 4h, daily"),
    ] = None,
    context: Annotated[
        str | None,
        Query(
            description="Filter by execution context: BACKTEST, PAPER_TRADE, SHADOW, "
            "LIVE_FORWARD, REAL_ACCOUNT"
        ),
    ] = None,
    badge: Annotated[
        str | None,
        Query(
            description="Filter by badge: SCALPING, INTRADAY, SWING, POSITIONAL, "
            "LONG_TERM, META_ROUTER, BASELINE"
        ),
    ] = None,
) -> LeaderboardResponse:
    """Return a ranked strategy leaderboard with optional filters."""
    service = get_registry_service()
    return service.get_leaderboard(timeframe=timeframe, context=context, badge=badge)


@router.get("/{strategy_id}", response_model=StrategyRegistryEntry)
def get_strategy(strategy_id: str) -> StrategyRegistryEntry:
    """Return a single strategy's registry entry with all performance data."""
    service = get_registry_service()
    entry = service.get_strategy(strategy_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found in registry",
        )
    return entry


@router.get("/{strategy_id}/report", response_model=StrategyPerformanceReport)
def get_strategy_report(strategy_id: str) -> StrategyPerformanceReport:
    """Return a detailed performance report for a single strategy."""
    service = get_registry_service()
    report = service.get_strategy_report(strategy_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found in registry",
        )
    return report


@router.post("/reload", response_model=StrategyRegistryOverview)
def reload_registry() -> StrategyRegistryOverview:
    """Force-reload strategy data from disk sources."""
    service = get_registry_service()
    service.reload()
    return service.get_registry()


__all__ = ["router"]
