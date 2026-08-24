"""Immutable provider-neutral source/provenance records; no remote client exists here."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import PositiveInt, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, Sha256
from ats.market.derivatives.contract_master import DerivativeUnderlying


class SourceFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class MarketFeedHealth(ATSBaseModel):
    provider: NonEmptyStr
    stream_id: NonEmptyStr
    exchange_time: UTCDateTime | None
    provider_time: UTCDateTime | None
    received_at: UTCDateTime
    processed_at: UTCDateTime
    freshness: SourceFreshness
    reason_codes: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_times(self) -> MarketFeedHealth:
        if self.processed_at < self.received_at:
            raise ValueError("processed_at must be >= received_at")
        return self


class DerivativeFixtureManifest(ATSBaseModel):
    """Evidence accompanying immutable approved raw and normalized replay artifacts."""

    schema_version: str
    fixture_id: UUID
    market: NonEmptyStr
    underlying: DerivativeUnderlying
    source: NonEmptyStr
    source_api_or_file: NonEmptyStr
    provider: NonEmptyStr
    retrieved_at: UTCDateTime
    source_version: NonEmptyStr | None
    contract_master_hash: Sha256
    interval: NonEmptyStr
    timezone: NonEmptyStr
    start_time: UTCDateTime
    end_time: UTCDateTime
    record_count: PositiveInt
    raw_hash: Sha256
    normalized_hash: Sha256
    normalizer_version: NonEmptyStr
    data_cutoff: UTCDateTime
    license_classification: NonEmptyStr

    @model_validator(mode="after")
    def validate_window(self) -> DerivativeFixtureManifest:
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")
        if self.end_time < self.start_time:
            raise ValueError("end_time must be >= start_time")
        if self.data_cutoff < self.end_time:
            raise ValueError("data_cutoff must be >= end_time")
        return self


__all__ = ["DerivativeFixtureManifest", "MarketFeedHealth", "SourceFreshness"]
