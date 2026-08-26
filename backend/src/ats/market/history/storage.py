"""Tamper-evident persistence for canonical historical datasets.

``save_historical_dataset`` writes the manifest and one canonical JSON line
per observation using atomic file replacement, then pins a SHA-256 of the
records file. ``load_historical_dataset`` re-verifies every layer on the way
back in: records-file digest, per-observation payload hashes, full
re-validation, content-derived ``dataset_id`` and manifest ``payload_hash``.
Any mismatch raises before a partially trusted dataset can be returned.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import Sha256

from .builder import build_historical_dataset
from .dataset import HistoricalDataset
from .errors import HistoricalTruthError, HistoricalTruthErrorCode
from .models import DatasetManifest, MarketObservation

MANIFEST_FILE = "manifest.json"
RECORDS_FILE = "observations.jsonl"
DIGEST_FILE = "records.sha256"


class SavedDatasetPaths(ATSBaseModel):
    """Locations and digest produced by one successful dataset save."""

    schema_version: str = "1.0"
    manifest_path: str
    records_path: str
    digest_path: str
    records_sha256: Sha256


def save_historical_dataset(
    dataset: HistoricalDataset,
    directory: Path | str,
) -> SavedDatasetPaths:
    """Atomically persist ``dataset`` and pin the records-file digest."""

    base = Path(directory)
    base.mkdir(parents=True, exist_ok=True)
    manifest_path = base / MANIFEST_FILE
    records_path = base / RECORDS_FILE
    digest_path = base / DIGEST_FILE
    payload = "".join(
        observation.model_dump_json() + "\n" for observation in dataset.observations
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    _atomic_write(manifest_path, dataset.manifest.model_dump_json().encode("utf-8"))
    _atomic_write(records_path, payload)
    _atomic_write(digest_path, f"{digest}\n".encode())
    return SavedDatasetPaths(
        manifest_path=str(manifest_path),
        records_path=str(records_path),
        digest_path=str(digest_path),
        records_sha256=digest,
    )


def load_historical_dataset(directory: Path | str) -> HistoricalDataset:
    """Reload and fully re-verify a persisted dataset; fail closed on any drift."""

    base = Path(directory)
    manifest_payload = _read(base / MANIFEST_FILE)
    records_payload = _read(base / RECORDS_FILE)
    declared_digest = (_read(base / DIGEST_FILE)).decode("utf-8").strip()
    actual_digest = hashlib.sha256(records_payload).hexdigest()
    if actual_digest != declared_digest:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.DATASET_STORAGE_CORRUPT,
            "records file digest does not match pinned records.sha256",
        )
    manifest = _parse_manifest(manifest_payload)
    observations = tuple(
        MarketObservation.model_validate_json(line)
        for line in records_payload.decode("utf-8").splitlines()
        if line.strip()
    )
    if not observations:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.DATASET_STORAGE_CORRUPT,
            "records file contains no observations",
        )
    rebuilt = build_historical_dataset(
        observations,
        source=manifest.source,
        source_version=manifest.source_version,
        data_classification=manifest.data_classification,
        contract_master_version=manifest.contract_master_version,
        file_hashes=manifest.file_hashes,
        transform_lineage=manifest.transform_lineage,
    )
    if (
        rebuilt.manifest.dataset_id != manifest.dataset_id
        or rebuilt.manifest.payload_hash != manifest.payload_hash
    ):
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.DATASET_IDENTITY_MISMATCH,
            "reloaded dataset identity does not reproduce the stored manifest",
        )
    return rebuilt


def verify_observation_integrity(observation: MarketObservation) -> None:
    """Raise when an observation's canonical hash does not cover its content."""

    if compute_payload_hash(observation) != observation.payload_hash:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.PAYLOAD_HASH_MISMATCH,
            f"observation {observation.observation_id} failed integrity check",
        )


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.DATASET_STORAGE_CORRUPT,
            f"cannot read required dataset file {path.name}",
        ) from error


def _parse_manifest(payload: bytes) -> DatasetManifest:
    try:
        return DatasetManifest.model_validate_json(payload)
    except ValueError as error:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.DATASET_STORAGE_CORRUPT,
            "manifest.json is not a valid DatasetManifest",
        ) from error


__all__ = [
    "DIGEST_FILE",
    "MANIFEST_FILE",
    "RECORDS_FILE",
    "SavedDatasetPaths",
    "load_historical_dataset",
    "save_historical_dataset",
    "verify_observation_integrity",
]
