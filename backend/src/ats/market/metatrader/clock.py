"""Explicit short-lived server-wall timestamp evidence for live quotes only.

This is not a historical timezone or DST rule. Default feeds remain SOURCE_UTC.
Evidence must compare terminal GMT to an independent UTC observation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BrokerClockEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    server: str = Field(min_length=1)
    terminal_gmt_epoch: int = Field(gt=0)
    terminal_server_epoch: int = Field(gt=0)
    tick_epoch_ms: int = Field(gt=0)
    independent_utc_epoch: int = Field(gt=0)
    captured_at: datetime
    valid_seconds: int = Field(default=900, ge=1, le=1800)
    probe_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    independent_source: str = Field(min_length=1)

    @model_validator(mode="after")
    def verify_anchors(self) -> BrokerClockEvidence:
        if self.captured_at.tzinfo is None:
            raise ValueError("CLOCK_EVIDENCE_REQUIRES_UTC")
        if (
            abs(self.terminal_gmt_epoch - self.independent_utc_epoch) > 10
            or abs(self.captured_at.timestamp() - self.terminal_gmt_epoch) > 2
            or abs(self.tick_epoch_ms / 1000 - self.terminal_server_epoch) > 5
        ):
            raise ValueError("CLOCK_ANCHORS_DO_NOT_AGREE")
        if abs(self.offset_seconds) > 14 * 3600 or self.offset_seconds % 60:
            raise ValueError("CLOCK_OFFSET_INVALID")
        return self

    @property
    def offset_seconds(self) -> int:
        return self.terminal_server_epoch - self.terminal_gmt_epoch

    @property
    def evidence_hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def normalize(self, raw_epoch_ms: int, server: str | None, now: datetime) -> datetime:
        if server != self.server:
            raise ValueError("CLOCK_SERVER_MISMATCH")
        if not 0 <= (now - self.captured_at).total_seconds() <= self.valid_seconds:
            raise ValueError("CLOCK_EVIDENCE_EXPIRED")
        return datetime.fromtimestamp(raw_epoch_ms / 1000 - self.offset_seconds, UTC)


def load_clock_evidence(path: Path) -> BrokerClockEvidence:
    return BrokerClockEvidence.model_validate_json(path.read_text(encoding="utf-8"))


def make_clock_evidence(
    probe: Path, independent_utc: datetime, independent_source: str
) -> BrokerClockEvidence:
    raw: dict[str, Any] = json.loads(probe.read_text(encoding="utf-8-sig"))
    if not raw["connected"]:
        raise ValueError("CONNECTED_CLOCK_PROBE_REQUIRED")
    return BrokerClockEvidence(
        server=raw["server"],
        terminal_gmt_epoch=raw["gmt"],
        terminal_server_epoch=raw["server_time"],
        tick_epoch_ms=raw["tick_msc"],
        independent_utc_epoch=int(independent_utc.timestamp()),
        captured_at=datetime.fromtimestamp(raw["gmt"], UTC),
        probe_hash=hashlib.sha256(probe.read_bytes()).hexdigest(),
        independent_source=independent_source,
    )
