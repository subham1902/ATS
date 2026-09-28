"""Dynamic Dataset Registry, Ingestion, Proving, and Merging Engine for ATS."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

# Base storage path for dynamic datasets
DATASETS_DIR = Path("data/datasets")
MANIFEST_PATH = DATASETS_DIR / "datasets_manifest.json"


@dataclass
class DatasetSplits:
    dev: int = 0
    wf: int = 0
    holdout: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"dev": self.dev, "wf": self.wf, "holdout": self.holdout}


@dataclass
class DatasetProofReport:
    proved_at: str = ""
    status: str = "UNPROVEN"  # PROVEN_PRISTINE, PROVEN_QUALIFIED, DEFECTIVE
    total_bars: int = 0
    ohlc_violations: int = 0
    chronological_inversions: int = 0
    duplicate_timestamps: int = 0
    zero_or_negative_prices: int = 0
    negative_volume_bars: int = 0
    gap_count: int = 0
    min_price: float = 0.0
    max_price: float = 0.0
    avg_price: float = 0.0
    price_volatility_pct: float = 0.0
    sha256_hash: str = ""
    certificate_id: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetMetadata:
    id: str
    name: str
    filename: str
    timeframe: str = "5m"
    symbol: str = "MCX:GOLDM FUT"
    source: str = "Direct Ingestion"
    authority: str = "ADMITTED_OPERATOR_FEED"
    range: str = ""
    start_time: str = ""
    end_time: str = ""
    rows: int = 0
    created_at: str = ""
    updated_at: str = ""
    quality: str = "Pending Proving"
    timezone: str = "IST +05:30"
    splits: DatasetSplits = field(default_factory=DatasetSplits)
    holdout_state: str = "SEALED_EVALUATED_ONCE"
    proving_status: str = "UNPROVEN"
    proof_report: dict[str, Any] = field(default_factory=dict)
    sha256_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["splits"] = (
            self.splits.to_dict() if isinstance(self.splits, DatasetSplits) else self.splits
        )
        return d


class DatasetRegistryService:
    """Manages dynamic datasets on disk with immediate proving and merging."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or DATASETS_DIR
        self.manifest_path = self.base_dir / "datasets_manifest.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            with self.manifest_path.open("w", encoding="utf-8") as f:
                json.dump({"datasets": []}, f, indent=2)

    def _load_manifest(self) -> list[dict[str, Any]]:
        try:
            with self.manifest_path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                datasets: list[dict[str, Any]] = data.get("datasets", [])
                return datasets
        except Exception as e:
            LOGGER.error("Failed to load dataset manifest: %s", e)
            return []

    def _save_manifest(self, datasets: list[dict[str, Any]]) -> None:
        try:
            with self.manifest_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {"datasets": datasets, "updated_at": datetime.now(UTC).isoformat()},
                    f,
                    indent=2,
                )
        except Exception as e:
            LOGGER.error("Failed to save dataset manifest: %s", e)

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return all registered datasets."""
        return self._load_manifest()

    def get_dataset(self, dataset_id: str, sample_limit: int = 50) -> dict[str, Any] | None:
        """Get dataset metadata and sample OHLCV rows."""
        datasets = self._load_manifest()
        match = next((d for d in datasets if d["id"] == dataset_id), None)
        if not match:
            return None

        result = dict(match)
        csv_path = self.base_dir / match["filename"]
        samples: list[dict[str, Any]] = []
        if csv_path.exists():
            try:
                with csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    all_rows = list(reader)
                    # First 25 and last 25 if large
                    if len(all_rows) <= sample_limit:
                        samples = all_rows
                    else:
                        samples = all_rows[: sample_limit // 2] + all_rows[-sample_limit // 2 :]
            except Exception as e:
                LOGGER.warning("Could not read sample rows for dataset %s: %s", dataset_id, e)
        result["sample_data"] = samples
        return result

    def get_raw_csv_path(self, dataset_id: str) -> Path | None:
        """Return the absolute path to the dataset CSV file."""
        datasets = self._load_manifest()
        match = next((d for d in datasets if d["id"] == dataset_id), None)
        if not match:
            return None
        p = self.base_dir / match["filename"]
        return p if p.exists() else None

    def add_dataset(
        self,
        dataset_id: str,
        name: str,
        timeframe: str = "5m",
        symbol: str = "MCX:GOLDM FUT",
        source: str = "Direct Ingestion",
        authority: str = "ADMITTED_OPERATOR_FEED",
        raw_text_or_rows: str | list[dict[str, Any]] = "",
        auto_prove: bool = True,
    ) -> dict[str, Any]:
        """Add and ingest a new dataset dynamically."""
        clean_id = dataset_id.strip().upper().replace(" ", "_")
        filename = f"{clean_id.lower()}.csv"
        csv_path = self.base_dir / filename

        rows: list[dict[str, Any]] = []
        if isinstance(raw_text_or_rows, str):
            rows = self._parse_text_to_rows(raw_text_or_rows)
        elif isinstance(raw_text_or_rows, list):
            rows = raw_text_or_rows

        if not rows:
            raise ValueError("No valid OHLC data provided for dataset ingestion.")

        # Write CSV
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["time", "open", "high", "low", "close", "volume"]
            )
            writer.writeheader()
            for r in rows:
                writer.writerow({
                    "time": str(r.get("time", r.get("timestamp", ""))),
                    "open": float(r.get("open", 0.0)),
                    "high": float(r.get("high", 0.0)),
                    "low": float(r.get("low", 0.0)),
                    "close": float(r.get("close", 0.0)),
                    "volume": float(r.get("volume", 0.0)),
                })

        # Calculate splits
        total_rows = len(rows)
        dev = int(total_rows * 0.6)
        wf = int(total_rows * 0.2)
        holdout = total_rows - dev - wf
        splits = DatasetSplits(dev=dev, wf=wf, holdout=holdout)

        start_time = str(rows[0].get("time", rows[0].get("timestamp", "")))
        end_time = str(rows[-1].get("time", rows[-1].get("timestamp", "")))
        date_range = f"{start_time} → {end_time} ({total_rows} bars)"

        # SHA-256 Hash
        hasher = hashlib.sha256()
        with csv_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        sha256_hash = hasher.hexdigest()

        now_iso = datetime.now(UTC).isoformat()
        meta = DatasetMetadata(
            id=clean_id,
            name=name or clean_id,
            filename=filename,
            timeframe=timeframe,
            symbol=symbol,
            source=source,
            authority=authority,
            range=date_range,
            start_time=start_time,
            end_time=end_time,
            rows=total_rows,
            created_at=now_iso,
            updated_at=now_iso,
            quality="Ingested; awaiting proving",
            splits=splits,
            sha256_hash=sha256_hash,
        )

        datasets = self._load_manifest()
        # Remove existing if overwriting
        datasets = [d for d in datasets if d["id"] != clean_id]
        datasets.insert(0, meta.to_dict())
        self._save_manifest(datasets)

        if auto_prove:
            return self.prove_dataset(clean_id)
        return meta.to_dict()

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete dataset file and remove from manifest."""
        datasets = self._load_manifest()
        match = next((d for d in datasets if d["id"] == dataset_id), None)
        if not match:
            return False

        csv_path = self.base_dir / match["filename"]
        if csv_path.exists():
            try:
                csv_path.unlink()
            except Exception as e:
                LOGGER.warning("Could not delete file %s: %s", csv_path, e)

        remaining = [d for d in datasets if d["id"] != dataset_id]
        self._save_manifest(remaining)
        return True

    def prove_dataset(self, dataset_id: str) -> dict[str, Any]:
        """Run comprehensive mathematical, chronological, and statistical proving on a dataset."""
        datasets = self._load_manifest()
        idx = next((i for i, d in enumerate(datasets) if d["id"] == dataset_id), None)
        if idx is None:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        meta = datasets[idx]
        csv_path = self.base_dir / meta["filename"]
        if not csv_path.exists():
            raise FileNotFoundError(f"Dataset file '{meta['filename']}' does not exist on disk.")

        rows: list[dict[str, Any]] = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_bars = len(rows)
        if total_bars == 0:
            raise ValueError(f"Dataset '{dataset_id}' is empty.")

        ohlc_violations = 0
        chronological_inversions = 0
        duplicate_timestamps = 0
        zero_or_negative = 0
        negative_vol = 0
        gaps = 0

        prices: list[float] = []
        seen_timestamps: set[str] = set()
        prev_dt: datetime | None = None
        notes: list[str] = []

        for row in rows:
            t_str = row.get("time") or row.get("timestamp") or ""
            o = float(row.get("open", 0.0))
            h = float(row.get("high", 0.0))
            low = float(row.get("low", 0.0))
            c = float(row.get("close", 0.0))
            v = float(row.get("volume", 0.0))

            prices.append(c)

            # Check OHLC Invariants: Low <= Open,Close <= High, High >= Low
            if h < low or h < o or h < c or low > o or low > c:
                ohlc_violations += 1

            # Check price validity
            if o <= 0 or h <= 0 or low <= 0 or c <= 0:
                zero_or_negative += 1

            # Check volume
            if v < 0:
                negative_vol += 1

            # Check duplicate timestamp
            if t_str in seen_timestamps:
                duplicate_timestamps += 1
            else:
                seen_timestamps.add(t_str)

            # Check chronological order
            cur_dt = self._parse_iso_or_datetime(t_str)
            if cur_dt and prev_dt:
                if cur_dt < prev_dt:
                    chronological_inversions += 1
                elif cur_dt == prev_dt:
                    pass  # already counted in duplicates
                else:
                    # Gap check if step > expected
                    step = (cur_dt - prev_dt).total_seconds()
                    # 5m = 300s, 15m = 900s, 1h = 3600s
                    if step > 86400 * 4:  # gap of more than 4 days
                        gaps += 1
            if cur_dt:
                prev_dt = cur_dt

        # Statistical analysis
        min_p = min(prices) if prices else 0.0
        max_p = max(prices) if prices else 0.0
        avg_p = sum(prices) / len(prices) if prices else 0.0

        variance = sum((p - avg_p) ** 2 for p in prices) / len(prices) if len(prices) > 1 else 0.0
        std_dev = variance ** 0.5
        vol_pct = (std_dev / avg_p * 100.0) if avg_p > 0 else 0.0

        # Verdict
        if ohlc_violations == 0 and chronological_inversions == 0 and zero_or_negative == 0:
            status = "PROVEN_PRISTINE"
            notes.append("100% strict OHLC geometric invariants verified.")
            notes.append("Monotonically ascending chronological timestamp sequence.")
            notes.append("Zero unparseable, null, or negative price anomalies.")
        elif ohlc_violations == 0 and zero_or_negative == 0:
            status = "PROVEN_QUALIFIED"
            notes.append("Valid OHLC pricing with minor calendar or sequence gaps.")
        else:
            status = "DEFECTIVE"
            notes.append(f"Detected {ohlc_violations} OHLC geometry violations.")
            if zero_or_negative > 0:
                notes.append(f"Detected {zero_or_negative} zero or negative prices.")

        # Re-compute content SHA-256
        hasher = hashlib.sha256()
        with csv_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        sha256_hash = hasher.hexdigest()

        cert_id = f"CERT-PROVE-{dataset_id}-{sha256_hash[:8].upper()}"

        report = DatasetProofReport(
            proved_at=datetime.now(UTC).isoformat(),
            status=status,
            total_bars=total_bars,
            ohlc_violations=ohlc_violations,
            chronological_inversions=chronological_inversions,
            duplicate_timestamps=duplicate_timestamps,
            zero_or_negative_prices=zero_or_negative,
            negative_volume_bars=negative_vol,
            gap_count=gaps,
            min_price=round(min_p, 2),
            max_price=round(max_p, 2),
            avg_price=round(avg_p, 2),
            price_volatility_pct=round(vol_pct, 2),
            sha256_hash=sha256_hash,
            certificate_id=cert_id,
            notes=notes,
        )

        quality_str = (
            f"{status}: {ohlc_violations} violations, {duplicate_timestamps} duplicates, "
            f"{total_bars} bars"
        )
        meta["proving_status"] = status
        meta["proof_report"] = report.to_dict()
        meta["quality"] = quality_str
        meta["sha256_hash"] = sha256_hash
        meta["updated_at"] = datetime.now(UTC).isoformat()

        datasets[idx] = meta
        self._save_manifest(datasets)
        return meta

    def merge_datasets(
        self,
        source_dataset_ids: list[str],
        new_dataset_id: str,
        new_name: str,
        merge_strategy: str = "CHRONOLOGICAL",
        deduplicate: bool = True,
    ) -> dict[str, Any]:
        """Merge multiple source datasets into a newly synthesized and proved dataset."""
        if len(source_dataset_ids) < 2:
            raise ValueError("Merging requires at least 2 source datasets.")

        clean_target_id = new_dataset_id.strip().upper().replace(" ", "_")
        datasets = self._load_manifest()
        sources_meta = [d for d in datasets if d["id"] in source_dataset_ids]

        if len(sources_meta) != len(source_dataset_ids):
            missing = set(source_dataset_ids) - {d["id"] for d in sources_meta}
            raise ValueError(f"One or more source datasets not found: {missing}")

        all_rows: list[dict[str, Any]] = []
        timeframe = sources_meta[0]["timeframe"]
        symbol = sources_meta[0].get("symbol", "MCX:GOLDM FUT")

        for s in sources_meta:
            csv_path = self.base_dir / s["filename"]
            if not csv_path.exists():
                raise FileNotFoundError(f"Source file {s['filename']} missing.")
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_rows.extend(list(reader))

        # Sort by timestamp
        def get_ts(r: dict[str, Any]) -> str:
            return str(r.get("time") or r.get("timestamp") or "")

        all_rows.sort(key=get_ts)

        # Deduplicate if requested
        final_rows: list[dict[str, Any]] = []
        seen_times: set[str] = set()

        for r in all_rows:
            t = get_ts(r)
            if deduplicate and t in seen_times:
                continue
            seen_times.add(t)
            final_rows.append(r)

        source_names = ", ".join(s["name"] for s in sources_meta)
        source_desc = f"Synthesized Merge ({len(sources_meta)} datasets: {source_names})"

        # Add synthesized dataset
        created = self.add_dataset(
            dataset_id=clean_target_id,
            name=new_name or f"Merged ({clean_target_id})",
            timeframe=timeframe,
            symbol=symbol,
            source=source_desc,
            authority="SYNTHESIZED_PROVED_MERGE",
            raw_text_or_rows=final_rows,
            auto_prove=True,
        )
        return created

    def _parse_text_to_rows(self, text: str) -> list[dict[str, Any]]:
        """Parse raw CSV or multiline text into list of OHLCV dicts."""
        lines = text.strip().split("\n")
        rows: list[dict[str, Any]] = []
        if not lines:
            return rows

        start_idx = 0
        first_line_lower = lines[0].lower()
        if "time" in first_line_lower or "date" in first_line_lower or "open" in first_line_lower:
            start_idx = 1

        for i in range(start_idx, len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            parts = (
                line.split("\t")
                if "\t" in line
                else (line.split(",") if "," in line else line.split())
            )
            if len(parts) < 5:
                continue
            try:
                t = parts[0].strip()
                o = float(parts[1])
                h = float(parts[2])
                low = float(parts[3])
                c = float(parts[4])
                v = float(parts[5]) if len(parts) > 5 else 1000.0
                rows.append({"time": t, "open": o, "high": h, "low": low, "close": c, "volume": v})
            except (ValueError, IndexError):
                continue
        return rows

    def _parse_iso_or_datetime(self, val: str) -> datetime | None:
        """Parse various timestamp strings to datetime."""
        val = val.strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None


# Global singleton instance
_GLOBAL_REGISTRY: DatasetRegistryService | None = None


def get_dataset_registry_service() -> DatasetRegistryService:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = DatasetRegistryService()
    return _GLOBAL_REGISTRY
