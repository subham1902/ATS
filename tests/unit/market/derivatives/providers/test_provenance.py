from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.derivatives.providers import (
    DerivativeFixtureManifest,
    MarketFeedHealth,
    SourceFreshness,
)

T0 = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)
HASH = "a" * 64


def manifest(**updates: object) -> DerivativeFixtureManifest:
    values = {
        "schema_version": "1.0",
        "fixture_id": UUID("5e1647bb-4cfc-5a58-85e7-b9a0229bff49"),
        "market": "NSE_FO",
        "underlying": DerivativeUnderlying.NIFTY,
        "source": "NSE_REFERENCE",
        "source_api_or_file": "approved-contract.gz",
        "provider": "NSE",
        "retrieved_at": T0,
        "source_version": None,
        "contract_master_hash": HASH,
        "interval": "5minute",
        "timezone": "Asia/Kolkata",
        "start_time": T0,
        "end_time": T0,
        "record_count": 1,
        "raw_hash": HASH,
        "normalized_hash": HASH,
        "normalizer_version": "1.0.0",
        "data_cutoff": T0,
        "license_classification": "APPROVED_REPLAY",
    }
    values.update(updates)
    return DerivativeFixtureManifest.model_validate(values)


def test_manifest_records_required_provenance() -> None:
    assert manifest().underlying is DerivativeUnderlying.NIFTY


@pytest.mark.parametrize("field", ("raw_hash", "normalized_hash", "contract_master_hash"))
def test_hashes_are_strict(field: str) -> None:
    with pytest.raises(ValueError):
        manifest(**{field: "not-a-hash"})


def test_future_cutoff_is_required_for_complete_replay_window() -> None:
    with pytest.raises(ValueError, match="data_cutoff"):
        manifest(data_cutoff=T0.replace(year=2025))


def test_feed_health_never_claims_processed_before_received() -> None:
    with pytest.raises(ValueError, match="processed_at"):
        MarketFeedHealth(
            provider="fake",
            stream_id="one",
            exchange_time=None,
            provider_time=None,
            received_at=T0,
            processed_at=T0.replace(year=2025),
            freshness=SourceFreshness.UNKNOWN,
            reason_codes=("NO_STREAM",),
        )
