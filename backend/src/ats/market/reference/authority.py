"""Reference truth for point-in-time instrument metadata."""

from datetime import datetime
from typing import Literal

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import InstrumentId, PositiveDecimal, PositiveInt


class ReferenceResolution(ATSBaseModel):
    status: Literal["RESOLVED", "REFERENCE_UNKNOWN"]
    instrument: InstrumentId
    lot_size: PositiveInt | None = None
    tick_size: PositiveDecimal | None = None
    contract_multiplier: PositiveDecimal | None = None

class InstrumentReferenceAuthority:
    """Authority for point-in-time instrument/lot/tick sizing."""
    
    def resolve(self, instrument: InstrumentId, as_of: datetime) -> ReferenceResolution:
        # Hard-coded reference truth lookup or placeholder for Phase 2 validation
        if instrument.startswith("NSE_INDEX_"):
            return ReferenceResolution(
                status="RESOLVED",
                instrument=instrument,
                lot_size=1,
                tick_size=PositiveDecimal("0.05"),
                contract_multiplier=PositiveDecimal("1.0"),
            )
        
        # If not known, MUST return REFERENCE_UNKNOWN as per rules
        return ReferenceResolution(
            status="REFERENCE_UNKNOWN",
            instrument=instrument,
        )
