"""Narrow caller-provided context lookup for position-bound interrupt delivery."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ats.intelligence.advisory import PositionAdvisoryContext


class PositionContextReader(Protocol):
    def get(self, position_id: UUID) -> PositionAdvisoryContext | None: ...


__all__ = ["PositionContextReader"]
