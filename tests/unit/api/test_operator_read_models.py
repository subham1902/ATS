from __future__ import annotations

from ats.contracts.common import SystemClock
from ats.observability.operator_intelligence import (
    CandidateClass,
    EdgeLedgerEntry,
    EdgeLedgerReadModel,
    FunnelCounts,
    OperatorSurvivalState,
    OpportunityScannerReadModel,
    RejectionBreakdown,
    resolve_operator_survival_state,
)


def test_operator_survival_state_resolution() -> None:
    # 1. Halted
    state, reasons = resolve_operator_survival_state(is_halted=True)
    assert state == OperatorSurvivalState.HALTED
    assert "SAFETY_HALTED" in reasons

    # 2. Cooldown
    state, reasons = resolve_operator_survival_state(loss_state="COOLDOWN")
    assert state == OperatorSurvivalState.COOLDOWN
    assert "COOLDOWN_ACTIVE" in reasons

    # 3. Exit only
    state, reasons = resolve_operator_survival_state(can_enter=False, can_reduce=True)
    assert state == OperatorSurvivalState.EXIT_ONLY
    assert "EXIT_ONLY_ENFORCED" in reasons

    # 4. Safe mode due feed unhealthy
    state, reasons = resolve_operator_survival_state(feed_healthy=False, broker_healthy=True)
    assert state == OperatorSurvivalState.SAFE
    assert "FEED_DEGRADED" in reasons

    state, reasons = resolve_operator_survival_state(
        loss_state="CAUTION",
        effective_mode="NORMAL",
        feed_healthy=True,
        broker_healthy=True,
        system_state="READY",
    )
    assert state == OperatorSurvivalState.CAUTION
    assert reasons == ("LOSS_CAUTION",)

    # 5. Normal mode
    state, reasons = resolve_operator_survival_state(
        effective_mode="NORMAL",
        feed_healthy=True,
        broker_healthy=True,
        system_state="READY",
        can_enter=True,
        can_reduce=True,
    )
    assert state == OperatorSurvivalState.NORMAL
    assert len(reasons) == 0

    # 6. UNKNOWN never returns NORMAL
    state, reasons = resolve_operator_survival_state()
    assert state == OperatorSurvivalState.UNKNOWN
    assert "STATE_UNVERIFIED" in reasons


def test_opportunity_scanner_read_model_serialization() -> None:
    now = SystemClock().now()
    model = OpportunityScannerReadModel(
        last_scan_at=now,
        data_cutoff=now,
        funnel=FunnelCounts(universe_observed=100, fresh=95, stale=5, invalid_reference=0),
        rejections=RejectionBreakdown(liquidity=20, spread=10),
    )
    dumped = model.model_dump(mode="json")
    assert dumped["funnel"]["universe_observed"] == 100
    assert dumped["rejections"]["liquidity"] == 20
    assert dumped["rejections"]["spread"] == 10


def test_edge_ledger_entry_null_safety() -> None:
    now = SystemClock().now()
    entry = EdgeLedgerEntry(
        candidate_id="cand-001",
        timestamp=now,
        underlying="NIFTY",
        instrument="NIFTY26AUG24500CE",
        direction="CALL",
        strategy="VOL_EXPANSION",
        candidate_class=CandidateClass.HIGH_CONVICTION,
    )
    assert entry.predicted_probability is None
    assert entry.market_implied_probability is None
    assert entry.expected_net_value is None

    ledger = EdgeLedgerReadModel(
        entries=(entry,),
        as_of=now,
    )
    dumped = ledger.model_dump(mode="json")
    assert len(dumped["entries"]) == 1
    assert dumped["entries"][0]["candidate_class"] == "HIGH_CONVICTION"
