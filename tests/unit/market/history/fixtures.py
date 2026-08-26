"""TEST_ONLY deterministic synthetic history fixtures.

Every record produced here is fabricated evidence for tests only. It is never
real market data: the source identifier and dataset classification mark it as
``TEST_ONLY_SYNTHETIC``. These builders deliberately exercise normal data, late
arrival, future leakage, revisions, contract-master changes, duplicates, and
stale records.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from ats.contracts.domain.hashing import canonical_sha256
from ats.contracts.domain.types import DataQualityState
from ats.market.history import (
    ContractMetadataPayload,
    DatasetSourceClass,
    FileHashEntry,
    HistoricalEventClass,
    HistoricalOptionType,
    MarketBarPayload,
    MarketEventPayload,
    MarketObservation,
    ObservationTimes,
    OptionChainQuotePayload,
    RawRecordReference,
    TransformStep,
    build_historical_dataset,
    build_market_observation,
)

TEST_ONLY_SOURCE = "ATS_TEST_ONLY_SYNTHETIC"
SOURCE_VERSION = "1.0.0"
MASTER_VERSION_V1 = "NSE_TEST_MASTER_V1"
MASTER_VERSION_V2 = "NSE_TEST_MASTER_V2"

SESSION_START = datetime(2024, 6, 3, 3, 45, tzinfo=UTC)
BAR_INTERVAL = timedelta(minutes=5)
EXPIRY_MONTHLY = "2024-06-27"
EXPIRY_WEEKLY = "2024-06-05"


def bar_event_time(sequence: int) -> datetime:
    return SESSION_START + BAR_INTERVAL * (sequence - 1)


def _synthetic_raw_hash(identity: str) -> str:
    return canonical_sha256(("ATS_TEST_ONLY_SYNTHETIC_RAW", identity))


def make_times(
    event_time: datetime,
    *,
    source_lag_ms: int = 500,
    ingest_lag_ms: int = 1_000,
    availability_lag_ms: int = 2_000,
) -> ObservationTimes:
    return ObservationTimes(
        event_time=event_time,
        source_time=event_time + timedelta(milliseconds=source_lag_ms),
        ingest_time=event_time + timedelta(milliseconds=ingest_lag_ms),
        available_to_strategy_time=event_time + timedelta(milliseconds=availability_lag_ms),
    )


def make_bar_observation(
    sequence: int,
    *,
    instrument: str = "RELIANCE",
    event_time: datetime | None = None,
    source_lag_ms: int = 500,
    ingest_lag_ms: int = 1_000,
    availability_lag_ms: int = 2_000,
    open_price: Decimal = Decimal("2915.00"),
    high_price: Decimal = Decimal("2920.00"),
    low_price: Decimal = Decimal("2912.00"),
    close_price: Decimal = Decimal("2918.50"),
    volume: Decimal = Decimal("12500"),
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[str, ...] = (),
    supersedes: UUID | None = None,
) -> MarketObservation:
    event = event_time if event_time is not None else bar_event_time(sequence)
    identity = (
        f"BAR|{instrument}|{event.isoformat()}|{open_price}|{high_price}"
        f"|{low_price}|{close_price}|{volume}"
    )
    return build_market_observation(
        instrument=instrument,
        times=make_times(
            event,
            source_lag_ms=source_lag_ms,
            ingest_lag_ms=ingest_lag_ms,
            availability_lag_ms=availability_lag_ms,
        ),
        payload=MarketBarPayload(
            payload_kind="MARKET_BAR",
            timeframe="5m",
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        ),
        provenance=RawRecordReference(
            source_id=TEST_ONLY_SOURCE,
            raw_record_sha256=_synthetic_raw_hash(identity),
            raw_location=f"candles/{instrument}/{sequence:06d}",
        ),
        quality_state=quality_state,
        quality_flags=tuple(quality_flags),
        supersedes=supersedes,
    )


def make_option_quote_observation(
    *,
    event_time: datetime,
    underlying: str = "NIFTY",
    trading_symbol: str = "NIFTY24JUN24000CE",
    expiry_date: str = EXPIRY_MONTHLY,
    strike: Decimal = Decimal("24000"),
    option_type: Literal["CE", "PE"] = "CE",
    bid: Decimal | None = Decimal("120.50"),
    ask: Decimal | None = Decimal("122.00"),
    source_lag_ms: int = 200,
    ingest_lag_ms: int = 400,
    availability_lag_ms: int = 800,
) -> MarketObservation:
    identity = f"QUOTE|{trading_symbol}|{event_time.isoformat()}"
    return build_market_observation(
        instrument=underlying,
        times=make_times(
            event_time,
            source_lag_ms=source_lag_ms,
            ingest_lag_ms=ingest_lag_ms,
            availability_lag_ms=availability_lag_ms,
        ),
        payload=OptionChainQuotePayload(
            payload_kind="OPTION_CHAIN_QUOTE",
            underlying=underlying,
            trading_symbol=trading_symbol,
            expiry_date=expiry_date,
            strike=strike,
            option_type=HistoricalOptionType(option_type),
            bid=bid,
            ask=ask,
            volume=Decimal("500"),
        ),
        provenance=RawRecordReference(
            source_id=TEST_ONLY_SOURCE,
            raw_record_sha256=_synthetic_raw_hash(identity),
            raw_location=f"option_chain/{trading_symbol}",
        ),
    )


def make_metadata_observation(
    *,
    master_version: str,
    trading_symbol: str,
    expiry_date: str,
    underlying: str = "NIFTY",
    instrument_type: str = "OPTIDX",
    event_time: datetime | None = None,
    source_lag_ms: int = 3_600_000,
    ingest_lag_ms: int = 3_600_500,
    availability_lag_ms: int = 3_601_000,
) -> MarketObservation:
    effective_event = event_time if event_time is not None else SESSION_START - timedelta(days=7)
    identity = f"META|{master_version}|{trading_symbol}|{expiry_date}"
    return build_market_observation(
        instrument=underlying,
        times=make_times(
            effective_event,
            source_lag_ms=source_lag_ms,
            ingest_lag_ms=ingest_lag_ms,
            availability_lag_ms=availability_lag_ms,
        ),
        payload=ContractMetadataPayload(
            payload_kind="CONTRACT_METADATA",
            contract_master_id=master_version,
            trading_symbol=trading_symbol,
            underlying=underlying,
            instrument_type=instrument_type,
            expiry_date=expiry_date,
            strike=Decimal("24000"),
            option_type=HistoricalOptionType.CALL,
            lot_size=25,
        ),
        provenance=RawRecordReference(
            source_id=TEST_ONLY_SOURCE,
            raw_record_sha256=_synthetic_raw_hash(identity),
            raw_location=f"contract_master/{master_version}/{trading_symbol}",
        ),
    )


def make_event_observation(
    *,
    headline: str,
    event_time: datetime,
    event_class: str = "NEWS",
    source_lag_ms: int = 1_000,
    ingest_lag_ms: int = 2_000,
    availability_lag_ms: int = 4_000,
) -> MarketObservation:
    identity = f"EVENT|{headline}|{event_time.isoformat()}"
    return build_market_observation(
        instrument="RELIANCE",
        times=make_times(
            event_time,
            source_lag_ms=source_lag_ms,
            ingest_lag_ms=ingest_lag_ms,
            availability_lag_ms=availability_lag_ms,
        ),
        payload=MarketEventPayload(
            payload_kind="MARKET_EVENT",
            event_class=HistoricalEventClass(event_class),
            headline=headline,
            summary=f"{TEST_ONLY_SOURCE} synthetic summary for {headline}",
        ),
        provenance=RawRecordReference(
            source_id=TEST_ONLY_SOURCE,
            raw_record_sha256=_synthetic_raw_hash(identity),
            raw_location=f"news/{identity}",
        ),
    )


def test_only_file_hashes() -> tuple[FileHashEntry, ...]:
    return (
        FileHashEntry(file_name="normalized.jsonl", content_sha256="c" * 64),
        FileHashEntry(file_name="raw.jsonl", content_sha256="d" * 64),
    )


def test_only_lineage() -> tuple[TransformStep, ...]:
    return (
        TransformStep(
            step_index=0,
            transform_id="D02_CONTRACT_NORMALIZER_V1",
            transform_version="1.0.0",
        ),
        TransformStep(
            step_index=1, transform_id="HISTORY_CANONICALIZER_V1", transform_version="1.0.0"
        ),
    )


def build_test_dataset(observations: tuple[MarketObservation, ...], **overrides: object):
    options: dict[str, object] = {
        "source": TEST_ONLY_SOURCE,
        "source_version": SOURCE_VERSION,
        "data_classification": DatasetSourceClass.TEST_ONLY_SYNTHETIC,
        "contract_master_version": MASTER_VERSION_V1,
        "file_hashes": test_only_file_hashes(),
        "transform_lineage": test_only_lineage(),
    }
    options.update(overrides)
    return build_historical_dataset(observations, **options)


def scenario_normal_series(count: int = 5) -> tuple[MarketObservation, ...]:
    return tuple(make_bar_observation(sequence=index + 1) for index in range(count))


def scenario_late_arrival() -> tuple[MarketObservation, ...]:
    on_time = tuple(make_bar_observation(sequence=index + 1) for index in range(3))
    late = make_bar_observation(
        sequence=4,
        availability_lag_ms=300_000,
        quality_flags=("LATE_ARRIVAL",),
    )
    return (*on_time, late)


def scenario_future_leak() -> MarketObservation:
    observation = make_bar_observation(sequence=1)
    leaked_times = observation.times.model_copy(
        update={"available_to_strategy_time": observation.times.event_time - timedelta(minutes=1)}
    )
    return observation.model_copy(update={"times": leaked_times})


def scenario_revised_pair() -> tuple[MarketObservation, MarketObservation]:
    original = make_bar_observation(sequence=1, close_price=Decimal("2918.50"))
    revision = make_bar_observation(
        sequence=1,
        close_price=Decimal("2919.00"),
        availability_lag_ms=400_000,
        supersedes=original.observation_id,
    )
    return original, revision


def scenario_contract_master_change() -> tuple[MarketObservation, MarketObservation]:
    v1_row = make_metadata_observation(
        master_version=MASTER_VERSION_V1,
        trading_symbol="NIFTY24JUN24000CE",
        expiry_date=EXPIRY_MONTHLY,
    )
    v2_row = make_metadata_observation(
        master_version=MASTER_VERSION_V2,
        trading_symbol="NIFTY24JUN24100CE",
        expiry_date=EXPIRY_WEEKLY,
        event_time=SESSION_START - timedelta(days=1),
        source_lag_ms=3_600_000,
        ingest_lag_ms=3_600_500,
        availability_lag_ms=3_601_000,
    )
    return v1_row, v2_row


def scenario_duplicate_pair() -> tuple[MarketObservation, MarketObservation]:
    record = make_bar_observation(sequence=1)
    return record, make_bar_observation(sequence=1)


def scenario_stale_bar() -> MarketObservation:
    return make_bar_observation(
        sequence=4,
        availability_lag_ms=1_200_000,
        quality_flags=("LATE_ARRIVAL",),
    )


def scenario_crossed_quote() -> MarketObservation:
    return make_option_quote_observation(
        event_time=SESSION_START,
        bid=Decimal("130.00"),
        ask=Decimal("121.00"),
    )


def scenario_locked_quote() -> MarketObservation:
    return make_option_quote_observation(
        event_time=SESSION_START,
        bid=Decimal("121.00"),
        ask=Decimal("121.00"),
    )


__all__ = [
    "BAR_INTERVAL",
    "EXPIRY_MONTHLY",
    "EXPIRY_WEEKLY",
    "MASTER_VERSION_V1",
    "MASTER_VERSION_V2",
    "SESSION_START",
    "SOURCE_VERSION",
    "TEST_ONLY_SOURCE",
    "bar_event_time",
    "build_test_dataset",
    "make_bar_observation",
    "make_event_observation",
    "make_metadata_observation",
    "make_option_quote_observation",
    "scenario_contract_master_change",
    "scenario_crossed_quote",
    "scenario_duplicate_pair",
    "scenario_future_leak",
    "scenario_late_arrival",
    "scenario_locked_quote",
    "scenario_normal_series",
    "scenario_revised_pair",
    "scenario_stale_bar",
]
