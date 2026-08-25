from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain.types import DataQualityState
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.intelligence_cache import (
    IntelligenceStaleness,
    MarketIntelligenceCache,
    build_market_intelligence_snapshot,
)

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def snapshot(*, quality: DataQualityState = DataQualityState.GOOD, offset: int = 0):
    as_of = NOW + timedelta(seconds=offset)
    return build_market_intelligence_snapshot(
        underlying=DerivativeUnderlying.NIFTY,
        data_cutoff=as_of,
        as_of_time=as_of,
        valid_until=as_of + timedelta(minutes=5),
        regime_reference="REGIME-EVIDENCE-1",
        forecast_reference=None,
        calibrated_probability=Decimal("0.6"),
        thesis_reference="THESIS-EVIDENCE-1",
        quality=quality,
    )


def test_nonblocking_read_returns_unknown_when_background_has_not_published() -> None:
    result = MarketIntelligenceCache().read(underlying=DerivativeUnderlying.NIFTY, at_time=NOW)
    assert result.status is IntelligenceStaleness.UNKNOWN
    assert result.snapshot is None


def test_valid_then_stale_read_does_not_wait_for_refresh() -> None:
    cache = MarketIntelligenceCache()
    value = snapshot()
    cache.update(value)
    assert (
        cache.read(underlying=DerivativeUnderlying.NIFTY, at_time=NOW).status
        is IntelligenceStaleness.VALID
    )
    assert (
        cache.read(
            underlying=DerivativeUnderlying.NIFTY,
            at_time=NOW + timedelta(minutes=5),
        ).status
        is IntelligenceStaleness.STALE
    )


def test_bad_quality_is_stale_and_temporal_regression_rejected() -> None:
    cache = MarketIntelligenceCache()
    later = snapshot(offset=10)
    cache.update(later)
    with pytest.raises(ValueError, match="regression"):
        cache.update(snapshot(offset=0))
    degraded = snapshot(quality=DataQualityState.DEGRADED, offset=20)
    cache.update(degraded)
    assert (
        cache.read(
            underlying=DerivativeUnderlying.NIFTY,
            at_time=NOW + timedelta(seconds=20),
        ).status
        is IntelligenceStaleness.STALE
    )


def test_snapshot_hash_is_deterministic_and_has_no_authority_method() -> None:
    assert snapshot().payload_hash == snapshot().payload_hash
    assert not hasattr(snapshot(), "authorize")
    assert not hasattr(snapshot(), "place_order")
