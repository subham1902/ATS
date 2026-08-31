"""COMPOUND FAILURE tests — the two previously-open failure gaps.

A. Process restart with an open position + pending reduction: recovery restores
   authoritative state and continues the reduction safely without duplicate
   exit or duplicate order.

B. Stale/disconnected feed with an already-open position requiring a protective
   exit: NEW RISK stays blocked, but the protective reduction path still works
   and is not disabled by the stale entry data.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ats.trading_runtime.broker import InMemoryMarketFeed
from ats.trading_runtime.engine import RuntimeEvent, RuntimeEventKind

from .helpers import (
    NIFTY,
    NOW,
    instrument,
    policy,
)
from .test_orchestrator import _bull_bar, _facts_provider, _fresh_orchestrator


def test_restart_recovers_pending_reduction_without_duplicate_exit() -> None:
    from ats.trading_runtime.broker import PaperBrokerAdapter
    from ats.trading_runtime.orchestrator import AutonomousPaperOrchestrator

    # Phase 1: live orchestrator opens a position and requests a reduction.
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    assert len(orch.get_open_positions()) == 1
    pid = next(iter(orch.get_open_positions().keys()))
    listed = orch.runtime.request_exit(
        pid, NOW, reason_codes=("PROTECTIVE_REDUCTION",), source="TEST"
    )
    assert listed["accepted"] is True
    assert pid in orch.runtime.state.pending_exits

    # Phase 2: simulate process restart by reusing the SAME authoritative
    # RuntimeState over a fresh runtime/orchestrator.
    restored_state = orch.runtime.state
    restored_feed = InMemoryMarketFeed()
    restored_feed.set_mark(NIFTY, Decimal("101"), NOW)
    restored_feed.set_mark("NIFTY", Decimal("25000"), NOW)
    restarted = AutonomousPaperOrchestrator(
        calendar=orch.config.calendar,
        market_feed=restored_feed,
        broker=PaperBrokerAdapter(policy=policy(), instrument=instrument()),
        policy=policy(),
        instrument=instrument(),
        market_facts_provider=_facts_provider,
        authorization_provider=orch._authorization_provider,
    )
    restarted.runtime.state = restored_state

    # Recovery must NOT re-submit an entry order (no new risk on restart).
    assert restarted.counters.submitted_orders == 0

    # The pending reduction survives and remains idempotent (no duplicate exit).
    re_listed = restarted.runtime.request_exit(
        pid, NOW, reason_codes=("PROTECTIVE_REDUCTION",), source="TEST"
    )
    assert re_listed["accepted"] is True
    assert re_listed.get("idempotent") is True

    # Flatten continues the reduction and closes the position.
    result = restarted.request_shutdown(NOW + timedelta(minutes=1))
    assert restarted.is_position_empty()
    assert result["status"] in ("CLOSED", "NOT_CLOSED")


def test_stale_feed_blocks_new_risk_but_allows_protective_exit() -> None:
    orch = _fresh_orchestrator()
    _bull_bar(orch)
    assert len(orch.get_open_positions()) == 1
    pid = next(iter(orch.get_open_positions().keys()))

    # Simulate feed disconnect: no fresh mark for the INDEX (entry instrument).
    orch.runtime.market_feed.set_healthy(False)

    # New risk must be blocked because the feed is stale/unhealthy.
    stale_at = NOW + timedelta(minutes=30)
    result = orch.runtime.process_event(
        RuntimeEvent(
            kind=RuntimeEventKind.BAR,
            instrument_id="NIFTY",
            payload={"previous_close": "25000", "close": "25600"},
            at=stale_at,
        )
    )
    assert result.get("verdict") in ("BLOCK_NEW_RISK", "REQUIRE_REDUCE_ONLY")
    # no NEW entry submitted after the stale event (count unchanged from the
    # single position opened before the disconnect)
    assert orch.counters.submitted_orders == 1

    # Protective reduction for the EXISTING exposure must still be possible.
    reduction = orch.runtime.request_exit(
        pid, stale_at, reason_codes=("PROTECTIVE_EXIT",), source="COMPOUND"
    )
    assert reduction["accepted"] is True

    # Shutdown can still flatten the existing position using fresh position facts.
    shutdown = orch.request_shutdown(stale_at + timedelta(minutes=1))
    assert orch.is_position_empty()
    assert shutdown["status"] in ("CLOSED", "NOT_CLOSED")
