"""Immutable cached references to asynchronously computed intelligence evidence."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, Probability, UTCDateTime
from ats.contracts.domain.types import DataQualityState, NonEmptyStr, Sha256
from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.contract_master import DerivativeUnderlying


class IntelligenceStaleness(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class MarketIntelligenceSnapshot(ATSBaseModel):
    schema_version: Literal["1.0"]
    underlying: DerivativeUnderlying
    data_cutoff: UTCDateTime
    as_of_time: UTCDateTime
    valid_until: UTCDateTime
    regime_reference: NonEmptyStr | None
    forecast_reference: NonEmptyStr | None
    calibrated_probability: Probability | None
    thesis_reference: NonEmptyStr | None
    quality: DataQualityState
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_temporal_boundary(self) -> MarketIntelligenceSnapshot:
        if self.data_cutoff > self.as_of_time:
            raise ValueError("data_cutoff must be <= as_of_time")
        if self.valid_until <= self.as_of_time:
            raise ValueError("valid_until must be > as_of_time")
        return self


class IntelligenceCacheRead(ATSBaseModel):
    status: IntelligenceStaleness
    snapshot: MarketIntelligenceSnapshot | None


def build_market_intelligence_snapshot(
    *,
    underlying: DerivativeUnderlying,
    data_cutoff: UTCDateTime,
    as_of_time: UTCDateTime,
    valid_until: UTCDateTime,
    regime_reference: str | None,
    forecast_reference: str | None,
    calibrated_probability: Probability | None,
    thesis_reference: str | None,
    quality: DataQualityState,
) -> MarketIntelligenceSnapshot:
    values = {
        "schema_version": "1.0",
        "underlying": underlying,
        "data_cutoff": data_cutoff,
        "as_of_time": as_of_time,
        "valid_until": valid_until,
        "regime_reference": regime_reference,
        "forecast_reference": forecast_reference,
        "calibrated_probability": calibrated_probability,
        "thesis_reference": thesis_reference,
        "quality": quality,
    }
    return MarketIntelligenceSnapshot.model_validate(
        {**values, "payload_hash": canonical_sha256(values)}
    )


__all__ = [
    "IntelligenceCacheRead",
    "IntelligenceStaleness",
    "MarketIntelligenceSnapshot",
    "build_market_intelligence_snapshot",
]
