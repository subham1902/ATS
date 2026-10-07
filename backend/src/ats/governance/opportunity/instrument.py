"""Hash-bound XAUUSD economics evidence; never execution authority."""

from typing import Literal
from uuid import UUID

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, NonNegativeDecimal, PositiveDecimal, Sha256
from pydantic import PositiveInt, model_validator


class InstrumentCandidate(ATSBaseModel):
    schema_version: Literal["1.0"]
    instrument_candidate_id: UUID
    instrument_id: Literal["XAUUSD"] = "XAUUSD"
    thesis_id: UUID
    thesis_version: PositiveInt
    distribution_id: UUID
    quantity: PositiveDecimal
    entry_ask: PositiveDecimal
    expected_gross_pnl: FiniteDecimal
    estimated_spread_cost: NonNegativeDecimal
    estimated_slippage: NonNegativeDecimal
    estimated_transaction_cost: NonNegativeDecimal
    expected_net_pnl: FiniteDecimal
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    method_version: NonEmptyStr
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_evidence(self) -> "InstrumentCandidate":
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff exceeds as_of_time")
        costs = (
            self.estimated_spread_cost + self.estimated_slippage + self.estimated_transaction_cost
        )
        if self.expected_net_pnl != self.expected_gross_pnl - costs:
            raise ValueError("net economics must include every declared cost")
        return self
