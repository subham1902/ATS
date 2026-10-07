"""Immutable XAUUSD imports with explicit provenance and streaming replay."""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ats.market.domain import require_xauusd
from ats.market.observations import MarketObservation, VolumeProvenance

NORMALIZATION_VERSION = "XAUUSD-UTC-V1"
NUMERIC_FIELDS = (
    "bid",
    "ask",
    "last",
    "volume",
    "tick_volume",
    "real_volume",
    "open",
    "high",
    "low",
    "close",
)


def data_root() -> Path:
    return Path(os.environ.get("ATS_DATA_ROOT", "data"))


def content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_rows(path: Path) -> Iterator[Mapping[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or "timestamp" not in reader.fieldnames:
                raise ValueError("TIMESTAMP_COLUMN_REQUIRED")
            yield from reader
    elif path.suffix.lower() == ".parquet":
        try:
            parquet = importlib.import_module("pyarrow.parquet")
        except ImportError as error:
            raise ValueError("PARQUET_REQUIRES_DATASET_EXTRA") from error
        for batch in parquet.ParquetFile(path).iter_batches():
            yield from batch.to_pylist()
    else:
        raise ValueError("SUPPORTED_FORMATS: CSV, PARQUET")


def normalize_row(
    row: Mapping[str, Any],
    *,
    broker_symbol: str,
    source: str,
    source_timezone: str,
    timeframe: str | None,
    dataset_id: str,
    price_basis: str,
) -> MarketObservation:
    raw_time = row.get("timestamp")
    stamp = (
        raw_time
        if isinstance(raw_time, datetime)
        else datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
    )
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ZoneInfo(source_timezone))
        if stamp.utcoffset() != stamp.replace(fold=1).utcoffset():
            raise ValueError("AMBIGUOUS_OR_NONEXISTENT_LOCAL_TIMESTAMP")
    stamp = stamp.astimezone(UTC)
    if (row.get("symbol") or row.get("canonical_symbol")) not in (
        None,
        "",
        "XAUUSD",
        broker_symbol,
    ):
        raise ValueError("SYMBOL_MISMATCH")
    values: dict[str, Any] = {
        key: Decimal(str(row[key])) for key in NUMERIC_FIELDS if row.get(key) not in (None, "")
    }
    kind = VolumeProvenance.UNKNOWN
    if "volume" in values:
        kind = VolumeProvenance.BROKER_VOLUME
    elif "real_volume" in values:
        kind = VolumeProvenance.REAL_VOLUME
    elif "tick_volume" in values:
        kind = VolumeProvenance.TICK_VOLUME
    if any(key in values for key in ("open", "high", "low", "close")) and price_basis not in {
        "BID",
        "ASK",
        "LAST",
        "MID",
    }:
        raise ValueError("BAR_PRICE_BASIS_REQUIRED")
    return MarketObservation(
        broker_symbol=broker_symbol,
        timestamp=stamp,
        received_at=stamp,
        source=source,
        dataset_id=dataset_id,
        provenance="BROKER_BAR" if timeframe else "BROKER_TICK_PROXY",
        timestamp_provenance=f"IMPORT:{source_timezone}:{price_basis}",
        volume_provenance=kind,
        flags=int(row["flags"]) if row.get("flags") not in (None, "") else None,
        timeframe=timeframe,
        **values,
    )


class XauUsdDatasetStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or data_root() / "xauusd" / "datasets"

    def list_datasets(self) -> list[dict[str, Any]]:
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("xauusd-*/manifest.json"))
        ]

    def get(self, dataset_id: str) -> dict[str, Any]:
        if (
            len(dataset_id) != 71
            or not dataset_id.startswith("xauusd-")
            or any(c not in "0123456789abcdef" for c in dataset_id[7:])
        ):
            raise ValueError("INVALID_DATASET_ID")
        return dict(
            json.loads((self.root / dataset_id / "manifest.json").read_text(encoding="utf-8"))
        )

    def import_file(
        self,
        path: Path,
        *,
        source: str,
        broker_symbol: str,
        source_timezone: str,
        canonical_symbol: str = "XAUUSD",
        timeframe: str | None = None,
        price_basis: str = "BID_ASK",
        gap_threshold_seconds: int = 300,
    ) -> dict[str, Any]:
        require_xauusd(canonical_symbol)
        if not source.strip() or source.upper() == "UNKNOWN" or not broker_symbol.strip():
            raise ValueError("SOURCE_PROVENANCE_REQUIRED")
        ZoneInfo(source_timezone)
        if timeframe not in {None, "1m", "5m", "15m", "1h", "1d"} or gap_threshold_seconds <= 0:
            raise ValueError("TIMEFRAME_OR_GAP_THRESHOLD_INVALID")
        raw_hash = content_hash(path)
        identity = {
            "content_hash": raw_hash,
            "source": source,
            "broker_symbol": broker_symbol,
            "canonical_symbol": "XAUUSD",
            "source_timezone": source_timezone,
            "timeframe": timeframe,
            "price_basis": price_basis,
            "normalization_version": NORMALIZATION_VERSION,
            "gap_threshold_seconds": gap_threshold_seconds,
        }
        dataset_id = (
            "xauusd-" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        )
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / dataset_id
        if target.exists():
            return self.get(dataset_id)
        missing: Counter[str] = Counter()
        total = valid = invalid = duplicates = disorder = gaps = 0
        previous: datetime | None = None
        first: datetime | None = None
        last: datetime | None = None
        schemas: set[str] = set()
        spread_min: Decimal | None = None
        spread_max: Decimal | None = None
        with tempfile.TemporaryDirectory(prefix=".import-", dir=self.root) as temporary:
            staging = Path(temporary)
            normalized = staging / "observations.jsonl"
            # Disk-backed deduplication bounds memory for future multi-year tick files.
            with (
                sqlite3.connect(staging / "dedup.sqlite3") as dedup,
                normalized.open("w", encoding="utf-8", newline="\n") as stream,
            ):
                dedup.execute("CREATE TABLE seen (hash TEXT PRIMARY KEY)")
                for row in source_rows(path):
                    total += 1
                    schemas.update(str(k) for k in row)
                    for key in NUMERIC_FIELDS:
                        missing[key] += row.get(key) in (None, "")
                    try:
                        item = normalize_row(
                            row,
                            broker_symbol=broker_symbol,
                            source=source,
                            source_timezone=source_timezone,
                            timeframe=timeframe,
                            dataset_id=dataset_id,
                            price_basis=price_basis,
                        )
                    except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError):
                        invalid += 1
                        continue
                    encoded = item.model_dump_json()
                    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
                    inserted = dedup.execute(
                        "INSERT OR IGNORE INTO seen VALUES (?)", (fingerprint,)
                    )
                    duplicates += inserted.rowcount == 0
                    if previous is not None:
                        disorder += item.timestamp < previous
                        gaps += (item.timestamp - previous).total_seconds() > gap_threshold_seconds
                    previous = item.timestamp
                    first = min(first, item.timestamp) if first else item.timestamp
                    last = max(last, item.timestamp) if last else item.timestamp
                    if item.ask is not None and item.bid is not None:
                        spread = item.ask - item.bid
                        spread_min = min(spread_min, spread) if spread_min is not None else spread
                        spread_max = max(spread_max, spread) if spread_max is not None else spread
                    stream.write(encoded + "\n")
                    valid += 1
            dedup.close()
            (staging / "dedup.sqlite3").unlink()
            findings = {
                "invalid_rows": invalid,
                "duplicates": duplicates,
                "out_of_order": disorder,
                "missing_periods": gaps,
                "gap_threshold_seconds": gap_threshold_seconds,
                "missing_fields": dict(missing),
                "spread_min": str(spread_min) if spread_min is not None else None,
                "spread_max": str(spread_max) if spread_max is not None else None,
            }
            eligible = bool(valid and not invalid and not duplicates and not disorder)
            manifest = {
                **identity,
                "dataset_id": dataset_id,
                "row_count": total,
                "normalized_row_count": valid,
                "schema": sorted(schemas),
                "date_range": [
                    first.isoformat() if first else None,
                    last.isoformat() if last else None,
                ],
                "import_timestamp": datetime.now(UTC).isoformat(),
                "quality": findings,
                "status": "RESEARCH_ONLY" if eligible else "NOT_ELIGIBLE",
                "authority": "RESEARCH_ONLY",
                "normalized_hash": content_hash(normalized),
                "source_format": path.suffix.lower(),
            }
            source_copy = staging / ("source" + path.suffix.lower())
            shutil.copyfile(path, source_copy)
            if content_hash(source_copy) != raw_hash:
                raise ValueError("SOURCE_CHANGED_DURING_IMPORT")
            for filename, document in (("manifest.json", manifest), ("quality.json", findings)):
                (staging / filename).write_text(
                    json.dumps(document, indent=2) + "\n", encoding="utf-8"
                )
            os.replace(staging, target)
        return manifest

    def replay(self, dataset_id: str) -> Iterator[MarketObservation]:
        manifest = self.get(dataset_id)
        path = self.root / dataset_id / "observations.jsonl"
        if manifest["status"] == "NOT_ELIGIBLE":
            raise ValueError("DATASET_QUALITY_NOT_ELIGIBLE")
        if content_hash(path) != manifest["normalized_hash"]:
            raise ValueError("DATASET_CONTENT_CHANGED")
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                yield MarketObservation.model_validate_json(line)
