"""DatasetBinding — explicit research dataset linkage."""

from __future__ import annotations

from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import InstrumentId, NonEmptyStr, Sha256, ensure_unique
from ats.contracts.intelligence.types import RegisteredCode


class DatasetBinding(ATSBaseModel):
    """Immutable research dataset binding (research-only, not a durable contract).

    Every experiment must bind these explicitly; no implicit 'latest'.
    """

    dataset_manifest_id: UUID
    dataset_version: NonEmptyStr
    dataset_cutoff: UTCDateTime
    strategy_definition_id: UUID
    strategy_definition_version: int
    formula_refs: tuple[tuple[UUID, int], ...]
    instrument_universe: tuple[InstrumentId, ...]
    timeframe: RegisteredCode
    parameter_set_hash: Sha256
    seed: int
    cost_model_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_binding(self) -> DatasetBinding:
        if not self.instrument_universe:
            raise ValueError("instrument_universe must be non-empty")
        ensure_unique(self.instrument_universe, "instrument_universe")
        if not self.formula_refs:
            raise ValueError("formula_refs must be non-empty")
        ensure_unique(self.formula_refs, "formula_refs")
        return self


__all__ = ["DatasetBinding"]
