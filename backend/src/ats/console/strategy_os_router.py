"""Strategy workspace projection. No promotion or financial authority endpoint."""

from typing import Any

from fastapi import APIRouter, HTTPException

from ats.agents.research_templates import research_templates
from ats.datasets.ingestion import data_root
from ats.strategies.lineages import bootstrap_store
from ats.strategies.operating_system import StrategyStore
from ats.strategies.research_jobs import ResearchQueue

router = APIRouter(prefix="/v1/strategy-os", tags=["strategy-os"])


def store_of() -> StrategyStore:
    return bootstrap_store(data_root() / "system" / "strategies" / "registry.sqlite3")


@router.get("")
def list_lineages() -> dict[str, Any]:
    return {
        "strategies": [record.model_dump(mode="json") for record in store_of().list()],
        "canonical_symbol": "XAUUSD",
        "promotion": "INDEPENDENT_VALIDATION_REQUIRED",
        "research_worker": "NOT_IMPLEMENTED",
    }


@router.get("/templates")
def templates() -> list[dict[str, object]]:
    return research_templates()


@router.get("/jobs")
def jobs() -> dict[str, Any]:
    store = store_of()
    queue = ResearchQueue(data_root() / "system" / "strategies" / "jobs.sqlite3", store)
    return {"jobs": queue.list(), "worker_status": "NOT_IMPLEMENTED"}


@router.get("/{strategy_id}")
def get_lineage(strategy_id: str, version: int | None = None) -> dict[str, Any]:
    try:
        return store_of().get(strategy_id, version).model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "STRATEGY_NOT_FOUND") from None
