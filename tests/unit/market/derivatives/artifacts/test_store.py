from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ats.market.derivatives.artifacts import (
    ArtifactConflictError,
    ArtifactSourceClass,
    RawArtifactMetadata,
    RawArtifactStore,
    SemanticParameter,
)
from pydantic import ValidationError


def metadata() -> RawArtifactMetadata:
    return RawArtifactMetadata(
        artifact_id="TEST_ONLY_PROVIDER_SHAPE_1",
        provider="FAKE_UPSTOX",
        source="RECORDED_PROVIDER_SHAPE",
        endpoint_identity="GET_EXPIRED_CANDLES",
        semantic_parameters=(SemanticParameter(name="instrument_key", value="TEST_FO|1"),),
        retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        source_as_of=None,
        instrument_identity="TEST_FO|1",
        expiry="2026-08-24",
        interval="1minute",
        timezone="Asia/Kolkata",
        provider_status="RECORDED_TEST_SHAPE",
        content_type="application/json",
        license_classification="TEST_ONLY",
        entitlement_class="NOT_APPLICABLE_TEST",
        source_class=ArtifactSourceClass.RECORDED_PROVIDER_SHAPE,
    )


def test_same_bytes_deduplicate_and_different_bytes_conflict(tmp_path) -> None:
    store = RawArtifactStore(tmp_path)
    first = store.store(metadata=metadata(), content=b'{"shape":1}')
    second = store.store(metadata=metadata(), content=b'{"shape":1}')
    assert first.raw_sha256 == second.raw_sha256
    assert first.content_path == second.content_path
    with pytest.raises(ArtifactConflictError, match="different immutable bytes"):
        store.store(metadata=metadata(), content=b'{"shape":2}')


def test_deduplication_returns_original_provenance(tmp_path) -> None:
    store = RawArtifactStore(tmp_path)
    first = store.store(metadata=metadata(), content=b"same")
    changed = metadata().model_copy(update={"provider_status": "LATER_OBSERVATION"})
    second = store.store(metadata=changed, content=b"same")
    assert second == first


def test_metadata_sidecar_contains_hash_but_no_headers(tmp_path) -> None:
    stored = RawArtifactStore(tmp_path).store(metadata=metadata(), content=b"shape")
    sidecar = (tmp_path / "TEST_ONLY_PROVIDER_SHAPE_1.metadata.json").read_text()
    assert stored.raw_sha256 in sidecar
    assert "Authorization" not in sidecar
    assert "Bearer" not in sidecar


@pytest.mark.parametrize("name", ("Authorization", "access_token", "client_secret", "cookie"))
def test_secret_bearing_metadata_keys_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError, match="secret-bearing"):
        SemanticParameter(name=name, value="REDACTED_TEST_VALUE")
