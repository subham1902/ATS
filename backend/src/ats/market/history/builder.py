"""Deterministic construction of canonical observations, manifests, datasets.

All builders are pure: identity is derived with UUIDv5 over canonical content,
hashes follow the canonical SHA-256 preimage convention, and dataset assembly
fails closed on any ``INVALID`` validation finding.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid5

from ats.contracts.domain.hashing import compute_payload_hash, payload_preimage
from ats.contracts.domain.types import DataQualityState, QualityFlag
from ats.contracts.hashing import canonical_sha256
from ats.contracts.ids import OpaqueId

from .dataset import HistoricalDataset
from .errors import HistoricalTruthError
from .models import (
    DATASET_NAMESPACE,
    DEFAULT_VALIDATION_POLICY,
    HISTORY_NAMESPACE,
    DatasetManifest,
    DatasetSourceClass,
    FileHashEntry,
    HistoryValidationPolicy,
    MarketObservation,
    ObservationPayload,
    ObservationTimes,
    QualitySummary,
    RawRecordReference,
    TransformStep,
    validation_policy_hash,
)
from .validation import (
    compute_effective_states,
    validate_market_history,
)


def build_market_observation(
    *,
    instrument: str,
    times: ObservationTimes,
    payload: ObservationPayload,
    provenance: RawRecordReference,
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[QualityFlag, ...] = (),
    supersedes: OpaqueId | None = None,
) -> MarketObservation:
    """Build one canonical observation with deterministic identity and hash.

    The observation id is ``uuid5`` over the record's business identity and raw
    provenance digest, so re-ingesting an identical raw record yields the same
    identity (surfacing duplicates) while a corrected raw record yields a new
    identity linkable through ``supersedes``.
    """

    identity = uuid5(
        HISTORY_NAMESPACE,
        "|".join(
            (
                payload.payload_kind.value,
                instrument,
                times.event_time.isoformat(),
                provenance.raw_record_sha256,
            )
        ),
    )
    candidate = MarketObservation(
        schema_version="1.0",
        observation_id=identity,
        instrument=instrument,
        times=times,
        payload=payload,
        provenance=provenance,
        supersedes=supersedes,
        quality_state=quality_state,
        quality_flags=quality_flags,
        payload_hash="0" * 64,
    )
    return candidate.model_copy(update={"payload_hash": compute_payload_hash(candidate)})


def build_historical_dataset(
    observations: Sequence[MarketObservation],
    *,
    source: str,
    source_version: str,
    data_classification: DatasetSourceClass,
    contract_master_version: str,
    file_hashes: Sequence[FileHashEntry],
    transform_lineage: Sequence[TransformStep],
    policy: HistoryValidationPolicy = DEFAULT_VALIDATION_POLICY,
) -> HistoricalDataset:
    """Validate observations and bind them into an immutable dataset.

    Fails closed with :class:`HistoricalTruthError` when any finding induces
    the ``INVALID`` quality state; degraded or stale records remain usable and
    surface through the manifest quality summary.
    """

    if not observations:
        raise ValueError("observations must be non-empty")
    report = validate_market_history(observations, policy=policy)
    invalid_codes = [
        item.code for item in report.findings if item.quality_state is DataQualityState.INVALID
    ]
    if invalid_codes:
        codes_text = ", ".join(sorted({code.value for code in invalid_codes}))
        raise HistoricalTruthError(
            invalid_codes[0],
            f"dataset rejected by historical-truth validation; offending codes: {codes_text}",
        )
    effective = compute_effective_states(observations, report.findings)
    summary_counts = {state: 0 for state in DataQualityState}
    for state in effective.values():
        summary_counts[state] += 1
    ordered_observations = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.times.available_to_strategy_time,
                item.times.event_time,
                item.observation_id,
            ),
        )
    )
    manifest = _build_manifest(
        observations=ordered_observations,
        source=source,
        source_version=source_version,
        data_classification=data_classification,
        contract_master_version=contract_master_version,
        file_hashes=tuple(file_hashes),
        transform_lineage=tuple(transform_lineage),
        validation_policy_hash=validation_policy_hash(policy),
        quality_summary=QualitySummary(
            good_count=summary_counts[DataQualityState.GOOD],
            degraded_count=summary_counts[DataQualityState.DEGRADED],
            unknown_count=summary_counts[DataQualityState.UNKNOWN],
            invalid_count=summary_counts[DataQualityState.INVALID],
        ),
    )
    return HistoricalDataset(manifest=manifest, observations=ordered_observations)


def _build_manifest(
    *,
    observations: tuple[MarketObservation, ...],
    source: str,
    source_version: str,
    data_classification: DatasetSourceClass,
    contract_master_version: str,
    file_hashes: tuple[FileHashEntry, ...],
    transform_lineage: tuple[TransformStep, ...],
    validation_policy_hash: str,
    quality_summary: QualitySummary,
) -> DatasetManifest:
    as_of_start = min(item.times.available_to_strategy_time for item in observations)
    as_of_end = max(item.times.available_to_strategy_time for item in observations)
    universe = frozenset(item.instrument for item in observations)
    candidate = DatasetManifest(
        schema_version="1.1",
        dataset_id=UUID(int=0),
        source=source,
        source_version=source_version,
        data_classification=data_classification,
        instrument_universe=tuple(sorted(universe)),
        as_of_start=as_of_start,
        as_of_end=as_of_end,
        contract_master_version=contract_master_version,
        file_hashes=file_hashes,
        transform_lineage=transform_lineage,
        row_count=len(observations),
        quality_summary=quality_summary,
        validation_policy_hash=validation_policy_hash,
        payload_hash="0" * 64,
    )
    preimage = payload_preimage(candidate)
    del preimage["dataset_id"]
    dataset_id = uuid5(DATASET_NAMESPACE, canonical_sha256(preimage))
    finalized = candidate.model_copy(update={"dataset_id": dataset_id})
    return finalized.model_copy(update={"payload_hash": compute_payload_hash(finalized)})


__all__ = [
    "build_historical_dataset",
    "build_market_observation",
]
