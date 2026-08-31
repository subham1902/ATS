"""Tests for ATS Autonomous Scanner scheduling, deduplication, and paper-trade pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from ats.contracts.common import SystemClock
from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import (
    DataQualityState,
    SessionState,
)
from ats.intelligence.agent_governance.governor import RuntimeChangeGovernor
from ats.intelligence.calibration.models import CalibrationObservation
from ats.intelligence.harness.harness_integration import A2HarnessIntegration
from ats.intelligence.harness.runtime import HarnessRuntimeAdapter
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    A2SessionState,
    UpstoxMarketFeedAdapter,
)


class _MockSidecar:
    def __init__(self) -> None:
        self.running = True
        self.sessions: list[str] = []
        self.prompts: list[tuple[str, str]] = []

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def healthy(self) -> bool:
        return self.running

    def create_session(self, *, cwd: str) -> str:
        sid = f"mock-session-{len(self.sessions) + 1}"
        self.sessions.append(sid)
        return sid

    def prompt(self, *, provider_session_id: str, prompt: str) -> str:
        self.prompts.append((provider_session_id, prompt))
        return f"ADVISORY[{provider_session_id}]: noted"

    def cancel(self, *, provider_session_id: str) -> None:
        pass


def _sample_snapshots(
    base_time: datetime, instrument_id: str = "NIFTY"
) -> tuple[MarketSnapshot, ...]:
    snapshots = []
    offset = base_time.minute % 5
    aligned_base = base_time - timedelta(
        minutes=offset, seconds=base_time.second, microseconds=base_time.microsecond
    )
    prices = [
        (Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), Decimal("1000")),
        (Decimal("101"), Decimal("103"), Decimal("100"), Decimal("102"), Decimal("1200")),
        (Decimal("102"), Decimal("104"), Decimal("101"), Decimal("103"), Decimal("1500")),
        (Decimal("103"), Decimal("106"), Decimal("102"), Decimal("105"), Decimal("2000")),
        (Decimal("105"), Decimal("108"), Decimal("104"), Decimal("107"), Decimal("2500")),
    ]
    for i, (op, hi, lo, cl, vol) in enumerate(prices):
        t = aligned_base + timedelta(minutes=5 * i)
        s = MarketSnapshot(
            schema_version="1.0",
            snapshot_id=uuid4(),
            instrument_id=instrument_id,
            exchange="NSE",
            segment="CASH",
            timeframe="5m",
            sequence=i + 1,
            bar_timestamp=t,
            received_at=t,
            open=op,
            high=hi,
            low=lo,
            close=cl,
            volume=vol,
            quality_state=DataQualityState.GOOD,
            quality_flags=(),
            source="feed",
            source_version="1.0.0",
            session_state=SessionState.OPEN,
            payload_hash="0" * 64,
        )
        snapshots.append(s.model_copy(update={"payload_hash": compute_payload_hash(s)}))
    return tuple(snapshots)


def _sample_calibration_observations(cutoff: datetime) -> tuple[CalibrationObservation, ...]:
    return tuple(
        CalibrationObservation(
            observation_id=uuid4(),
            forecast_probability=Decimal("0.74"),
            outcome_occurred=index < 15,
            observed_at=cutoff - timedelta(days=2, minutes=20 - index),
            available_to_strategy_time=cutoff - timedelta(days=2, minutes=20 - index),
            regime_evidence_id=None,
            realized_return_fraction=0.01 if index < 15 else -0.01,
            realized_volatility_fraction=0.015,
            realized_mfe_fraction=0.02,
            realized_mae_fraction=-0.01,
        )
        for index in range(20)
    )


def test_autonomous_scanner_starts_and_evaluates_on_ticks() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    assert controller.start(require_token=False) is True

    now = SystemClock().now()
    # Ingest NIFTY and BANKNIFTY ticks
    controller.process_tick("NIFTY", Decimal("24500.00"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    counters = controller.pipeline_counters()
    assert counters.scanner_observations >= 1
    assert counters.r10_evaluations >= 1
    assert counters.r10x_evaluations >= 1
    assert counters.regime_evaluations >= 1
    assert counters.feature_bundles >= 1

    # Without calibration observations, zero forced trades
    assert counters.candidates_qualified == 0
    assert counters.paper_orders == 0
    assert controller.status().real_orders_placed == 0
    assert counters.candidates_rejected >= 1
    assert counters.rejection_reasons.get("insufficient_calibration_support", 0) >= 1

    controller.stop()


def test_decision_state_deduplication() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)

    now = SystemClock().now()
    # Ingest initial decision state
    controller.process_tick("NIFTY", Decimal("24500.00"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)
    initial_scans = controller.pipeline_counters().scanner_observations
    assert initial_scans == 1

    # Send identical prices at same bar timestamp 5 times
    for _ in range(5):
        controller.process_tick("NIFTY", Decimal("24500.00"), at=now)
        controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    # Scans must remain exactly 1 (deduplication proof)
    assert controller.pipeline_counters().scanner_observations == 1

    # Update mark -> new decision state
    controller.process_tick("NIFTY", Decimal("24510.00"), at=now)
    assert controller.pipeline_counters().scanner_observations == 2

    # New 5-minute bar -> new decision state
    next_bar_time = now + timedelta(minutes=5)
    controller.process_tick("NIFTY", Decimal("24510.00"), at=next_bar_time)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=next_bar_time)
    assert controller.pipeline_counters().scanner_observations == 3

    controller.stop()


def test_stale_and_unhealthy_feed_prevents_new_risk() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)

    now = SystemClock().now()
    feed.set_healthy(False)

    controller.process_tick("NIFTY", Decimal("24500.00"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    # Unhealthy feed prevents automatic scanner execution
    assert controller.pipeline_counters().scanner_observations == 0

    # Restore feed health
    feed.set_healthy(True)

    # Set marks with old timestamp
    old_time = now - timedelta(milliseconds=controller.config.max_quote_age_ms + 1)
    feed.set_mark("NIFTY", Decimal("24500.00"), at=old_time)
    feed.set_mark("BANKNIFTY", Decimal("52800.00"), at=old_time)

    # Evaluated just beyond the configured inclusive freshness boundary.
    outcome = controller._maybe_scan_decision_ready_state(now)
    assert outcome is None
    assert controller.pipeline_counters().scanner_observations == 0

    controller.stop()


def test_scanner_exception_isolated_from_p0_p1() -> None:
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(market_feed=feed)
    controller.start(require_token=False)

    # Monkeypatch scan_market_for_candidates to throw
    def _broken_scan(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("INJECTED_SCANNER_FAILURE")

    controller.scan_market_for_candidates = _broken_scan  # type: ignore[assignment]

    now = SystemClock().now()
    res1 = controller.process_tick("NIFTY", Decimal("24500.00"), at=now)
    res2 = controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    # Tick processing and session health remain completely alive
    assert res1["accepted"] is True
    assert res2["accepted"] is True
    assert controller.health()["status"] == "HEALTHY"
    assert controller.state is A2SessionState.RUNNING

    controller.stop()


def test_automatic_qualifying_candidate_paper_broker_pipeline() -> None:
    feed = UpstoxMarketFeedAdapter()
    config = A2PaperSessionConfig(
        execution_target="PAPER",
        live_money="DISABLED",
        lot_sizes={"NIFTY_CE": 1, "NIFTY_PE": 1},
    )
    controller = A2PaperSessionController(config=config, market_feed=feed)
    controller.start(require_token=False)

    now = SystemClock().now()
    # Seed 5-bar snapshot history with positive momentum on NIFTY
    snaps = _sample_snapshots(now - timedelta(minutes=25), instrument_id="NIFTY")
    controller.seed_snapshot_history("NIFTY", snaps)

    controller.set_calibration_observations_provider(lambda: _sample_calibration_observations(now))

    # Ingest decision-ready tick matching the last bar
    controller.process_tick("NIFTY", Decimal("107.00"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    # The pipeline should have qualified a candidate and submitted it to PaperBroker
    counters = controller.pipeline_counters()
    assert counters.scanner_observations >= 1
    assert counters.candidates_qualified >= 1
    assert counters.paper_orders >= 1
    assert counters.paper_fills >= 1
    assert counters.a04_allow >= 1
    assert controller.status().real_orders_placed == 0
    assert controller.status().live_money == "DISABLED"
    assert controller.status().execution_target == "PAPER"
    assert len(controller.engine.state.open_positions) >= 1

    # Position monitor exit flow: move mark to trigger exit
    pos_id = next(iter(controller.engine.state.open_positions.keys()))
    pos = controller.engine.state.open_positions[pos_id]
    entry_price = pos.entry_price

    # Process mark move that triggers monitor exit
    exit_time = now + timedelta(seconds=1)
    controller.process_tick(pos.instrument_id, entry_price + Decimal("50.00"), at=exit_time)
    controller.engine.request_exit(
        pos_id, exit_time, reason_codes=("PROFIT_TARGET",), source="MONITOR"
    )
    controller.engine.handle_exit_fill(pos_id, exit_time)
    controller.runtime_provider.update_from_engine(controller.engine)

    assert len(controller.engine.state.open_positions) == 0
    assert controller.status().open_paper_positions == 0
    assert controller.status().paper_fills_recorded >= 1

    controller.stop()


def test_harness_material_event_routing() -> None:
    sidecar = _MockSidecar()
    adapter = HarnessRuntimeAdapter(sidecar=sidecar, clock=SystemClock())
    governor = RuntimeChangeGovernor(clock=SystemClock())
    integration = A2HarnessIntegration(governor=governor, adapter=adapter)
    integration.start()

    controller = A2PaperSessionController()
    controller.attach_harness_integration(integration)
    controller.start(require_token=False)

    now = SystemClock().now()
    controller.notify_material_event("REGIME_CHANGE", "Regime changed to TREND", now=now)
    controller.notify_material_event(
        "OPPORTUNITY_QUALIFIED", "Candidate qualified on NIFTY_CE", now=now
    )
    controller.notify_material_event("POSITION_DETERIORATION", "Position stop hit", now=now)

    assert len(sidecar.prompts) >= 3  # Routed through adapter to sidecar
    controller.stop()


def test_portfolio_brain_and_a04_deny_remain_safe() -> None:
    # Capital budget too small -> Portfolio Brain denies
    config = A2PaperSessionConfig(capital_budget=Decimal("100"))
    controller = A2PaperSessionController(config=config)
    controller.start(require_token=False)

    now = SystemClock().now()
    # Seed 5-bar snapshot history with positive momentum on NIFTY
    snaps = _sample_snapshots(now - timedelta(minutes=25), instrument_id="NIFTY")
    controller.seed_snapshot_history("NIFTY", snaps)

    controller.set_calibration_observations_provider(lambda: _sample_calibration_observations(now))

    controller.process_tick("NIFTY", Decimal("107.00"), at=now)
    controller.process_tick("BANKNIFTY", Decimal("52800.00"), at=now)

    # Denied by Portfolio Brain -> No paper order
    counters = controller.pipeline_counters()
    assert counters.paper_orders == 0
    assert counters.candidates_qualified == 0
    assert counters.portfolio_brain_deny >= 1
    assert len(controller.engine.state.open_positions) == 0

    controller.stop()
