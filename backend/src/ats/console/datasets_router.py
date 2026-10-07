"""Imports produce quality evidence, never promotion authority."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ats.datasets.service import get_dataset_registry_service

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])


class ImportDatasetRequest(BaseModel):
    path: str
    source: str
    broker_symbol: str
    source_timezone: str
    canonical_symbol: str = "XAUUSD"
    timeframe: str | None = None
    price_basis: str = "BID_ASK"
    gap_threshold_seconds: int = 300


@router.get("")
def list_datasets() -> dict[str, Any]:
    return {"datasets": get_dataset_registry_service().list_datasets()}


@router.post("/import")
def import_dataset(body: ImportDatasetRequest) -> dict[str, Any]:
    try:
        return get_dataset_registry_service().import_file(
            Path(body.path), **body.model_dump(exclude={"path"})
        )
    except (ValueError, OSError) as error:
        raise HTTPException(422, "DATASET_IMPORT_REJECTED: " + type(error).__name__) from error


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
    try:
        return get_dataset_registry_service().get(dataset_id)
    except (ValueError, OSError) as error:
        raise HTTPException(404, "DATASET_VERSION_NOT_FOUND") from error
