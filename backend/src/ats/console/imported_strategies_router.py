"""Read-only API endpoints for imported binary strategies and shadow tournament."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from ats.market.strategy_import import (
    ImportedStrategyMetadata,
    ShadowMetrics,
    ShadowTournamentEngine,
    StrategyDecoder,
)

router = APIRouter(prefix="/v1/strategies/imported", tags=["imported-strategies"])

DEFAULT_BIN_DIR = Path(r"D:\Projects\ATS\ATS trade data\strategy bins")


class ImportedStrategiesOverview(BaseModel):
    total_files: int
    admitted_count: int
    quarantined_count: int
    strategies: list[ImportedStrategyMetadata]
    tournament: list[ShadowMetrics]


def engine_of(request: Request) -> ShadowTournamentEngine:
    """Retrieve the tournament engine singleton from app state."""
    engine = getattr(request.app.state, "shadow_tournament_engine", None)
    if engine is None:
        fabric = getattr(request.app.state, "market_fabric", None)
        if fabric is None:
            from ats.market.fabric import MarketDataFabric
            fabric = MarketDataFabric(
                source_label="UPSTOX_V3", authority_class="LIVE_FEED_ATTACHED"
            )
            request.app.state.market_fabric = fabric
        persistence_dir = Path(r"D:\Projects\ATS\evidence\bin_03")
        engine = ShadowTournamentEngine(fabric=fabric, persistence_dir=persistence_dir)
        engine.load_state()
        request.app.state.shadow_tournament_engine = engine
    return engine


@router.get("", response_model=ImportedStrategiesOverview)
def get_imported_strategies(
    request: Request,
    include_native: Annotated[
        bool, Query(description="Include native research candidates like S17")
    ] = False,
) -> ImportedStrategiesOverview:
    """Return all imported strategy candidates and their current shadow tournament status."""
    engine = engine_of(request)
    cached_metadata = getattr(request.app.state, "imported_strategies_metadata", None)
    if cached_metadata is None:
        cached_metadata = StrategyDecoder.scan_directory(DEFAULT_BIN_DIR)
        request.app.state.imported_strategies_metadata = cached_metadata

    quarantined = sum(1 for s in cached_metadata if s.status == "QUARANTINED")
    admitted = len(cached_metadata) - quarantined

    return ImportedStrategiesOverview(
        total_files=len(cached_metadata),
        admitted_count=admitted,
        quarantined_count=quarantined,
        strategies=cached_metadata,
        tournament=engine.get_leaderboard(include_native=include_native),
    )


@router.post("/scan", response_model=ImportedStrategiesOverview)
def scan_imported_strategies(
    request: Request,
    include_native: Annotated[
        bool, Query(description="Include native research candidates like S17")
    ] = False,
) -> ImportedStrategiesOverview:
    """Re-scan the local strategy bins folder safely without code execution."""
    engine = engine_of(request)
    metadata = StrategyDecoder.scan_directory(DEFAULT_BIN_DIR)
    request.app.state.imported_strategies_metadata = metadata

    quarantined = sum(1 for s in metadata if s.status == "QUARANTINED")
    admitted = len(metadata) - quarantined

    try:
        from ats.trading_runtime.paper_tournament import record_system_activity
        record_system_activity(
            event_kind="STRATEGY_BIN_SCAN",
            summary=(
                f"Strategy binary scan executed: {admitted} admitted, {quarantined} "
                f"quarantined across {len(metadata)} total binaries."
            ),
        )
    except Exception:
        pass

    return ImportedStrategiesOverview(
        total_files=len(metadata),
        admitted_count=admitted,
        quarantined_count=quarantined,
        strategies=metadata,
        tournament=engine.get_leaderboard(include_native=include_native),
    )


@router.get("/tournament", response_model=list[ShadowMetrics])
def get_tournament_leaderboard(
    request: Request,
    include_native: Annotated[
        bool, Query(description="Include native research candidates like S17")
    ] = False,
) -> list[ShadowMetrics]:
    """Return the side-by-side tournament leaderboard."""
    engine = engine_of(request)
    return engine.get_leaderboard(include_native=include_native)


__all__ = ["router"]
