"""Comprehensive unit and integration tests for ATS-BIN-01 strategy import and tournament."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from ats.console.app import create_console_app
from ats.market.fabric import MarketDataFabric
from ats.market.feeds.upstox_v3.messages import NormalizedFeedUpdate, UpdateKind
from ats.market.strategy_import import (
    BaseImportedAdapter,
    MarketSnapshotContext,
    ShadowTournamentEngine,
    StrategyCompatibilityState,
    StrategyDecoder,
    StrategyStatus,
    create_all_adapters,
)
from fastapi.testclient import TestClient

BIN_DIR = Path(r"D:\Projects\ATS\ATS trade data\strategy bins")

# The strategy bins are operator material kept outside the repository, so a
# clone or CI runner cannot have them. These three tests read that directory
# directly; they must say the evidence is absent rather than fail on an
# absolute local path. The remaining tests in this module build their adapters
# from code and run everywhere.
requires_strategy_bins = pytest.mark.skipif(
    not BIN_DIR.exists(),
    reason=f"strategy bin evidence lives outside the repo at {BIN_DIR}",
)


@requires_strategy_bins
def test_inventory_and_hashing() -> None:
    """Verify inventory, SHA-256 calculation, and entropy for strategy bin files."""
    assert BIN_DIR.exists(), f"Bin directory {BIN_DIR} must exist"
    items = list(BIN_DIR.glob("*.py")) + list(BIN_DIR.glob("*.sh"))
    assert len(items) == 9, f"Expected 9 files in {BIN_DIR}, found {len(items)}"

    for p in items:
        info = StrategyDecoder.inspect_file(p)
        assert len(str(info["sha256"])) == 64
        assert int(info["size"]) > 0
        assert float(info["entropy"]) > 4.0
        assert not info["is_quarantined"]


@requires_strategy_bins
def test_safe_decoder_and_authority() -> None:
    """Verify that decoded strategies strictly have authority = RESEARCH_ONLY."""
    strategies = StrategyDecoder.scan_directory(BIN_DIR)
    assert len(strategies) == 9

    for s in strategies:
        assert s.authority == "RESEARCH_ONLY", "CRITICAL: Imported strategy must be RESEARCH_ONLY"
        assert s.status == StrategyStatus.SHADOW_READY
        assert s.compatibility_state == StrategyCompatibilityState.LIVE_COMPATIBLE
        assert "open" in s.required_data_fields
        assert "close" in s.required_data_fields


def test_quarantine_policy(tmp_path: Path) -> None:
    """Verify that unsafe files (pickle, dangerous calls, malformed AST) are quarantined."""
    # Create an unsafe file with eval
    unsafe_file = tmp_path / "unsafe_eval.py"
    unsafe_file.write_text("cat << 'EOF' > bad.py\nx = eval('1+1')\nEOF", encoding="utf-8")

    meta = StrategyDecoder.decode_metadata(unsafe_file)
    assert meta.status == StrategyStatus.QUARANTINED
    assert meta.compatibility_state == StrategyCompatibilityState.QUARANTINED
    assert "DANGEROUS_CALLS_OR_INVALID_AST" in meta.blockers


def test_adapters_no_broker_authority() -> None:
    """Verify that adapters only produce StrategyDecision and have no broker authority."""
    adapters = create_all_adapters()
    assert len(adapters) == 9

    now = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)
    ctx = MarketSnapshotContext(
        instrument_key="MCX_FO|GOLDM",
        timestamp=now,
        last_price=Decimal("72500.00"),
        recent_5m_closes=tuple(Decimal(str(p)) for p in range(72400, 72500, 5)),
        recent_1h_closes=tuple(Decimal(str(p)) for p in range(72000, 72500, 10)),
        pdh=Decimal("72400.00"),
        pdl=Decimal("72100.00"),
        is_yesterday_nr7=True,
        opening_range_high=Decimal("72450.00"),
        opening_range_low=Decimal("72350.00"),
    )

    for adapter in adapters:
        assert not hasattr(adapter, "place_order"), "Adapter must not have place_order"
        assert not hasattr(adapter, "broker"), "Adapter must not have broker reference"
        assert not hasattr(adapter, "paper_broker"), "Adapter must not have paper_broker reference"

        decision = adapter.on_market_event(ctx)
        if decision is not None:
            assert decision.strategy_id == adapter.strategy_id
            assert decision.action in ["BUY", "SELL", "HOLD", "CLOSE"]
            assert decision.direction in ["LONG", "SHORT", "FLAT"]


def test_strategy_exception_isolation() -> None:
    """Verify that a failing strategy adapter does not crash the tournament engine."""
    fabric = MarketDataFabric(source_label="TEST")

    class BrokenAdapter(BaseImportedAdapter):
        def __init__(self) -> None:
            super().__init__("BIN_BROKEN", "broken_model")

        def _evaluate(self, context: MarketSnapshotContext) -> None:
            raise RuntimeError("Deliberate failure in broken strategy")

    adapters = create_all_adapters() + [BrokenAdapter()]
    engine = ShadowTournamentEngine(fabric=fabric, adapters=adapters)

    # Publish a tick
    now = datetime.now(UTC)
    tick = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.INDEX,
        last_traded_price=Decimal("72500.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=100,
    )

    # Engine must process tick without raising RuntimeError
    decisions = engine.on_tick(tick)
    assert "BIN_BROKEN" in decisions
    assert decisions["BIN_BROKEN"] is None

    # Broken adapter must transition to RUNTIME_BLOCKED
    broken_metric = engine.metrics["BIN_BROKEN"]
    assert broken_metric.status == StrategyStatus.RUNTIME_BLOCKED


def test_tournament_telemetry_and_metrics() -> None:
    """Verify that tournament engine tracks PnL, win rate, and sample status honestly."""
    fabric = MarketDataFabric(source_label="TEST")
    engine = ShadowTournamentEngine(fabric=fabric)

    now = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)

    # Feed ticks
    t1 = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.INDEX,
        last_traded_price=Decimal("72500.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=10,
    )
    fabric.publish(t1)
    engine.on_tick(t1)

    leaderboard = engine.get_leaderboard()
    assert len(leaderboard) == 9
    for m in leaderboard:
        # Sample size honesty: < 20 samples must report INSUFFICIENT_EVIDENCE
        assert m.sample_status == "INSUFFICIENT_EVIDENCE"


@requires_strategy_bins
def test_imported_strategies_api_endpoints() -> None:
    """Verify REST endpoints for imported strategies."""
    app = create_console_app()
    client = TestClient(app)

    # 1. GET /v1/strategies/imported
    res = client.get("/v1/strategies/imported")
    assert res.status_code == 200
    data = res.json()
    assert data["total_files"] == 9
    assert data["admitted_count"] == 9
    assert data["quarantined_count"] == 0
    assert len(data["strategies"]) == 9
    assert len(data["tournament"]) == 9

    # 2. POST /v1/strategies/imported/scan
    res_scan = client.post("/v1/strategies/imported/scan")
    assert res_scan.status_code == 200
    assert res_scan.json()["total_files"] == 9

    # 3. GET /v1/strategies/imported/tournament
    res_tour = client.get("/v1/strategies/imported/tournament")
    assert res_tour.status_code == 200
    assert len(res_tour.json()) == 9

    # 4. GET /v1/strategies/imported?include_native=true (Unified view)
    res_unified = client.get("/v1/strategies/imported?include_native=true")
    assert res_unified.status_code == 200
    assert len(res_unified.json()["tournament"]) == 10
    strat_ids = [s["strategy_id"] for s in res_unified.json()["tournament"]]
    assert "S17" in strat_ids
    assert "BIN_S01" in strat_ids


def test_ats_bin_02_s17_native_and_cost_stress() -> None:
    """Verify ATS-BIN-02 prospective requirements: S17 OI state machine, cost
    stress, and sample support honesty.
    """
    fabric = MarketDataFabric(source_label="TEST_PROSPECTIVE")
    engine = ShadowTournamentEngine(fabric=fabric, include_native=True)

    now = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)

    # 1. Tick without OI -> S17 is DATA_BLOCKED / no trade
    t_no_oi = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.OPTION,
        last_traded_price=Decimal("72500.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=50,
        open_interest=None,
    )
    decisions = engine.on_tick(t_no_oi)
    assert decisions["S17"] is None

    # 2. Tick with initial OI baseline
    t_oi_base = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.OPTION,
        last_traded_price=Decimal("72500.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=50,
        open_interest=1000,
    )
    engine.on_tick(t_oi_base)

    # 3. Tick with Price UP, OI UP, Volume active -> S17 Long Buildup
    t_long = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.OPTION,
        last_traded_price=Decimal("72550.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=75,
        open_interest=1100,
    )
    decisions2 = engine.on_tick(t_long)
    assert decisions2["S17"] is not None
    assert decisions2["S17"].action == "BUY"
    assert decisions2["S17"].direction == "LONG"

    # 4. Tick with Price DOWN, OI DOWN -> S17 Long Unwinding (exit)
    t_exit = NormalizedFeedUpdate(
        instrument_key="MCX_FO|GOLDM",
        kind=UpdateKind.OPTION,
        last_traded_price=Decimal("72520.00"),
        exchange_timestamp=now,
        received_at=now,
        volume=80,
        open_interest=1050,
    )
    decisions3 = engine.on_tick(t_exit)
    assert decisions3["S17"] is not None
    assert decisions3["S17"].action == "CLOSE"

    metrics = engine.metrics["S17"]
    assert metrics.support_count == 1
    assert metrics.support_target == 20
    assert metrics.sample_status == "INSUFFICIENT_EVIDENCE"  # Target is 20
    assert metrics.cost_stress_base == Decimal("40.00")
    assert metrics.cost_stress_1_5x == Decimal("60.00")
    assert metrics.cost_stress_2_0x == Decimal("80.00")
