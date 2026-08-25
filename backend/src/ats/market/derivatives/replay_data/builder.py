"""Generic fixture builder with an explicit real-source Phase-P gate."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid5

from ats.contracts.hashing import canonical_json_bytes, canonical_sha256
from ats.market.derivatives.artifacts import ArtifactSourceClass
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.derivatives.providers import DerivativeFixtureManifest

from .models import (
    DerivativeFixtureBinding,
    FiveMinuteDerivativeBar,
    FixtureBuildResult,
    FixtureBuildSpec,
)

_FIXTURE_NAMESPACE = UUID("ef4dd6ea-38cd-54c8-9fbe-c7e8feb999a2")


def build_fixture(
    *, spec: FixtureBuildSpec, bars: tuple[FiveMinuteDerivativeBar, ...]
) -> FixtureBuildResult:
    if not bars:
        raise ValueError("fixture requires normalized bars")
    ordered = tuple(sorted(bars, key=lambda item: (item.bar_close, item.instrument_id)))
    if ordered != bars:
        raise ValueError("fixture bars must be deterministically ordered")
    identities = tuple((item.instrument_id, item.bar_close) for item in bars)
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate normalized bar identity")
    selected = set(spec.selected_contract_ids)
    if any(item.instrument_id not in selected for item in bars):
        raise ValueError("normalized bar does not bind to selected contract")
    raw_hash = canonical_sha256(tuple(item.raw_sha256 for item in spec.raw_artifacts))
    document = {
        "schema_version": "1.0",
        "fixture_name": spec.fixture_name,
        "session_date": spec.session_date,
        "expiry": spec.expiry,
        "raw_hash": raw_hash,
        "contract_master_hash": spec.contract_master_hash,
        "normalizer_version": spec.normalizer_version,
        "bars": bars,
    }
    normalized_hash = hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    fixture_id = uuid5(
        _FIXTURE_NAMESPACE,
        f"{spec.fixture_name}|{spec.contract_master_hash}|{raw_hash}|{normalized_hash}",
    )
    manifest = DerivativeFixtureManifest(
        schema_version="1.0",
        fixture_id=fixture_id,
        market=spec.market,
        underlying=DerivativeUnderlying(spec.underlying),
        source=spec.source,
        source_api_or_file=spec.source_api_or_file,
        provider=spec.provider,
        retrieved_at=spec.retrieved_at,
        source_version=spec.source_version,
        contract_master_hash=spec.contract_master_hash,
        interval="5m",
        timezone=spec.timezone,
        start_time=bars[0].bar_close,
        end_time=bars[-1].bar_close,
        record_count=len(bars),
        raw_hash=raw_hash,
        normalized_hash=normalized_hash,
        normalizer_version=spec.normalizer_version,
        data_cutoff=spec.data_cutoff,
        license_classification=spec.license_classification,
    )
    binding = DerivativeFixtureBinding(
        session_date=spec.session_date,
        expiry=spec.expiry,
        selected_contract_ids=spec.selected_contract_ids,
        raw_artifacts=spec.raw_artifacts,
    )
    evidence = {"manifest": manifest, "binding": binding}
    return FixtureBuildResult(
        manifest=manifest,
        binding=binding,
        bars=bars,
        manifest_hash=canonical_sha256(evidence),
    )


def assert_phase_p_eligible(result: FixtureBuildResult) -> None:
    if any(
        item.source_class is not ArtifactSourceClass.REAL_SOURCE
        for item in result.binding.raw_artifacts
    ):
        raise ValueError("Phase-P requires exclusively REAL_SOURCE artifacts")
    if "TEST" in result.manifest.license_classification.upper():
        raise ValueError("Phase-P forbids TEST_ONLY license classification")


__all__ = ["assert_phase_p_eligible", "build_fixture"]
