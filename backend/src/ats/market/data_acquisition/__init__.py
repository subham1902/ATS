"""Read-only Upstox market-data acquisition and Historical Truth ingestion."""

from __future__ import annotations

from .ingest_session import build_session_datasets
from .upstox_client import UpstoxReadOnlyClient

__all__ = ["UpstoxReadOnlyClient", "build_session_datasets"]
