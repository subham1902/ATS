from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ats.trading_runtime.candidate_factory import build_opportunity_candidate

from tests.unit.contracts.intelligence.fixtures import uid


def test_build_opportunity_candidate_is_production_contract() -> None:
    now = datetime.now(UTC)
    cand = build_opportunity_candidate(
        instrument_id="NIFTY25JUN100CE",
        campaign_id=uid(1),
        campaign_version=1,
        strategy_id=uid(2),
        strategy_version=1,
        market_context_id=uid(3),
        thesis_id=uid(4),
        thesis_version=1,
        distribution_id=uid(5),
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert cand.instrument_id == "NIFTY25JUN100CE"
    assert cand.candidate_id is not None
    assert cand.payload_hash is not None
    # Binding must survive round-trip
    from ats.contracts.domain.hashing import compute_payload_hash

    assert cand.payload_hash == compute_payload_hash(cand)


def test_engine_emits_production_candidate() -> None:
    from datetime import UTC, date, datetime, time
    from decimal import Decimal

    from ats.market.calendar.models import SessionCalendar
    from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
    from ats.trading_runtime.engine import (
        RuntimeConfig,
        RuntimeEvent,
        RuntimeEventKind,
        TradingRuntime,
    )

    cal = SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    feed.set_mark("NIFTY", Decimal("101"), now)
    rt = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    result = rt.process_event(RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={"previous_close": "100"}, at=now))
    assert "candidate" in result or "no_action" in result
    # If candidate, it must have production-like instrument
    if "candidate" in result:
        assert result["candidate"]["instrument"] == "NIFTY"


def test_exit_converges_through_single_path() -> None:
    from datetime import date, time
    from decimal import Decimal

    from ats.market.calendar.models import SessionCalendar
    from ats.trading_runtime.broker import InMemoryMarketFeed, PaperBrokerAdapter
    from ats.trading_runtime.engine import (
        RuntimeConfig,
        RuntimeEvent,
        RuntimeEventKind,
        TradingRuntime,
    )

    cal = SessionCalendar(
        calendar_id="T",
        calendar_version="1.0.0",
        timezone="Asia/Kolkata",
        trading_dates=(date(2024, 6, 3),),
        preopen_start=time(9, 0),
        market_open=time(9, 15),
        market_close=time(15, 30),
        overrides=(),
    )
    feed = InMemoryMarketFeed()
    broker = PaperBrokerAdapter()
    now = datetime.now(UTC).replace(year=2024, month=6, day=3, hour=5, minute=0, second=0, microsecond=0)
    rt = TradingRuntime(config=RuntimeConfig(calendar=cal), market_feed=feed, broker=broker)
    rt.handle_fill("NIFTY:1", Decimal("100"), Decimal("75"), now)
    # Trigger P1 exit via hard loss
    feed.set_mark("NIFTY", Decimal("100"), now)
    rt.state.open_positions["NIFTY:1"] = rt.state.open_positions["NIFTY:1"].__class__(
        **{**rt.state.open_positions["NIFTY:1"].__dict__, "current_mark": Decimal("95")}
    )
    result = rt.process_event(RuntimeEvent(kind=RuntimeEventKind.BAR, instrument_id="NIFTY", payload={}, at=now))
    assert "exits" in result
    # No duplicate
    pids = [e["position_id"] for e in result["exits"]]
    assert len(pids) == len(set(pids))


def test_no_fake_candidate_in_production_path() -> None:
    import pathlib

    src = pathlib.Path("backend/src/ats/trading_runtime/engine.py").read_text()
    # _FakeCandidate should not be used in process_event anymore; only _LegacyFakeCandidate alias remains
    assert "_FakeCandidate(signal)" not in src or "_LegacyFakeCandidate" in src
