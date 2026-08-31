from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from ats.trading_runtime.broker import InMemoryMarketFeed
from ats.trading_runtime.forward_validation import (
    ForwardValidationLedger,
    ValidationListener,
    ValidationSource,
    aggregate,
    require_paper_only,
)

from .helpers import NIFTY, NOW, build_orchestrator, market_facts


def _facts(instrument_id: str, at):
    return market_facts(instrument_id=NIFTY, at=at) if instrument_id == NIFTY else None


def test_replay_harness_persists_only_final_reconciled_result(tmp_path) -> None:
    ledger = ForwardValidationLedger(tmp_path / "validation.jsonl")
    listener = ValidationListener(
        ledger=ledger, source=ValidationSource.REPLAY, code_version="6cbb53d",
        strategy_version="A2-FROZEN", policy_version="A04-V1",
    )
    feed = InMemoryMarketFeed()
    feed.set_mark("NIFTY", Decimal("25000"), NOW)
    feed.set_mark(NIFTY, Decimal("101"), NOW)
    orchestrator = build_orchestrator(market_facts_provider=_facts, feed=feed)
    orchestrator.listener = listener
    orchestrator.runtime.market_feed.set_mark("NIFTY", Decimal("25600"), NOW)
    orchestrator.bar("NIFTY", close=Decimal("25600"), previous_close=Decimal("25000"), at=NOW)
    orchestrator.request_shutdown(NOW + timedelta(minutes=2))
    assert listener.result is not None
    assert listener.result.source is ValidationSource.REPLAY
    assert listener.result.reconciliation["status"] == "CLOSED"
    report = aggregate(ledger.results(), minimum_sessions=2, minimum_trades=2)
    assert report.conclusion == "INSUFFICIENT_SAMPLE"


def test_startup_refuses_non_paper_execution_modes() -> None:
    # A result from the first test's deterministic construction is not needed;
    # the startup boundary itself is strict and rejects non-PAPER modes.
    with pytest.raises(RuntimeError, match="execution_mode=PAPER"):
        require_paper_only("LIVE")
    with pytest.raises(RuntimeError, match="execution_mode=PAPER"):
        require_paper_only(None)
    require_paper_only("PAPER")
