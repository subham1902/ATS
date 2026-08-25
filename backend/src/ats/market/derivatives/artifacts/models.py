"""Secret-free provenance metadata for immutable raw source bytes."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import StringConstraints, model_validator

from ats.contracts.common import ATSBaseModel, UTCDateTime
from ats.contracts.domain.types import NonEmptyStr, NonNegativeInt, Sha256


class ArtifactSourceClass(StrEnum):
    REAL_SOURCE = "REAL_SOURCE"
    TEST_ONLY_SYNTHETIC = "TEST_ONLY_SYNTHETIC"
    RECORDED_PROVIDER_SHAPE = "RECORDED_PROVIDER_SHAPE"


ArtifactId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


class SemanticParameter(ATSBaseModel):
    name: NonEmptyStr
    value: NonEmptyStr

    @model_validator(mode="after")
    def reject_secrets(self) -> SemanticParameter:
        lowered = self.name.casefold()
        if any(term in lowered for term in ("authorization", "token", "secret", "cookie")):
            raise ValueError("secret-bearing semantic parameter is forbidden")
        return self


class RawArtifactMetadata(ATSBaseModel):
    artifact_id: ArtifactId
    provider: NonEmptyStr
    source: NonEmptyStr
    endpoint_identity: NonEmptyStr
    semantic_parameters: tuple[SemanticParameter, ...]
    retrieved_at: UTCDateTime
    source_as_of: UTCDateTime | None
    instrument_identity: NonEmptyStr | None
    expiry: NonEmptyStr | None
    interval: NonEmptyStr | None
    timezone: NonEmptyStr
    provider_status: NonEmptyStr
    content_type: NonEmptyStr
    license_classification: NonEmptyStr
    entitlement_class: NonEmptyStr
    source_class: ArtifactSourceClass


class StoredRawArtifact(ATSBaseModel):
    metadata: RawArtifactMetadata
    raw_sha256: Sha256
    content_length: NonNegativeInt
    content_path: NonEmptyStr
    metadata_path: NonEmptyStr


__all__ = [
    "ArtifactId",
    "ArtifactSourceClass",
    "RawArtifactMetadata",
    "SemanticParameter",
    "StoredRawArtifact",
]
