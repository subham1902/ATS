"""Small durable projection for operational paper-position continuity.

This projection does not authorize execution.  It restores monitoring state after a
runtime restart; broker fills and governed authority records remain canonical.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from .position_monitor import ManagedExitMode, MonitoredPosition, PositionOrigin


class RuntimeCheckpointStore(Protocol):
    def load(self) -> dict[str, Any] | None: ...
    def save(self, payload: dict[str, Any]) -> None: ...


class MemoryRuntimeCheckpointStore:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def load(self) -> dict[str, Any] | None:
        return None if self.payload is None else json.loads(json.dumps(self.payload))

    def save(self, payload: dict[str, Any]) -> None:
        self.payload = json.loads(json.dumps(payload))


class JsonRuntimeCheckpointStore:
    """Atomic local JSON checkpoint suitable for the PAPER runtime only."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("runtime checkpoint must contain a JSON object")
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)


def serialize_position(position: MonitoredPosition) -> dict[str, Any]:
    payload = asdict(position)
    for key, value in tuple(payload.items()):
        if isinstance(value, Decimal):
            payload[key] = str(value)
        elif isinstance(value, datetime):
            payload[key] = value.isoformat()
        elif isinstance(value, PositionOrigin | ManagedExitMode):
            payload[key] = value.value
    return payload


def deserialize_position(payload: dict[str, Any]) -> MonitoredPosition:
    decimal_fields = {
        "entry_price", "current_mark", "quantity", "realized_pnl", "unrealized_pnl",
        "peak_pnl", "current_stop", "trailing_stop", "capital_at_risk",
        "capital_committed", "risk_budget", "maximum_loss_per_unit",
    }
    values = dict(payload)
    for key in decimal_fields:
        if values.get(key) is not None:
            values[key] = Decimal(str(values[key]))
    if values.get("entry_at") is not None:
        values["entry_at"] = datetime.fromisoformat(values["entry_at"])
    values["origin"] = PositionOrigin(values.get("origin", PositionOrigin.ATS_AUTONOMOUS))
    values["managed_exit_mode"] = ManagedExitMode(
        values.get("managed_exit_mode", ManagedExitMode.ATS_MANAGED_EXIT)
    )
    return MonitoredPosition(**values)


__all__ = [
    "JsonRuntimeCheckpointStore", "MemoryRuntimeCheckpointStore", "RuntimeCheckpointStore",
    "deserialize_position", "serialize_position",
]
