from __future__ import annotations

from uuid import UUID

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.intelligence.models import MarketContext
from ats.contracts.intelligence.types import LiquidityState, VolatilityState
from ats.intelligence.regime import detect_regime
from ats.market import (
    ApprovedFixture,
    ReplayConfiguration,
    approved_manifest,
    create_approved_replay,
    nse_cash_alpha_v1_calendar,
)
from ats.market.features import compute_feature_bundle

from tests.unit.intelligence.regime.helpers import configuration


def test_b01_replay_to_r01_features_to_r02_regime() -> None:
    manifest = approved_manifest(ApprovedFixture.NSE_CASH_RELIANCE_5M_V1)
    replay = create_approved_replay(
        ApprovedFixture.NSE_CASH_RELIANCE_5M_V1,
        nse_cash_alpha_v1_calendar(),
        ReplayConfiguration(start_at=manifest.first_bar, received_delay_ms=250),
    )
    snapshots = tuple(replay.advance() for _ in range(manifest.bar_count))
    bundles = tuple(
        compute_feature_bundle(snapshots, cutoff_sequence=snapshot.sequence)
        for snapshot in snapshots
        if snapshot.sequence >= 4
    )
    current = bundles[-1]
    snapshot = snapshots[-1]
    market_context = MarketContext(
        schema_version="1.0",
        market_context_id=UUID("30000000-0000-0000-0000-000000000001"),
        instrument_spec_id=UUID("30000000-0000-0000-0000-000000000002"),
        instrument_id=snapshot.instrument_id,
        snapshot_id=snapshot.snapshot_id,
        feature_bundle_id=current.feature_bundle_id,
        timeframe=snapshot.timeframe,
        as_of_time=current.computed_at,
        data_cutoff=snapshot.bar_timestamp,
        session_state=snapshot.session_state,
        data_quality_state=snapshot.quality_state,
        freshness_ms=250,
        liquidity_state=LiquidityState.NORMAL,
        volatility_state=VolatilityState.NORMAL,
        higher_timeframe_context_refs=(),
        related_market_context_refs=(),
        cost_model_version="PAPER-V1",
        input_hash=current.input_hash,
        payload_hash="0" * 64,
    )
    market_context = market_context.model_copy(
        update={"payload_hash": compute_payload_hash(market_context)}
    )
    evidence = detect_regime(
        market_context=market_context,
        feature_history=bundles,
        configuration=configuration(),
    )
    assert evidence.market_context_id == market_context.market_context_id
    assert evidence.instrument_id == snapshot.instrument_id
    assert evidence.data_cutoff <= evidence.as_of_time
    assert evidence.payload_hash == compute_payload_hash(evidence)
