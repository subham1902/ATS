from __future__ import annotations

from datetime import UTC, datetime

import pytest
from ats.market.derivatives.artifacts import (
    ArtifactSourceClass,
    DerivativeProvenanceRecord,
    RawArtifactMetadata,
    build_provenance_record,
)

RETRIEVED_AT = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
RAW_HASH = "a" * 64
NORMALIZED_HASH = "b" * 64
MASTER_HASH = "c" * 64


def artifact(
    *,
    source_class: ArtifactSourceClass = ArtifactSourceClass.REAL_SOURCE,
    entitlement_class: str = "AUTHENTICATED_READ",
) -> RawArtifactMetadata:
    return RawArtifactMetadata(
        artifact_id="d08-test-artifact",
        provider="UPSTOX",
        source="NSE_BOD_EXPORT",
        endpoint_identity="/expired-instruments/option/contract",
        semantic_parameters=(),
        retrieved_at=RETRIEVED_AT,
        source_as_of=RETRIEVED_AT,
        instrument_identity=None,
        expiry=None,
        interval=None,
        timezone="Asia/Kolkata",
        provider_status="success",
        content_type="application/json",
        license_classification="PROVIDER_API_TERMS",
        entitlement_class=entitlement_class,
        source_class=source_class,
    )


def record(**overrides: object) -> DerivativeProvenanceRecord:
    values: dict[str, object] = dict(
        artifact=artifact(),
        raw_sha256=RAW_HASH,
        normalized_hash=NORMALIZED_HASH,
        contract_master_hash=MASTER_HASH,
        normalizer_version="ats-normalizer-1.0",
        freshness_semantics="EXCHANGE_SESSION_LATCHED_FRESH_STALE_RESYNC",
        data_start=datetime(2026, 8, 1, 3, 45, tzinfo=UTC),
        data_end=datetime(2026, 8, 22, 10, 0, tzinfo=UTC),
        record_count=375,
        interval="1minute",
        exchange="NSE",
        instrument_identity="NIFTY26AUG25000CE",
    )
    values.update(overrides)
    return build_provenance_record(**values)  # type: ignore[arg-type]


class TestCompleteRecord:
    def test_every_charter_field_is_present(self) -> None:
        subject = record()
        assert subject.provider == "UPSTOX"
        assert subject.provider_endpoint_or_file.endswith("/contract")
        assert subject.exchange == "NSE"
        assert subject.instrument_identity == "NIFTY26AUG25000CE"
        assert subject.retrieved_at == RETRIEVED_AT
        assert subject.source_as_of == RETRIEVED_AT
        assert subject.data_start < subject.data_end
        assert subject.interval == "1minute"
        assert subject.timezone == "Asia/Kolkata"
        assert subject.record_count == 375
        assert subject.raw_hash == RAW_HASH
        assert subject.normalized_hash == NORMALIZED_HASH
        assert subject.contract_master_hash == MASTER_HASH
        assert subject.normalizer_version == "ats-normalizer-1.0"
        assert subject.license_classification == "PROVIDER_API_TERMS"
        assert subject.entitlement_required is True
        assert subject.freshness_semantics.startswith("EXCHANGE_SESSION")
        assert subject.provider_status == "success"
        assert subject.source_revision is None
        assert subject.upstream_hashes[0].raw_sha256 == RAW_HASH

    def test_public_entitlement_is_not_flagged_required(self) -> None:
        subject = record(artifact=artifact(entitlement_class="PUBLIC"))
        assert subject.entitlement_required is False

    def test_upstream_chain_can_carry_multiple_raw_hashes(self) -> None:
        extra = ("d" * 64, "e" * 64)
        subject = record(upstream_raw_hashes=extra)
        linked = [link.raw_sha256 for link in subject.upstream_hashes]
        assert linked == [RAW_HASH, *extra]

    def test_raw_hash_is_the_first_chain_link(self) -> None:
        subject = record()
        assert subject.upstream_hashes[0].raw_sha256 == RAW_HASH
        assert subject.upstream_hashes[0].artifact_id == "d08-test-artifact"

    def test_source_revision_round_trips(self) -> None:
        assert record(source_revision="upstox-v3-rev-2").source_revision == "upstox-v3-rev-2"


class TestRefusals:
    def test_test_only_synthetic_artifact_is_refused(self) -> None:
        with pytest.raises(ValueError):
            record(artifact=artifact(source_class=ArtifactSourceClass.TEST_ONLY_SYNTHETIC))

    def test_raw_hash_absent_from_chain_is_refused(self) -> None:
        with pytest.raises(ValueError):
            DerivativeProvenanceRecord.model_validate(
                {
                    "schema_version": "1.0",
                    "record_id": "00000000-0000-0000-0000-000000000000",
                    "provider": "UPSTOX",
                    "provider_endpoint_or_file": "/x",
                    "exchange": "NSE",
                    "instrument_identity": None,
                    "retrieved_at": RETRIEVED_AT,
                    "source_as_of": RETRIEVED_AT,
                    "data_start": datetime(2026, 8, 1, tzinfo=UTC),
                    "data_end": datetime(2026, 8, 22, tzinfo=UTC),
                    "interval": "1minute",
                    "timezone": "Asia/Kolkata",
                    "record_count": 1,
                    "raw_hash": RAW_HASH,
                    "normalized_hash": NORMALIZED_HASH,
                    "contract_master_hash": MASTER_HASH,
                    "version": "v",
                    "license_classification": "PROVIDER_API_TERMS",
                    "entitlement_required": True,
                    "freshness_semantics": "EXPLICIT",
                    "provider_status": "success",
                    "source_revision": None,
                    "source_class": "REAL_SOURCE",
                    "upstream_hashes": [
                        {"artifact_id": "other", "raw_sha256": "f" * 64}
                    ],
                }
            )

    def test_inverted_window_is_refused(self) -> None:
        with pytest.raises(ValueError):
            record(
                data_start=datetime(2026, 8, 22, tzinfo=UTC),
                data_end=datetime(2026, 8, 1, tzinfo=UTC),
            )

    def test_blank_freshness_semantics_is_refused(self) -> None:
        with pytest.raises(ValueError):
            record(freshness_semantics="   ")


class TestDeterminism:
    def test_record_id_is_repeatable(self) -> None:
        assert record().record_id == record().record_id
        assert record().model_dump(exclude={"record_id"}) == record().model_dump(
            exclude={"record_id"}
        )

    def test_changed_evidence_changes_record_id(self) -> None:
        assert record(record_count=376).record_id != record().record_id


class TestRoundTrip:
    def test_json_round_trip_preserves_record(self) -> None:
        subject = record()
        restored = DerivativeProvenanceRecord.model_validate_json(subject.model_dump_json())
        assert restored == subject
