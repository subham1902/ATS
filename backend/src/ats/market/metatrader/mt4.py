"""MT4 read-only file bridge. No unsupported claim of an official Python API."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


class Mt4Transport:
    def __init__(self, snapshot_path: Path | None = None) -> None:
        configured = os.environ.get("ATS_MT4_SNAPSHOT_PATH")
        self.path = snapshot_path or (Path(configured) if configured else None)

    def _snapshot(self) -> dict[str, Any]:
        if self.path is None:
            raise ValueError("MT4_BRIDGE_PATH_NOT_CONFIGURED")
        if self.path.stat().st_size > 64_000:
            raise ValueError("MT4_BRIDGE_PAYLOAD_TOO_LARGE")
        result = json.loads(self.path.read_text(encoding="utf-8-sig"))
        if not isinstance(result, dict) or result.get("schema_version") != "ats-mt4-readonly-v1":
            raise ValueError("MT4_BRIDGE_SCHEMA_INVALID")
        return result

    def initialize(self) -> bool:
        self._snapshot()
        return True

    def symbol_info(self, symbol: str) -> Mapping[str, Any] | None:
        snapshot = self._snapshot()
        result = snapshot.get("metadata")
        if not isinstance(result, dict) or result.get("name") != symbol:
            return None
        return result

    def latest_tick(self, symbol: str) -> Mapping[str, Any] | None:
        snapshot = self._snapshot()
        result = snapshot.get("tick")
        if not isinstance(result, dict) or result.get("symbol") != symbol:
            return None
        return result

    def historical_ticks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        raise ValueError("MT4_TICK_HISTORY_REQUIRES_VERSIONED_DATASET_IMPORT")

    def historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        raise ValueError("MT4_BAR_HISTORY_REQUIRES_VERSIONED_DATASET_IMPORT")

    def shutdown(self) -> None:
        pass
