"""Position authority projection seam owned by IBA-R17."""

from __future__ import annotations

from typing import Protocol

from ats.persistence.types import StateSnapshot


class PositionRepository(Protocol):
    def save(self, snapshot: StateSnapshot, *, expected_version: int | None) -> None: ...
    def get(self, position_id: str) -> StateSnapshot | None: ...


__all__ = ["PositionRepository"]
