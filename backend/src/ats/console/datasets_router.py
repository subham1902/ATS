"""FastAPI router for dynamic Dataset Configuration, Ingestion, Proving, and Merging."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ats.datasets.service import get_dataset_registry_service

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])


class CreateDatasetRequest(BaseModel):
    id: str = Field(..., description="Unique dataset identifier, e.g. MCX_GOLDM_5M_OCT26")
    name: str = Field(..., description="Human-readable title or label")
    timeframe: str = Field("5m", description="Bar interval: 1s, 5s, 1m, 5m, 15m, 1h, 1d")
    symbol: str = Field("MCX:GOLDM FUT", description="Trading contract or index key")
    source: str = Field("Direct Ingestion", description="Data origin or feed description")
    authority: str = Field("ADMITTED_OPERATOR_FEED", description="Verification authority tier")
    raw_text: str | None = Field(None, description="Raw CSV text content")
    rows: list[dict[str, Any]] | None = Field(None, description="List of OHLCV dictionaries")
    auto_prove: bool = Field(
        True, description="Immediately prove and certify dataset upon creation"
    )


class MergeDatasetsRequest(BaseModel):
    source_dataset_ids: list[str] = Field(
        ..., min_length=2, description="List of dataset IDs to merge"
    )
    new_dataset_id: str = Field(..., description="Target dataset ID for the synthesized dataset")
    new_name: str | None = Field(None, description="Human-readable name for merged dataset")
    merge_strategy: str = Field(
        "CHRONOLOGICAL", description="Merge strategy: CHRONOLOGICAL or OVERLAY"
    )
    deduplicate: bool = Field(True, description="Deduplicate identical timestamps")


@router.get("")
def list_datasets() -> dict[str, Any]:
    """List all registered datasets with metadata, split information, and proving status."""
    service = get_dataset_registry_service()
    datasets = service.list_datasets()
    return {
        "datasets": datasets,
        "total_count": len(datasets),
        "total_bars": sum(d.get("rows", 0) for d in datasets),
    }


@router.get("/{dataset_id}")
def get_dataset_details(
    dataset_id: str,
    sample_limit: int = Query(50, ge=1, le=500, description="Max sample bars to return"),
) -> dict[str, Any]:
    """Retrieve metadata and sample OHLCV rows for a specific dataset."""
    service = get_dataset_registry_service()
    item = service.get_dataset(dataset_id, sample_limit=sample_limit)
    if not item:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return item


@router.post("")
def create_dataset(body: CreateDatasetRequest) -> dict[str, Any]:
    """Add and ingest a new dataset dynamically with optional immediate proving."""
    service = get_dataset_registry_service()
    content = body.raw_text or body.rows
    if not content:
        raise HTTPException(
            status_code=400, detail="Must provide either raw_text (CSV) or rows array."
        )

    try:
        created = service.add_dataset(
            dataset_id=body.id,
            name=body.name,
            timeframe=body.timeframe,
            symbol=body.symbol,
            source=body.source,
            authority=body.authority,
            raw_text_or_rows=content,
            auto_prove=body.auto_prove,
        )
        return {
            "status": "success",
            "message": f"Dataset '{body.id}' successfully registered and proved.",
            "dataset": created,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict[str, Any]:
    """Delete a dataset and its persistent file from disk dynamically."""
    service = get_dataset_registry_service()
    deleted = service.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return {
        "status": "success",
        "message": f"Dataset '{dataset_id}' deleted successfully.",
        "dataset_id": dataset_id,
    }


@router.post("/{dataset_id}/prove")
def prove_dataset_in_system(dataset_id: str) -> dict[str, Any]:
    """Immediately run the full system proving engine on a dataset, validating geometry,
    continuity, and generating a proof certificate.
    """
    service = get_dataset_registry_service()
    try:
        result = service.prove_dataset(dataset_id)
        return {
            "status": "success",
            "message": f"Dataset '{dataset_id}' successfully proved in system.",
            "proving_status": result.get("proving_status"),
            "proof_report": result.get("proof_report"),
            "dataset": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/merge")
def merge_datasets(body: MergeDatasetsRequest) -> dict[str, Any]:
    """Merge two or more datasets dynamically, synthesize a continuous series, and
    immediately prove the result.
    """
    service = get_dataset_registry_service()
    try:
        merged = service.merge_datasets(
            source_dataset_ids=body.source_dataset_ids,
            new_dataset_id=body.new_dataset_id,
            new_name=body.new_name or f"Merged ({body.new_dataset_id})",
            merge_strategy=body.merge_strategy,
            deduplicate=body.deduplicate,
        )
        return {
            "status": "success",
            "message": (
                f"Successfully merged {len(body.source_dataset_ids)} datasets into "
                f"'{body.new_dataset_id}' and proved."
            ),
            "dataset": merged,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{dataset_id}/export")
def export_dataset_csv(dataset_id: str) -> Response:
    """Export and download the raw CSV data for a dataset."""
    service = get_dataset_registry_service()
    csv_path = service.get_raw_csv_path(dataset_id)
    if not csv_path or not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset CSV for '{dataset_id}' not found.")

    with csv_path.open("r", encoding="utf-8") as f:
        content = f.read()

    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_path.name}"},
    )
