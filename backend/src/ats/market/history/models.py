"""Immutable canonical historical market observations and dataset manifests.

Every observation carries the explicit four-clock information timeline
(``event_time <= source_time <= ingest_time <= available_to_strategy_time``)
declared by :data:`AS_OF_INFORMATION_MODEL`. A replayed strategy may observe a
record at simulated decision time ``T`` only when
``observation.times.available_to_strategy_time <= T``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from ats.contracts.common import ATSBaseModel, FiniteDecimal, SchemaVersion, UTCDateTime
from ats.contracts.domain.types import (
    DataQualityState,
    InstrumentId,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    QualityFlag,
    SemVer,
    Sha256,
    ensure_unique,
)
from ats.contracts.enums import ATSStringEnum
from ats.contracts.hashing import canonical_sha256
from ats.contracts.ids import OpaqueId
from ats.contracts.intelligence.types import BoundedText, RegisteredCode
from ats.market.calendar.models import SessionCalendar

from .errors import HistoricalTruthErrorCode

HISTORY_NAMESPACE = UUID("5f1c3a9e-8b24-5d67-a9c0-3e7f2b8d1c4a")
DATASET_NAMESPACE = UUID("9d2b7e4a-6c31-5f88-b2d9-4a1e8c6f3b75")

ExpiryDateText = Annotated[str, StringConstraints(strict=True, pattern=r"^\d{4}-\d{2}-\d{2}$")]
HeadlineText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=256)]
SummaryText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2048)]
NonEmptyText = Annotated[str, StringConstraints(strict=True, min_length=1)]

_MILLISECOND = timedelta(milliseconds=1)


def milliseconds_between(start: UTCDateTime, end: UTCDateTime) -> int:
    """Return exact whole milliseconds from ``start`` until ``end``."""

    return int((end - start) / _MILLISECOND)


class ObservationKind(ATSStringEnum):
    """Closed kinds of canonical historical observations."""

    MARKET_BAR = "MARKET_BAR"
    OPTION_CHAIN_QUOTE = "OPTION_CHAIN_QUOTE"
    CONTRACT_METADATA = "CONTRACT_METADATA"
    MARKET_EVENT = "MARKET_EVENT"


class HistoricalOptionType(ATSStringEnum):
    """Closed option-right vocabulary for historical derivative records."""

    CALL = "CE"
    PUT = "PE"


class HistoricalEventClass(ATSStringEnum):
    """Closed classes of historical market events and news."""

    NEWS = "NEWS"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    DISCLOSURE = "DISCLOSURE"


class DatasetSourceClass(ATSStringEnum):
    """Evidence class of the upstream data behind a dataset manifest."""

    REAL_SOURCE = "REAL_SOURCE"
    RECORDED_PROVIDER_SHAPE = "RECORDED_PROVIDER_SHAPE"
    TEST_ONLY_SYNTHETIC = "TEST_ONLY_SYNTHETIC"


class ObservationTimes(ATSBaseModel):
    """Explicit four-clock availability timeline of one historical record.

    ``event_time`` is the true occurrence instant of the underlying market
    event. ``source_time`` is when the upstream source published the record.
    ``ingest_time`` is when ATS first durably ingested the raw record. The
    strategy-facing boundary is ``available_to_strategy_time``: the earliest
    instant at which every component of this observation was genuinely
    retrievable by a strategy process.
    """

    event_time: UTCDateTime
    source_time: UTCDateTime
    ingest_time: UTCDateTime
    available_to_strategy_time: UTCDateTime

    @model_validator(mode="after")
    def validate_ordering(self) -> ObservationTimes:
        if self.source_time < self.event_time:
            raise ValueError("source_time must be >= event_time")
        if self.ingest_time < self.source_time:
            raise ValueError("ingest_time must be >= source_time")
        if self.available_to_strategy_time < self.ingest_time:
            raise ValueError("available_to_strategy_time must be >= ingest_time")
        return self


class MarketBarPayload(ATSBaseModel):
    """Normalized OHLCV bar payload."""

    payload_kind: Literal[ObservationKind.MARKET_BAR]
    timeframe: RegisteredCode
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal

    @model_validator(mode="after")
    def validate_ohlc(self) -> MarketBarPayload:
        if self.low > self.open or self.low > self.close:
            raise ValueError("open and close must be >= low")
        if self.high < self.open or self.high < self.close:
            raise ValueError("open and close must be <= high")
        return self


class OptionChainQuotePayload(ATSBaseModel):
    """Normalized single-contract option-chain quote payload."""

    payload_kind: Literal[ObservationKind.OPTION_CHAIN_QUOTE]
    underlying: InstrumentId
    trading_symbol: InstrumentId
    expiry_date: ExpiryDateText
    strike: PositiveDecimal
    option_type: HistoricalOptionType
    bid: FiniteDecimal | None = None
    ask: FiniteDecimal | None = None
    last_trade_price: FiniteDecimal | None = None
    volume: NonNegativeDecimal | None = None
    open_interest: NonNegativeDecimal | None = None

    @model_validator(mode="after")
    def validate_quote_pair(self) -> OptionChainQuotePayload:
        if (self.bid is None) != (self.ask is None):
            raise ValueError("bid and ask must be provided together")
        return self


class ContractMetadataPayload(ATSBaseModel):
    """One contract-master row as it was known at its availability instant."""

    payload_kind: Literal[ObservationKind.CONTRACT_METADATA]
    contract_master_id: NonEmptyText
    trading_symbol: InstrumentId
    underlying: InstrumentId
    instrument_type: NonEmptyText
    expiry_date: ExpiryDateText
    strike: PositiveDecimal | None = None
    option_type: HistoricalOptionType | None = None
    lot_size: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_option_fields(self) -> ContractMetadataPayload:
        if (self.strike is None) != (self.option_type is None):
            raise ValueError("strike and option_type must be provided together")
        return self


class MarketEventPayload(ATSBaseModel):
    """Canonical historical news or corporate-action event payload."""

    payload_kind: Literal[ObservationKind.MARKET_EVENT]
    event_class: HistoricalEventClass
    headline: HeadlineText
    summary: SummaryText | None = None


ObservationPayload = Annotated[
    MarketBarPayload | OptionChainQuotePayload | ContractMetadataPayload | MarketEventPayload,
    Field(discriminator="payload_kind"),
]


class RawRecordReference(ATSBaseModel):
    """Preserved raw-to-normalized provenance for one observation."""

    source_id: NonEmptyText
    raw_record_sha256: Sha256
    raw_location: NonEmptyText


class TransformStep(ATSBaseModel):
    """One deterministic transform application in raw-to-canonical lineage."""

    step_index: NonNegativeInt
    transform_id: RegisteredCode
    transform_version: SemVer


class FileHashEntry(ATSBaseModel):
    """Content hash pin for one upstream dataset file."""

    file_name: NonEmptyText
    content_sha256: Sha256


class QualitySummary(ATSBaseModel):
    """Row counts per canonical data-quality classification."""

    good_count: NonNegativeInt
    degraded_count: NonNegativeInt
    unknown_count: NonNegativeInt
    invalid_count: NonNegativeInt

    @property
    def total_count(self) -> int:
        return self.good_count + self.degraded_count + self.unknown_count + self.invalid_count


class DatasetManifest(ATSBaseModel):
    """Immutable manifest binding one canonical historical dataset.

    The manifest pins identity, provenance, coverage, upstream file hashes,
    transform lineage, row count, and quality summary. It never contains
    market values itself; integrity flows from the pinned content hashes.
    """

    schema_version: SchemaVersion = "1.1"
    dataset_id: OpaqueId
    source: NonEmptyText
    source_version: SemVer
    data_classification: DatasetSourceClass
    instrument_universe: tuple[InstrumentId, ...]
    as_of_start: UTCDateTime
    as_of_end: UTCDateTime
    contract_master_version: NonEmptyText
    file_hashes: tuple[FileHashEntry, ...]
    transform_lineage: tuple[TransformStep, ...]
    row_count: PositiveInt
    quality_summary: QualitySummary
    validation_policy_hash: Sha256
    payload_hash: Sha256

    @model_validator(mode="after")
    def validate_binding(self) -> DatasetManifest:
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must be >= as_of_start")
        if tuple(sorted(self.instrument_universe)) != self.instrument_universe:
            raise ValueError("instrument_universe must be sorted and unique")
        names = tuple(item.file_name for item in self.file_hashes)
        if names != tuple(sorted(names)):
            raise ValueError("file_hashes must be sorted by file_name")
        ensure_unique(names, "file_hashes file_name")
        indexes = tuple(step.step_index for step in self.transform_lineage)
        if indexes != tuple(range(len(indexes))):
            raise ValueError("transform_lineage step_index must be contiguous from zero")
        return self


class InstrumentPolicyOverride(ATSBaseModel):
    """Instrument-scoped (optionally timeframe-scoped) policy relaxation.

    Only bar-level availability thresholds may be overridden; every unset
    field falls back to the global :class:`HistoryValidationPolicy` value.
    """

    instrument: InstrumentId
    timeframe: RegisteredCode | None = None
    bar_minimum_availability_delay_ms: NonNegativeInt | None = None
    bar_maximum_source_lag_ms: NonNegativeInt | None = None


class HistoryValidationPolicy(ATSBaseModel):
    """Deterministic thresholds used by the historical validation engine.

    Delays are expressed in whole milliseconds. Minimum availability delays
    guard against unrealistic same-bar visibility; maximum source-lag
    thresholds classify stale records; the expected bar interval drives missing
    interval detection; the contract universe gates derivative records. When a
    ``session_calendar`` is attached, gap detection becomes calendar-aware:
    intervals that span only closed/halted time are not flagged, and per-
    instrument overrides relax bar thresholds for specific instruments.
    """

    bar_minimum_availability_delay_ms: NonNegativeInt = 1_000
    quote_minimum_availability_delay_ms: NonNegativeInt = 0
    metadata_minimum_availability_delay_ms: NonNegativeInt = 0
    event_minimum_availability_delay_ms: NonNegativeInt = 0
    bar_maximum_source_lag_ms: NonNegativeInt = 900_000
    quote_maximum_source_lag_ms: NonNegativeInt = 10_000
    metadata_maximum_source_lag_ms: NonNegativeInt = 604_800_000
    event_maximum_source_lag_ms: NonNegativeInt = 3_600_000
    expected_bar_interval_ms: PositiveInt = 300_000
    contract_universe: tuple[InstrumentId, ...] = ()
    session_calendar: SessionCalendar | None = None
    instrument_overrides: tuple[InstrumentPolicyOverride, ...] = ()

    @model_validator(mode="after")
    def validate_universe(self) -> HistoryValidationPolicy:
        if tuple(sorted(self.contract_universe)) != self.contract_universe:
            raise ValueError("contract_universe must be sorted and unique")
        keys = tuple(
            (override.instrument, override.timeframe) for override in self.instrument_overrides
        )
        if tuple(sorted(keys)) != keys or len(set(keys)) != len(keys):
            raise ValueError(
                "instrument_overrides must be sorted and unique by (instrument, timeframe)"
            )
        return self


DEFAULT_VALIDATION_POLICY = HistoryValidationPolicy()


def validation_policy_hash(policy: HistoryValidationPolicy) -> Sha256:
    """Hash the complete effective policy through ATS canonical JSON primitives.

    JSON-mode dumping makes calendar dates/times explicit strings before the
    canonical hash is computed, while preserving strict model validation and
    deterministic ordering of the policy's validated tuple fields.
    """

    return canonical_sha256(policy.model_dump(mode="json"))


class AsOfInformationModel(ATSBaseModel):
    """Explicit declaration of replay information-admission semantics.

    At replay decision time ``T`` an observation is admissible exactly when
    ``observation.times.available_to_strategy_time <= T``, subject to the
    declared four-clock ordering invariant.
    """

    schema_version: SchemaVersion = "1.0"
    model_id: Literal["AS_OF_INFORMATION_MODEL_V1"]
    availability_field: Literal["times.available_to_strategy_time"]
    admission_rule: Literal["observation.times.available_to_strategy_time <= decision_time"]
    time_order_rule: Literal[
        "event_time <= source_time <= ingest_time <= available_to_strategy_time"
    ]


AS_OF_INFORMATION_MODEL = AsOfInformationModel(
    model_id="AS_OF_INFORMATION_MODEL_V1",
    availability_field="times.available_to_strategy_time",
    admission_rule="observation.times.available_to_strategy_time <= decision_time",
    time_order_rule=("event_time <= source_time <= ingest_time <= available_to_strategy_time"),
)


class MarketObservation(ATSBaseModel):
    """Canonical immutable historical observation with full provenance.

    ``payload_hash`` covers every authoritative field except itself and follows
    the canonical SHA-256 preimage convention. ``supersedes`` links a corrected
    record to the exact earlier record it replaces.
    """

    schema_version: SchemaVersion = "1.0"
    observation_id: OpaqueId
    instrument: InstrumentId
    times: ObservationTimes
    payload: ObservationPayload
    provenance: RawRecordReference
    supersedes: OpaqueId | None = None
    quality_state: DataQualityState
    quality_flags: tuple[QualityFlag, ...]
    payload_hash: Sha256

    @property
    def kind(self) -> ObservationKind:
        return self.payload.payload_kind

    @model_validator(mode="after")
    def validate_flags(self) -> MarketObservation:
        ensure_unique(self.quality_flags, "quality_flags")
        return self


class HistoryFinding(ATSBaseModel):
    """One deterministic validation finding with induced quality state."""

    code: HistoricalTruthErrorCode
    message: BoundedText
    quality_state: DataQualityState
    observation_id: OpaqueId | None = None
    related_observation_id: OpaqueId | None = None


class HistoryValidationReport(ATSBaseModel):
    """Deterministic outcome of validating an observation collection."""

    evaluated_count: PositiveInt
    findings: tuple[HistoryFinding, ...]
    overall_quality_state: DataQualityState

    @property
    def has_invalid(self) -> bool:
        return any(item.quality_state is DataQualityState.INVALID for item in self.findings)


__all__ = [
    "AS_OF_INFORMATION_MODEL",
    "AsOfInformationModel",
    "DATASET_NAMESPACE",
    "DatasetManifest",
    "DatasetSourceClass",
    "FileHashEntry",
    "HISTORY_NAMESPACE",
    "HistoricalEventClass",
    "HistoricalOptionType",
    "HistoryFinding",
    "HistoryValidationPolicy",
    "HistoryValidationReport",
    "InstrumentPolicyOverride",
    "MarketBarPayload",
    "MarketEventPayload",
    "MarketObservation",
    "ObservationKind",
    "ObservationPayload",
    "ObservationTimes",
    "OptionChainQuotePayload",
    "QualitySummary",
    "RawRecordReference",
    "TransformStep",
    "milliseconds_between",
    "validation_policy_hash",
]
