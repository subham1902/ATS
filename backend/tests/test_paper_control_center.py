from datetime import UTC, datetime
from decimal import Decimal

from ats.trading_runtime.paper_tournament import (
    LivePaperTournamentSession,
    PaperSessionConfig,
    get_paper_presets,
    run_configured_paper_session,
    save_paper_preset,
    validate_paper_session_config,
)


def test_config_validation_matrix():
    """Test validation of diverse capital, duration, strategy sets, and risk modes (Section 55)."""
    # 1. 10K session (non-blocked, warnings for sub-15K margin)
    cfg_10k = {
        "capital": 10000,
        "duration_minutes": 15,
        "selected_strategies": ["A04_PROBABILISTIC"],
        "max_concurrent_positions": 1,
        "max_trades_limit": 3,
        "instrument": "GOLDM",
        "contract": "MCX GOLDM 25SEP26",
    }
    res_10k = validate_paper_session_config(cfg_10k)
    assert res_10k["status"] in ["VALID", "WARNING"]
    assert len(res_10k["reason_codes"]) == 0

    # 2. Valid 50K multi-strategy session
    cfg_50k = {
        "capital": 50000,
        "duration_minutes": 120,
        "selected_strategies": ["A04_PROBABILISTIC", "S01_ORB_NR7", "S02_TSMOM"],
        "max_concurrent_positions": 3,
        "max_trades_limit": 15,
        "stop_loss_mode": "ATR",
        "take_profit_mode": "R_MULTIPLE",
        "trailing_stop_mode": "ATR",
    }
    res_50k = validate_paper_session_config(cfg_50k)
    assert res_50k["status"] == "VALID"
    assert len(res_50k["reason_codes"]) == 0

    # 3. Invalid capital (exceeds system safety ceiling of 10,00,000)
    cfg_excess = {
        "capital": 2500000,
        "duration_minutes": 60,
        "selected_strategies": ["A04_PROBABILISTIC"],
    }
    res_excess = validate_paper_session_config(cfg_excess)
    assert res_excess["status"] == "BLOCKED"
    assert "CAPITAL_EXCEEDS_SYSTEM_CEILING" in res_excess["reason_codes"]

    # 4. Invalid negative or zero duration
    cfg_bad_dur = {
        "capital": 30000,
        "duration_minutes": 0,
        "selected_strategies": ["A04_PROBABILISTIC"],
    }
    res_bad_dur = validate_paper_session_config(cfg_bad_dur)
    assert res_bad_dur["status"] == "BLOCKED"
    assert "DURATION_TOO_SHORT" in res_bad_dur["reason_codes"]

    # 5. Invalid empty strategies
    cfg_no_strat = {
        "capital": 30000,
        "duration_minutes": 60,
        "selected_strategies": [],
    }
    res_no_strat = validate_paper_session_config(cfg_no_strat)
    assert res_no_strat["status"] == "BLOCKED"
    assert "NO_STRATEGIES_SELECTED" in res_no_strat["reason_codes"]

    # 6. Invalid positions count (> 10)
    cfg_too_many_pos = {
        "capital": 100000,
        "duration_minutes": 60,
        "selected_strategies": ["A04_PROBABILISTIC"],
        "max_concurrent_positions": 20,
    }
    res_pos = validate_paper_session_config(cfg_too_many_pos)
    assert res_pos["status"] == "BLOCKED"
    assert "MAX_CONCURRENT_POSITIONS_EXCEEDS_CEILING" in res_pos["reason_codes"]


def test_concurrency_deterministic_evaluation():
    """Test Section 56: S01, S02, S04 generate candidates simultaneously.
    Verify candidate logging, capital governor evaluation, no oversubscription,
    margin ceiling never exceeded.
    """
    config = PaperSessionConfig(
        capital=Decimal("30000.00"),
        duration_minutes=60,
        selected_strategies=["S01_ORB_NR7", "S02_TSMOM", "S04_VOL_TARGET"],
        max_concurrent_positions=1,  # Only 1 position allowed concurrently
        max_trades_limit=10,
    )
    session = LivePaperTournamentSession(
        session_id="PT-CONC-TEST-01",
        budget=config.capital,
        config=config,
    )

    t0 = datetime(2026, 9, 24, 10, 0, 0, tzinfo=UTC)

    # Candidate A from S01
    cand_a = session.evaluate_opportunity(
        strategy_id="S01_ORB_NR7",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        price=Decimal("75000.00"),
        timestamp=t0,
        stop_offset=Decimal("100.00"),
        target_offset=Decimal("250.00"),
        expected_prob=0.65,
    )
    assert cand_a.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 1
    assert session.reserved_capital == Decimal("15000.00")  # S01 margin is 15,000
    assert session.available_capital == Decimal("15000.00")

    # Candidate B from S02 at same timestamp: margin req (16,500) > available
    # (15,000) -> blocked by CAPITAL_LIMIT
    cand_b = session.evaluate_opportunity(
        strategy_id="S02_TSMOM",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        price=Decimal("75005.00"),
        timestamp=t0,
        stop_offset=Decimal("95.00"),
        target_offset=Decimal("255.00"),
        expected_prob=0.62,
    )
    assert cand_b.candidate_status == "CAPITAL_DENIED"
    assert cand_b.rejection is not None
    assert cand_b.rejection.reason_code == "CAPITAL_LIMIT"
    assert len(session.open_positions) == 1
    assert session.reserved_capital == Decimal("15000.00")

    # Candidate C from S04 at same timestamp: margin (12,500) <= 15,000, but
    # blocked by max_concurrent_positions=1
    cand_c = session.evaluate_opportunity(
        strategy_id="S04_VOL_TARGET",
        symbol="MCX:GOLDM25SEP",
        direction="SHORT",
        price=Decimal("74990.00"),
        timestamp=t0,
        stop_offset=Decimal("100.00"),
        target_offset=Decimal("240.00"),
        expected_prob=0.60,
    )
    assert cand_c.candidate_status == "EXECUTION_DENIED"
    assert cand_c.rejection is not None
    assert cand_c.rejection.reason_code == "MAX_CONCURRENT_POSITIONS"
    assert len(session.open_positions) == 1
    assert session.reserved_capital == Decimal("15000.00")
    assert session.reserved_capital <= config.capital

    # All 3 candidates are recorded in ledger
    assert len(session.candidates_ledger) == 3


def test_multiple_concurrent_positions():
    """Test Section 57: Capital = 100,000, max concurrent positions = 3, strategies: S01, S02, S04.
    3 valid candidates -> 3 simultaneous positions.
    Closing one releases capital and leaves other two intact.
    """
    config = PaperSessionConfig(
        capital=Decimal("100000.00"),
        duration_minutes=120,
        selected_strategies=["S01_ORB_NR7", "S02_TSMOM", "S04_VOL_TARGET"],
        max_concurrent_positions=3,
        max_trades_limit=10,
        position_policy="ONE_POSITION_PER_STRATEGY",
    )
    session = LivePaperTournamentSession(
        session_id="PT-MULTI-POS-01",
        budget=config.capital,
        config=config,
    )

    t0 = datetime(2026, 9, 24, 10, 0, 0, tzinfo=UTC)

    # S01 margin: 15,000; S02 margin: 16,500; S04 margin: 12,500
    cand_1 = session.evaluate_opportunity(
        strategy_id="S01_ORB_NR7",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        price=Decimal("75000.00"),
        timestamp=t0,
        stop_offset=Decimal("100.00"),
        target_offset=Decimal("300.00"),
        expected_prob=0.65,
    )
    cand_2 = session.evaluate_opportunity(
        strategy_id="S02_TSMOM",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        price=Decimal("75010.00"),
        timestamp=t0,
        stop_offset=Decimal("100.00"),
        target_offset=Decimal("300.00"),
        expected_prob=0.65,
    )
    cand_3 = session.evaluate_opportunity(
        strategy_id="S04_VOL_TARGET",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        price=Decimal("75020.00"),
        timestamp=t0,
        stop_offset=Decimal("100.00"),
        target_offset=Decimal("300.00"),
        expected_prob=0.65,
    )

    assert cand_1.candidate_status == "EXECUTED"
    assert cand_2.candidate_status == "EXECUTED"
    assert cand_3.candidate_status == "EXECUTED"

    # Verify 3 simultaneous independent positions
    assert len(session.open_positions) == 3
    expected_reserved = Decimal("15000.00") + Decimal("16500.00") + Decimal("12500.00")  # 44,000
    assert session.reserved_capital == expected_reserved
    assert session.available_capital == Decimal("100000.00") - expected_reserved

    # Close Position 1 (S01_ORB_NR7)
    trades = list(session.open_positions.values())
    trade_1 = [t for t in trades if t.strategy_id == "S01_ORB_NR7"][0]
    trade_2 = [t for t in trades if t.strategy_id == "S02_TSMOM"][0]
    trade_3 = [t for t in trades if t.strategy_id == "S04_VOL_TARGET"][0]

    session._close_position(
        trade=trade_1,
        exit_price=Decimal("75250.00"),
        timestamp=datetime(2026, 9, 24, 10, 30, 0, tzinfo=UTC),
        reason="TAKE_PROFIT",
    )

    # Verify position 1 closed, margin released
    assert len(session.open_positions) == 2
    assert trade_1.trade_id not in session.open_positions
    assert trade_2.trade_id in session.open_positions
    assert trade_3.trade_id in session.open_positions

    # Margin reservation decreased by 15,000
    assert session.reserved_capital == expected_reserved - Decimal("15000.00")
    assert session.available_capital == (
        Decimal("100000.00") - expected_reserved
    ) + Decimal("15000.00")


def test_multiple_entry_sequence():
    """Test Section 58: max entries = 5, max concurrent positions = 2.
    Sequence: entry, entry, exit, entry, exit, entry, entry.
    Maximum concurrent positions never exceeds 2. Total entries reaches 5.
    """
    config = PaperSessionConfig(
        capital=Decimal("80000.00"),
        duration_minutes=60,
        selected_strategies=["A04_PROBABILISTIC", "S02_TSMOM"],
        max_concurrent_positions=2,
        max_trades_limit=5,
        position_policy="ALLOW_MULTIPLE",
    )
    session = LivePaperTournamentSession(
        session_id="PT-SEQ-TEST-01",
        budget=config.capital,
        config=config,
    )

    t = datetime(2026, 9, 24, 10, 0, 0, tzinfo=UTC)

    def trigger_entry(strat: str = "A04_PROBABILISTIC"):
        return session.evaluate_opportunity(
            strategy_id=strat,
            symbol="MCX:GOLDM25SEP",
            direction="LONG",
            price=Decimal("75000.00"),
            timestamp=t,
            stop_offset=Decimal("100.00"),
            target_offset=Decimal("250.00"),
            expected_prob=0.65,
        )

    # 1. Entry 1
    c1 = trigger_entry("A04_PROBABILISTIC")
    assert c1.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 1

    # 2. Entry 2
    c2 = trigger_entry("S02_TSMOM")
    assert c2.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 2

    # Max concurrent reached (2) -> Next entry blocked by concurrency gate
    c_blocked = trigger_entry("A04_PROBABILISTIC")
    assert c_blocked.candidate_status == "EXECUTION_DENIED"
    assert c_blocked.rejection.reason_code == "MAX_CONCURRENT_POSITIONS"

    # 3. Exit 1
    pos1 = list(session.open_positions.values())[0]
    session._close_position(pos1, Decimal("75100.00"), t, "TAKE_PROFIT")
    assert len(session.open_positions) == 1
    assert len(session.closed_trades) == 1

    # 4. Entry 3
    c3 = trigger_entry("A04_PROBABILISTIC")
    assert c3.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 2

    # 5. Exit 2
    pos2 = list(session.open_positions.values())[0]
    session._close_position(pos2, Decimal("75150.00"), t, "TAKE_PROFIT")
    assert len(session.open_positions) == 1
    assert len(session.closed_trades) == 2

    # 6. Entry 4
    c4 = trigger_entry("S02_TSMOM")
    assert c4.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 2

    # Exit another to make room for entry 5
    pos3 = list(session.open_positions.values())[0]
    session._close_position(pos3, Decimal("75200.00"), t, "TAKE_PROFIT")
    assert len(session.open_positions) == 1
    assert len(session.closed_trades) == 3

    # 7. Entry 5
    c5 = trigger_entry("A04_PROBABILISTIC")
    assert c5.candidate_status == "EXECUTED"
    assert len(session.open_positions) == 2

    # Total entered trades is 5 (3 closed + 2 open)
    total_entered = len(session.closed_trades) + len(session.open_positions)
    assert total_entered == 5

    # 8. Entry 6 (exceeds max_trades_limit=5) -> must be blocked
    pos_temp = list(session.open_positions.values())[0]
    session._close_position(pos_temp, Decimal("75100.00"), t, "TAKE_PROFIT")
    assert len(session.open_positions) == 1
    # Even with room for positions, trade count limit is 5
    c6 = trigger_entry("A04_PROBABILISTIC")
    assert c6.candidate_status == "EXECUTION_DENIED"
    assert c6.rejection.reason_code == "MAX_TRADES_LIMIT"


def test_preset_management_and_templates():
    """Test Section 54: Presets DEFAULT_PAPER, GOLDM_30K_CONSERVATIVE,
    GOLDM_50K_MULTI_STRATEGY, GOLDM_RESEARCH_STRESS.
    """
    presets = get_paper_presets()
    preset_ids = [p["preset_id"] for p in presets]
    assert "DEFAULT_PAPER" in preset_ids
    assert "GOLDM_30K_CONSERVATIVE" in preset_ids
    assert "GOLDM_50K_MULTI_STRATEGY" in preset_ids
    assert "GOLDM_RESEARCH_STRESS" in preset_ids

    # Save a custom preset
    custom_p = {
        "preset_id": "CUSTOM_TEST_SCALPING",
        "name": "Custom 15m Scalping (₹25K)",
        "description": "Short duration high frequency test",
        "capital": 25000.0,
        "duration_minutes": 15,
        "selected_strategies": ["A04_PROBABILISTIC"],
        "max_concurrent_positions": 1,
        "max_trades_limit": 5,
    }
    saved = save_paper_preset(custom_p)
    assert saved["preset_id"] == "CUSTOM_TEST_SCALPING"

    # Reload and verify
    reloaded = get_paper_presets()
    assert any(p["preset_id"] == "CUSTOM_TEST_SCALPING" for p in reloaded)


def test_paperbroker_invariant_and_live_safety():
    """Test Section 59 & 63: PaperBroker is sole execution target,
    LIVE_MONEY=False invariant is strictly preserved.
    """
    config = PaperSessionConfig(capital=Decimal("30000.00"))
    session = run_configured_paper_session(config)

    # Invariant checks
    assert session.live_money is False
    summary = session.get_summary()
    assert summary["live_money"] is False
    assert summary["mode"] == "A2_PAPER"

    # Zero live broker orders
    assert summary["telemetry"]["zero_broker_orders_verified"] is True
    assert summary["telemetry"]["live_money_false_verified"] is True
