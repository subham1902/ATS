"""Typed evidence and configuration for long-option selection."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, UTCDateTime
from ats.contracts.domain.types import (
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    Sha256,
)
from ats.contracts.intelligence.types import RegisteredCode
from ats.market.derivatives.contract_master import DerivativeUnderlying, OptionType


class ThetaSemantics(StrEnum):
    PER_CALENDAR_DAY = "PER_CALENDAR_DAY"


class InstrumentSelectionStatus(StrEnum):
    CANDIDATES_AVAILABLE = "CANDIDATES_AVAILABLE"
    NO_ELIGIBLE_INSTRUMENT = "NO_ELIGIBLE_INSTRUMENT"


class InstrumentSelectionConfiguration(ATSBaseModel):
    selector_id: RegisteredCode
    selector_version: NonEmptyStr
    maximum_master_age_ms: PositiveInt
    maximum_chain_age_ms: PositiveInt
    maximum_quote_age_ms: PositiveInt
    maximum_spread_fraction: NonNegativeDecimal
    minimum_top_quantity: PositiveInt
    minimum_volume: NonNegativeInt
    minimum_open_interest: NonNegativeInt
    maximum_premium_per_candidate: PositiveDecimal
    slippage_fraction: NonNegativeDecimal
    transaction_cost_fraction: NonNegativeDecimal
    iv_penalty_factor: NonNegativeDecimal
    degraded_liquidity_penalty_fraction: NonNegativeDecimal
    near_expiry_threshold_hours: PositiveDecimal
    near_expiry_penalty_fraction: NonNegativeDecimal
    bar_duration_minutes: PositiveInt
    theta_semantics: Literal[ThetaSemantics.PER_CALENDAR_DAY]

    @model_validator(mode="after")
    def validate_fractions(self) -> InstrumentSelectionConfiguration:
        for field in (
            "maximum_spread_fraction",
            "slippage_fraction",
            "transaction_cost_fraction",
            "iv_penalty_factor",
            "degraded_liquidity_penalty_fraction",
            "near_expiry_penalty_fraction",
        ):
            if getattr(self, field) > Decimal(1):
                raise ValueError(f"{field} must be <= 1")
        return self


class InstrumentCandidate(ATSBaseModel):
    schema_version: Literal["1.0"]
    instrument_candidate_id: UUID
    instrument_id: RegisteredCode
    trading_symbol: NonEmptyStr
    underlying: DerivativeUnderlying
    option_type: OptionType
    expiry: NonEmptyStr
    strike: PositiveDecimal
    thesis_id: UUID
    thesis_version: PositiveInt
    distribution_id: UUID
    option_chain_id: UUID
    lot_size: PositiveInt
    lot_count: Literal[1]
    quantity: PositiveInt
    entry_ask: PositiveDecimal
    premium_required: PositiveDecimal
    expected_gross_pnl: FiniteDecimal
    estimated_spread_cost: NonNegativeDecimal
    estimated_slippage: NonNegativeDecimal
    estimated_transaction_cost: NonNegativeDecimal
    estimated_theta_cost: NonNegativeDecimal
    estimated_iv_penalty: NonNegativeDecimal
    estimated_liquidity_penalty: NonNegativeDecimal
    estimated_expiry_penalty: NonNegativeDecimal
    expected_net_pnl: FiniteDecimal
    as_of_time: UTCDateTime
    data_cutoff: UTCDateTime
    method_version: NonEmptyStr
    payload_hash: Sha256


class InstrumentRejection(ATSBaseModel):
    instrument_id: RegisteredCode
    reason_codes: tuple[RegisteredCode, ...]


class InstrumentSelectionResult(ATSBaseModel):
    status: InstrumentSelectionStatus
    candidates: tuple[InstrumentCandidate, ...]
    rejections: tuple[InstrumentRejection, ...]
    reason_codes: tuple[RegisteredCode, ...]


__all__ = [
    "InstrumentCandidate",
    "InstrumentRejection",
    "InstrumentSelectionConfiguration",
    "InstrumentSelectionResult",
    "InstrumentSelectionStatus",
    "ThetaSemantics",
]
