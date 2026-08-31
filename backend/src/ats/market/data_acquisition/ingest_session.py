"""Ingest real Upstox session artifacts into canonical Historical Truth datasets.

The raw 1-minute candles acquired from Upstox (underlying indices plus the
real listed ATM +/-2 CE/PE option chain) are normalized into immutable
:class:`MarketObservation` records carrying the explicit four-clock timeline
and a :class:`RawRecordReference` back to the exact raw candle. Datasets are
then validated and persisted through the frozen, tamper-evident storage layer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ats.market.history import (
    ContractMetadataPayload,
    DatasetSourceClass,
    FileHashEntry,
    HistoricalOptionType,
    HistoryValidationPolicy,
    MarketBarPayload,
    ObservationKind,
    ObservationTimes,
    RawRecordReference,
    TransformStep,
    build_historical_dataset,
    build_market_observation,
    load_historical_dataset,
    save_historical_dataset,
)
from ats.market.history.models import MarketObservation

ONE_MINUTE_POLICY = HistoryValidationPolicy(expected_bar_interval_ms=60_000)

SOURCE = "UPSTOX_ANALYTICS_V3"
SOURCE_VERSION = "1.0.0"
TRANSFORM_LINEAGE = (
    TransformStep(step_index=0, transform_id="UPSTOX_V3_NORMALIZER_V1", transform_version="1.0.0"),
    TransformStep(step_index=1, transform_id="HISTORY_CANONICALIZER_V1", transform_version="1.0.0"),
)
UNDERLYING_IDS = {
    "NSE_INDEX|Nifty 50": "NSE_INDEX_NIFTY_50",
    "NSE_INDEX|Nifty Bank": "NSE_INDEX_NIFTY_BANK",
}
BAR_SOURCE_LAG_MS = 60_000
BAR_INGEST_LAG_MS = 61_000
BAR_AVAIL_LAG_MS = 62_000
META_SOURCE_LAG_MS = 1_000
META_INGEST_LAG_MS = 1_500
META_AVAIL_LAG_MS = 2_000

_DATA_ROOT = Path(r"D:\Projects\ATS\ats\data")
SESSION_DATE = "2026-08-25"
SESSION_DIR = _DATA_ROOT / "raw" / "upstox" / "sessions" / SESSION_DATE
OUTPUT_DIR = _DATA_ROOT / "historical"


def _canon_option(trading_symbol: str) -> str:
    return trading_symbol.replace(" ", "_").upper()


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _bar_times(event: datetime) -> ObservationTimes:
    return ObservationTimes(
        event_time=event,
        source_time=event + timedelta(milliseconds=BAR_SOURCE_LAG_MS),
        ingest_time=event + timedelta(milliseconds=BAR_INGEST_LAG_MS),
        available_to_strategy_time=event + timedelta(milliseconds=BAR_AVAIL_LAG_MS),
    )


def _meta_times(event: datetime) -> ObservationTimes:
    return ObservationTimes(
        event_time=event,
        source_time=event + timedelta(milliseconds=META_SOURCE_LAG_MS),
        ingest_time=event + timedelta(milliseconds=META_INGEST_LAG_MS),
        available_to_strategy_time=event + timedelta(milliseconds=META_AVAIL_LAG_MS),
    )


def _candle_sha(row: list[Any]) -> str:
    return hashlib.sha256(json.dumps(row, separators=(",", ":")).encode("utf-8")).hexdigest()


def _build_underlying_observations(
    und_key: str, session_entry: dict[str, Any], file_hashes: list[FileHashEntry]
) -> list[MarketObservation]:
    obs: list[MarketObservation] = []
    und_id = UNDERLYING_IDS[und_key]
    path = SESSION_DIR / session_entry["underlying_file"]
    raw = json.loads(path.read_bytes())["data"]["candles"]
    file_hashes.append(
        FileHashEntry(
            file_name=session_entry["underlying_file"],
            content_sha256=session_entry["underlying_sha256"],
        )
    )
    for index, row in enumerate(raw):
        event = _parse_ts(row[0])
        rec_sha = _candle_sha(row)
        obs.append(
            build_market_observation(
                instrument=und_id,
                times=_bar_times(event),
                payload=MarketBarPayload(
                    payload_kind=ObservationKind.MARKET_BAR,
                    timeframe="1m",
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    volume=Decimal(str(row[5])),
                ),
                provenance=RawRecordReference(
                    source_id=SOURCE,
                    raw_record_sha256=rec_sha,
                    raw_location=f"{session_entry['underlying_file']}:{index}",
                ),
            )
        )
    return obs


def _build_option_observations(
    und_key: str, session_entry: dict[str, Any], file_hashes: list[FileHashEntry]
) -> list[MarketObservation]:
    obs: list[MarketObservation] = []
    und_id = UNDERLYING_IDS[und_key]
    underlying_path = SESSION_DIR / session_entry["underlying_file"]
    first_row = json.loads(underlying_path.read_bytes())["data"]["candles"][0]
    first_event = _parse_ts(first_row[0])
    for opt in session_entry["options"]:
        opt_id = _canon_option(opt["trading_symbol"])
        path = SESSION_DIR / opt["file"]
        raw = json.loads(path.read_bytes())["data"]["candles"]
        file_hashes.append(FileHashEntry(file_name=opt["file"], content_sha256=opt["sha256"]))
        for index, row in enumerate(raw):
            event = _parse_ts(row[0])
            rec_sha = _candle_sha(row)
            obs.append(
                build_market_observation(
                    instrument=opt_id,
                    times=_bar_times(event),
                    payload=MarketBarPayload(
                        payload_kind=ObservationKind.MARKET_BAR,
                        timeframe="1m",
                        open=Decimal(str(row[1])),
                        high=Decimal(str(row[2])),
                        low=Decimal(str(row[3])),
                        close=Decimal(str(row[4])),
                        volume=Decimal(str(row[5])),
                    ),
                    provenance=RawRecordReference(
                        source_id=SOURCE,
                        raw_record_sha256=rec_sha,
                        raw_location=f"{opt['file']}:{index}",
                    ),
                )
            )
        meta_sha = hashlib.sha256(
            json.dumps(
                {"ts": opt["trading_symbol"], "expiry": opt["expiry"]}, separators=(",", ":")
            ).encode()
        ).hexdigest()
        obs.append(
            build_market_observation(
                instrument=opt_id,
                times=_meta_times(first_event),
                payload=ContractMetadataPayload(
                    payload_kind=ObservationKind.CONTRACT_METADATA,
                    contract_master_id=f"UPSTOX_OPTION_CHAIN_{SESSION_DATE}",
                    trading_symbol=opt_id,
                    underlying=und_id,
                    instrument_type="OPTIDX",
                    expiry_date=opt["expiry"],
                    strike=Decimal(str(opt["strike_price"])),
                    option_type=HistoricalOptionType(opt["instrument_type"]),
                    lot_size=int(opt["lot_size"]),
                ),
                provenance=RawRecordReference(
                    source_id=SOURCE,
                    raw_record_sha256=meta_sha,
                    raw_location=f"chain:{opt['trading_symbol']}",
                ),
            )
        )
    return obs


def build_session_datasets() -> dict[str, Any]:
    manifest = json.loads((SESSION_DIR / "session_manifest.json").read_bytes())
    results: dict[str, Any] = {}
    for name, entry in manifest["underlyings"].items():
        und_key = entry["underlying_key"]
        file_hashes: list[FileHashEntry] = []
        observations = _build_underlying_observations(und_key, entry, file_hashes)
        observations += _build_option_observations(und_key, entry, file_hashes)
        file_hashes.sort(key=lambda item: item.file_name)
        dataset = build_historical_dataset(
            observations,
            source=SOURCE,
            source_version=SOURCE_VERSION,
            data_classification=DatasetSourceClass.REAL_SOURCE,
            contract_master_version=f"UPSTOX_OPTION_CHAIN_{SESSION_DATE}",
            file_hashes=file_hashes,
            transform_lineage=TRANSFORM_LINEAGE,
            policy=ONE_MINUTE_POLICY,
        )
        out_dir = OUTPUT_DIR / f"{name.lower()}_options_a2_replay_v1"
        saved = save_historical_dataset(dataset, out_dir, policy=ONE_MINUTE_POLICY)
        reloaded = load_historical_dataset(out_dir)
        results[name] = {
            "output_dir": str(out_dir),
            "dataset_id": str(reloaded.manifest.dataset_id),
            "payload_hash": reloaded.manifest.payload_hash,
            "row_count": reloaded.manifest.row_count,
            "quality": reloaded.manifest.quality_summary.model_dump(),
            "as_of_start": reloaded.manifest.as_of_start.isoformat(),
            "as_of_end": reloaded.manifest.as_of_end.isoformat(),
            "records_sha256": saved.records_sha256,
            "instruments": len(reloaded.manifest.instrument_universe),
        }
    return results


if __name__ == "__main__":
    import pprint

    pprint.pprint(build_session_datasets())
