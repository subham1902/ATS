"""Strict types for 1m source bars, completed 5m bars, and fixture hash evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import (
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    Sha256,
    ensure_unique,
)
from ats.market.derivatives.artifacts import ArtifactSourceClass
from ats.market.derivatives.contract_master.models import ExpiryDate
from ats.market.derivatives.providers import DerivativeFixtureManifest


class OneMinuteDerivativeBar(ATSBaseModel):
    instrument_id: NonEmptyStr
    minute_start: UTCDateTime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    open_interest: NonNegativeDecimal

    @model_validator(mode="after")
    def validate_ohlc(self) -> OneMinuteDerivativeBar:
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low/high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low/high")
        if self.minute_start.second or self.minute_start.microsecond:
            raise ValueError("minute_start must be minute aligned")
        return self


class FiveMinuteDerivativeBar(ATSBaseModel):
    instrument_id: NonEmptyStr
    bar_close: UTCDateTime
    timeframe: Literal["5m"]
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    open_interest: NonNegativeDecimal
    source_minute_count: Literal[5]
    quality: Literal["COMPLETE"]


class IncompleteBucketEvidence(ATSBaseModel):
    instrument_id: NonEmptyStr
    bucket_close: UTCDateTime
    actual_minute_count: NonNegativeInt
    missing_minute_starts: tuple[UTCDateTime, ...]
    disposition: Literal["EXCLUDED_FROM_AUTHORITATIVE_REPLAY"]


class ResampleResult(ATSBaseModel):
    bars: tuple[FiveMinuteDerivativeBar, ...]
    excluded_buckets: tuple[IncompleteBucketEvidence, ...]


class RawArtifactBinding(ATSBaseModel):
    artifact_id: NonEmptyStr
    raw_sha256: Sha256
    source_class: ArtifactSourceClass


class FixtureBuildSpec(ATSBaseModel):
    fixture_name: NonEmptyStr
    market: NonEmptyStr
    underlying: NonEmptyStr
    source: NonEmptyStr
    source_api_or_file: NonEmptyStr
    provider: NonEmptyStr
    retrieved_at: UTCDateTime
    source_version: NonEmptyStr | None
    contract_master_hash: Sha256
    timezone: Literal["Asia/Kolkata"]
    normalizer_version: NonEmptyStr
    data_cutoff: UTCDateTime
    license_classification: NonEmptyStr
    session_date: ExpiryDate
    expiry: ExpiryDate
    selected_contract_ids: tuple[NonEmptyStr, ...]
    raw_artifacts: tuple[RawArtifactBinding, ...]

    @model_validator(mode="after")
    def validate_bindings(self) -> FixtureBuildSpec:
        if not self.selected_contract_ids:
            raise ValueError("fixture must bind selected contracts")
        ensure_unique(self.selected_contract_ids, "selected contract IDs")
        if not self.raw_artifacts:
            raise ValueError("fixture must bind raw artifacts")
        ensure_unique(tuple(item.artifact_id for item in self.raw_artifacts), "raw artifact IDs")
        return self


class DerivativeFixtureBinding(ATSBaseModel):
    session_date: ExpiryDate
    expiry: ExpiryDate
    selected_contract_ids: tuple[NonEmptyStr, ...]
    raw_artifacts: tuple[RawArtifactBinding, ...]


class FixtureBuildResult(ATSBaseModel):
    manifest: DerivativeFixtureManifest
    binding: DerivativeFixtureBinding
    bars: tuple[FiveMinuteDerivativeBar, ...]
    manifest_hash: Sha256


__all__ = [
    "DerivativeFixtureBinding",
    "FiveMinuteDerivativeBar",
    "FixtureBuildResult",
    "FixtureBuildSpec",
    "IncompleteBucketEvidence",
    "OneMinuteDerivativeBar",
    "RawArtifactBinding",
    "ResampleResult",
]
