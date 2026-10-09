"""Strategy workspace projection. No promotion or financial authority endpoint."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ats.agents.managed_router import get_managed_store
from ats.agents.research_templates import research_templates
from ats.datasets.ingestion import XauUsdDatasetStore, data_root
from ats.strategies.lineages import bootstrap_store
from ats.strategies.operating_system import StrategyStore
from ats.strategies.research_jobs import ResearchJob, ResearchQueue
from ats.strategies.research_worker import ResearchWorker

router = APIRouter(prefix="/v1/strategy-os", tags=["strategy-os"])


def store_of() -> StrategyStore:
    return bootstrap_store(data_root() / "system" / "strategies" / "registry.sqlite3")


def worker_of() -> ResearchWorker:
    return ResearchWorker(
        ResearchQueue(data_root() / "system" / "strategies" / "jobs.sqlite3", store_of()),
        XauUsdDatasetStore(),
        get_managed_store(),
    )


class SubmitResearch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job: ResearchJob
    idempotency: str = Field(min_length=1, max_length=128)


@router.post("/jobs", status_code=201)
def submit_job(body: SubmitResearch) -> dict[str, str]:
    worker = worker_of()
    try:
        worker.validate(body.job)
        return {"run_id": worker.queue.submit(body.job, body.idempotency)}
    except (ValueError, KeyError, OSError):
        raise HTTPException(409, "RESEARCH_ADMISSION_DENIED") from None


@router.post("/jobs/run-next")
async def run_next() -> dict[str, str | None]:
    return {"run_id": await asyncio.to_thread(worker_of().run_once)}


@router.post("/jobs/{run_id}/cancel")
def cancel_job(run_id: str) -> dict[str, str]:
    try:
        worker_of().queue.cancel(run_id)
        return {"status": "CANCELLED"}
    except ValueError:
        raise HTTPException(409, "RESEARCH_RUN_NOT_CANCELLABLE") from None


@router.get("")
def list_lineages() -> dict[str, Any]:
    return {
        "strategies": [record.model_dump(mode="json") for record in store_of().list()],
        "canonical_symbol": "XAUUSD",
        "promotion": "INDEPENDENT_VALIDATION_REQUIRED",
        "research_worker": "BOUNDED_MANUAL_QUOTE_REPLAY",
    }


@router.get("/templates")
def templates() -> list[dict[str, object]]:
    return research_templates()


@router.get("/jobs")
def jobs() -> dict[str, Any]:
    store = store_of()
    queue = ResearchQueue(data_root() / "system" / "strategies" / "jobs.sqlite3", store)
    return {"jobs": queue.list(), "worker_status": "BOUNDED_MANUAL_QUOTE_REPLAY"}


@router.get("/{strategy_id}")
def get_lineage(strategy_id: str, version: int | None = None) -> dict[str, Any]:
    try:
        return store_of().get(strategy_id, version).model_dump(mode="json")
    except KeyError:
        raise HTTPException(404, "STRATEGY_NOT_FOUND") from None
