"""Immutable internal types for approved deterministic replay datasets."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import (
    DataQualityState,
    InstrumentId,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    QualityFlag,
    SessionState,
    Sha256,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum


class ReplayManifest(ATSBaseModel):
    dataset_id: UUID
    dataset_version: NonEmptyStr
    source_description: NonEmptyStr
    instrument: InstrumentId
    exchange: Literal["NSE"]
    segment: Literal["CASH"]
    timeframe: Literal["5m"]
    first_bar: UTCDateTime
    last_bar: UTCDateTime
    bar_count: PositiveInt
    content_sha256: Sha256
    calendar_id: NonEmptyStr
    calendar_version: NonEmptyStr

    @model_validator(mode="after")
    def validate_range(self) -> ReplayManifest:
        if self.last_bar < self.first_bar:
            raise ValueError("last_bar must be >= first_bar")
        return self


class ReplayBar(ATSBaseModel):
    instrument_id: InstrumentId
    exchange: Literal["NSE"]
    segment: Literal["CASH"]
    timeframe: Literal["5m"]
    bar_timestamp: UTCDateTime
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal
    source_sequence: PositiveInt
    quality_state: DataQualityState
    quality_flags: tuple[QualityFlag, ...]
    session_state: SessionState

    @model_validator(mode="after")
    def validate_bar(self) -> ReplayBar:
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low/high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low/high")
        ensure_unique(self.quality_flags, "quality_flags")
        return self


class ReplayFixtureDocument(ATSBaseModel):
    dataset_id: UUID
    dataset_version: NonEmptyStr
    calendar_id: NonEmptyStr
    calendar_version: NonEmptyStr
    bars: tuple[ReplayBar, ...]

    @model_validator(mode="after")
    def validate_bars(self) -> ReplayFixtureDocument:
        if not self.bars:
            raise ValueError("bars must be non-empty")
        timestamps = tuple(item.bar_timestamp for item in self.bars)
        ensure_unique(timestamps, "bar timestamps")
        if tuple(sorted(timestamps)) != timestamps:
            raise ValueError("bars must be strictly timestamp ordered")
        sequences = tuple(item.source_sequence for item in self.bars)
        if sequences != tuple(range(1, len(self.bars) + 1)):
            raise ValueError("source sequence must be contiguous and start at one")
        return self


class ReplayDataset(ATSBaseModel):
    manifest: ReplayManifest
    bars: tuple[ReplayBar, ...]

    @model_validator(mode="after")
    def validate_manifest_binding(self) -> ReplayDataset:
        if not self.bars:
            raise ValueError("bars must be non-empty")
        if len(self.bars) != self.manifest.bar_count:
            raise ValueError("bar_count does not match fixture")
        if self.bars[0].bar_timestamp != self.manifest.first_bar:
            raise ValueError("first_bar does not match fixture")
        if self.bars[-1].bar_timestamp != self.manifest.last_bar:
            raise ValueError("last_bar does not match fixture")
        for bar in self.bars:
            if (
                bar.instrument_id != self.manifest.instrument
                or bar.exchange != self.manifest.exchange
                or bar.segment != self.manifest.segment
                or bar.timeframe != self.manifest.timeframe
            ):
                raise ValueError("bar identity does not match manifest")
        return self


class ReplayConfiguration(ATSBaseModel):
    start_at: UTCDateTime
    received_delay_ms: NonNegativeInt


class ReplayPhase(ATSStringEnum):
    INITIAL = "INITIAL"
    RUNNING = "RUNNING"
    TERMINAL = "TERMINAL"


class ReplayCursor(ATSBaseModel):
    visible_count: NonNegativeInt
    last_sequence: NonNegativeInt
    replay_time: UTCDateTime


class ReplayState(ATSBaseModel):
    phase: ReplayPhase
    cursor: ReplayCursor
    total_bars: PositiveInt


ZERO = Decimal("0")


__all__ = [
    "ReplayBar",
    "ReplayConfiguration",
    "ReplayCursor",
    "ReplayDataset",
    "ReplayFixtureDocument",
    "ReplayManifest",
    "ReplayPhase",
    "ReplayState",
]
