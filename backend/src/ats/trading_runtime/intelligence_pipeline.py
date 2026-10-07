"""Research-only evaluation; clean-room evidence is required for candidates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ats.contracts.domain.models import MarketSnapshot
from ats.market.domain import require_xauusd
from ats.market.features.engine import compute_feature_bundle


@dataclass(frozen=True)
class IntelligencePipelineConfig:
    version: str = "XAUUSD-RESEARCH-V1"


@dataclass(frozen=True)
class PipelineResult:
    is_actionable: bool = False
    direction: str = "NEUTRAL"
    expected_edge_r: float | None = None
    candidate: Any = None
    instrument_candidate: Any = None
    thesis: Any = None
    regime: Any = None
    distribution: Any = None
    reason_codes: tuple[str, ...] = ("XAUUSD_EVIDENCE_REQUIRED",)


class MarketIntelligencePipeline:
    def __init__(self, config: IntelligencePipelineConfig | None = None) -> None:
        self.config = config or IntelligencePipelineConfig()

    def evaluate(
        self, *, snapshots: Sequence[MarketSnapshot], cutoff_sequence: int, **context: Any
    ) -> PipelineResult:
        for snapshot in snapshots:
            require_xauusd(snapshot.instrument_id)
        try:
            compute_feature_bundle(snapshots, cutoff_sequence=cutoff_sequence)
        except (ValueError, TypeError):
            return PipelineResult(reason_codes=("FEATURE_EVIDENCE_UNAVAILABLE",))
        return PipelineResult()
