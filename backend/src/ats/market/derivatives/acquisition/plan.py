"""Explicit, data-independent acquisition plan for authorized NIFTY/BANKNIFTY history.

This descriptor names exactly which authenticated calls will be executed once
Upstox F&O authorization arrives. Nothing here performs network I/O or holds a
credential; it exists so the post-approval run is deterministic and auditable.

OI resampling rule (deterministic, matching ``replay_data.resampler``):
``open_interest = open_interest of the LAST source minute in each 5-minute
bucket``. OI is a stock (level) quantity, not a flow; summing it across
minutes would double-count open contracts. Missing minutes exclude the whole
bucket from authoritative replay.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, PositiveInt
from ats.market.derivatives.contract_master import DerivativeUnderlying

OI_RESAMPLE_RULE = "OPEN_INTEREST_CARRIES_LAST_SOURCE_MINUTE"
RESAMPLE_SOURCE_INTERVAL_MINUTES: PositiveInt = 1
RESAMPLE_TARGET_INTERVAL_MINUTES: PositiveInt = 5


class AcquisitionObjective(StrEnum):
    BOD_INSTRUMENTS = "BOD_INSTRUMENTS"
    UNDERLYING_EXPIRED_EXPIRIES = "UNDERLYING_EXPIRED_EXPIRIES"
    EXPIRED_OPTION_CONTRACTS = "EXPIRED_OPTION_CONTRACTS"
    EXPIRED_OPTION_CANDLES_1M = "EXPIRED_OPTION_CANDLES_1M"
    UNDERLYING_CANDLES_1M = "UNDERLYING_CANDLES_1M"
    EXPIRED_FUTURE_CONTRACTS = "EXPIRED_FUTURE_CONTRACTS"


class PlannedAcquisition(ATSBaseModel):
    """One authorized call that will be made after approval."""

    objective: AcquisitionObjective
    endpoint_class: NonEmptyStr
    underlying: DerivativeUnderlying
    requires_authorization: Literal[True] = True
    instrument_key: NonEmptyStr | None
    expiry: NonEmptyStr | None
    interval_minutes: PositiveInt | None
    entitlement_class: NonEmptyStr

    @model_validator(mode="after")
    def validate_shape(self) -> PlannedAcquisition:
        if not self.requires_authorization:
            raise ValueError("every planned acquisition requires explicit authorization")
        needs_key = self.objective in (
            AcquisitionObjective.EXPIRED_OPTION_CONTRACTS,
            AcquisitionObjective.EXPIRED_OPTION_CANDLES_1M,
            AcquisitionObjective.UNDERLYING_CANDLES_1M,
            AcquisitionObjective.UNDERLYING_EXPIRED_EXPIRIES,
            AcquisitionObjective.EXPIRED_FUTURE_CONTRACTS,
        )
        needs_expiry = self.objective in (
            AcquisitionObjective.EXPIRED_OPTION_CONTRACTS,
            AcquisitionObjective.EXPIRED_FUTURE_CONTRACTS,
        )
        needs_interval = self.objective in (
            AcquisitionObjective.EXPIRED_OPTION_CANDLES_1M,
            AcquisitionObjective.UNDERLYING_CANDLES_1M,
        )
        if needs_key and self.instrument_key is None:
            raise ValueError(f"{self.objective.value} requires an instrument key")
        if needs_expiry and self.expiry is None:
            raise ValueError(f"{self.objective.value} requires an expiry")
        if needs_interval and self.interval_minutes is None:
            raise ValueError(f"{self.objective.value} requires an interval")
        return self


class DerivativesAcquisitionPlan(ATSBaseModel):
    """Complete bounded acquisition backlog for one readiness cycle."""

    schema_version: str
    plan_id: NonEmptyStr
    items: tuple[PlannedAcquisition, ...]

    @model_validator(mode="after")
    def validate_items(self) -> DerivativesAcquisitionPlan:
        if not self.items:
            raise ValueError("acquisition plan must contain at least one item")
        identities = [
            (item.objective, item.underlying, item.instrument_key, item.expiry)
            for item in self.items
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("acquisition plan items must be unique")
        return self


def derivatives_readiness_plan() -> DerivativesAcquisitionPlan:
    """The exact NIFTY/BANKNIFTY research-window backlog pending authorization."""

    items: list[PlannedAcquisition] = []
    for underlying in DerivativeUnderlying:
        key_suffix = "NIFTY 50" if underlying is DerivativeUnderlying.NIFTY else "NIFTY BANK"
        underlying_key = f"NSE_INDEX|{key_suffix}"
        items.append(
            PlannedAcquisition(
                objective=AcquisitionObjective.BOD_INSTRUMENTS,
                endpoint_class="BOD_INSTRUMENTS",
                underlying=underlying,
                instrument_key=None,
                expiry=None,
                interval_minutes=None,
                entitlement_class="PUBLIC_EXPORT",
            )
        )
        items.append(
            PlannedAcquisition(
                objective=AcquisitionObjective.UNDERLYING_EXPIRED_EXPIRIES,
                endpoint_class="EXPIRED_EXPIRIES",
                underlying=underlying,
                instrument_key=underlying_key,
                expiry=None,
                interval_minutes=None,
                entitlement_class="AUTHENTICATED_READ",
            )
        )
        items.append(
            PlannedAcquisition(
                objective=AcquisitionObjective.UNDERLYING_CANDLES_1M,
                endpoint_class="UNDERLYING_HISTORY",
                underlying=underlying,
                instrument_key=underlying_key,
                expiry=None,
                interval_minutes=RESAMPLE_SOURCE_INTERVAL_MINUTES,
                entitlement_class="AUTHENTICATED_READ",
            )
        )
    return DerivativesAcquisitionPlan(
        schema_version="1.0",
        plan_id="D08_DERIVATIVES_READINESS_V1",
        items=tuple(items),
    )


__all__ = [
    "AcquisitionObjective",
    "DerivativesAcquisitionPlan",
    "OI_RESAMPLE_RULE",
    "PlannedAcquisition",
    "RESAMPLE_SOURCE_INTERVAL_MINUTES",
    "RESAMPLE_TARGET_INTERVAL_MINUTES",
    "derivatives_readiness_plan",
]
