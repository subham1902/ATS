"""Assembled provenance records binding raw artifacts to normalized evidence.

Every future acquired raw/normalized derivative artifact must be able to carry
this record. Construction fails closed: a record cannot exist without the
complete integrity chain, an explicit license classification, an explicit
entitlement requirement, and explicit freshness semantics. Existing D01
provenance requirements are strengthened, never weakened.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid5

from pydantic import model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, PositiveInt, Sha256
from ats.contracts.hashing import canonical_sha256
from ats.market.derivatives.artifacts.models import (
    ArtifactId,
    ArtifactSourceClass,
    RawArtifactMetadata,
)

_PROVENANCE_NAMESPACE = UUID("9f2f6a3e-6a5c-4b8e-9d0a-1f0c1d2b3a70")


class UpstreamHashLink(ATSBaseModel):
    """One hop in the upstream raw-to-normalized hash chain."""

    artifact_id: ArtifactId
    raw_sha256: Sha256


class DerivativeProvenanceRecord(ATSBaseModel):
    """Complete charter provenance for one acquired dataset."""

    schema_version: Literal["1.0"]
    record_id: UUID
    provider: NonEmptyStr
    provider_endpoint_or_file: NonEmptyStr
    exchange: NonEmptyStr
    instrument_identity: NonEmptyStr | None
    retrieved_at: UTCDateTime
    source_as_of: UTCDateTime | None
    data_start: UTCDateTime
    data_end: UTCDateTime
    interval: NonEmptyStr
    timezone: Literal["Asia/Kolkata"]
    record_count: PositiveInt
    raw_hash: Sha256
    normalized_hash: Sha256
    contract_master_hash: Sha256
    normalizer_version: NonEmptyStr
    license_classification: NonEmptyStr
    entitlement_required: bool
    freshness_semantics: NonEmptyStr
    provider_status: NonEmptyStr
    source_revision: NonEmptyStr | None
    source_class: ArtifactSourceClass
    upstream_hashes: tuple[UpstreamHashLink, ...]

    @model_validator(mode="after")
    def validate_chain(self) -> DerivativeProvenanceRecord:
        if self.data_end < self.data_start:
            raise ValueError("data_end must be >= data_start")
        if not self.upstream_hashes:
            raise ValueError("upstream hash chain must be non-empty")
        linked = {link.raw_sha256 for link in self.upstream_hashes}
        if self.raw_hash not in linked:
            raise ValueError("raw_hash must appear in the upstream hash chain")
        if not self.freshness_semantics.strip():
            raise ValueError("freshness_semantics must be explicit")
        return self


def build_provenance_record(
    *,
    artifact: RawArtifactMetadata,
    raw_sha256: Sha256,
    normalized_hash: Sha256,
    contract_master_hash: Sha256,
    normalizer_version: NonEmptyStr,
    freshness_semantics: NonEmptyStr,
    data_start: UTCDateTime,
    data_end: UTCDateTime,
    record_count: PositiveInt,
    interval: NonEmptyStr,
    exchange: NonEmptyStr,
    instrument_identity: NonEmptyStr | None,
    source_revision: NonEmptyStr | None = None,
    upstream_raw_hashes: tuple[Sha256, ...] = (),
) -> DerivativeProvenanceRecord:
    """Assemble a provenance record from existing D01 evidence; refuse gaps."""

    if artifact.source_class is ArtifactSourceClass.TEST_ONLY_SYNTHETIC:
        raise ValueError("TEST_ONLY_SYNTHETIC artifacts cannot back a provenance record")
    if artifact.entitlement_class.strip() == "":
        raise ValueError("entitlement classification is required")
    chain_ids = [
        artifact.artifact_id,
        *(f"{artifact.artifact_id}.{index}" for index in range(len(upstream_raw_hashes))),
    ]
    links = tuple(
        UpstreamHashLink(artifact_id=chain_ids[index], raw_sha256=digest)
        for index, digest in enumerate((raw_sha256, *upstream_raw_hashes))
    )
    values: dict[str, object] = {
        "schema_version": "1.0",
        "provider": artifact.provider,
        "provider_endpoint_or_file": artifact.endpoint_identity,
        "exchange": exchange,
        "instrument_identity": instrument_identity,
        "retrieved_at": artifact.retrieved_at,
        "source_as_of": artifact.source_as_of,
        "data_start": data_start,
        "data_end": data_end,
        "interval": interval,
        "timezone": "Asia/Kolkata",
        "record_count": record_count,
        "raw_hash": raw_sha256,
        "normalized_hash": normalized_hash,
        "contract_master_hash": contract_master_hash,
        "normalizer_version": normalizer_version,
        "license_classification": artifact.license_classification,
        "entitlement_required": artifact.entitlement_class.upper() not in {"PUBLIC", "NONE"},
        "freshness_semantics": freshness_semantics,
        "provider_status": artifact.provider_status,
        "source_revision": source_revision,
        "source_class": artifact.source_class,
        "upstream_hashes": links,
    }
    record_id = uuid5(_PROVENANCE_NAMESPACE, canonical_sha256(values))
    return DerivativeProvenanceRecord.model_validate({**values, "record_id": record_id})


__all__ = ["DerivativeProvenanceRecord", "UpstreamHashLink", "build_provenance_record"]
