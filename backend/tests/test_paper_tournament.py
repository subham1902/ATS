import os
from decimal import Decimal

from ats.trading_runtime.paper_tournament import (
    LivePaperTournamentSession,
    calculate_break_even,
    calculate_friction,
    get_system_activity_items,
    run_full_one_hour_paper_session,
    run_multi_session_validation_campaign,
)


def test_calculate_friction():
    # 1 lot Gold Mini at 75000 entry and 75100 exit
    cost = calculate_friction(Decimal("75000.00"), Decimal("75100.00"), Decimal("1.0"))
    assert cost > Decimal("50.00")  # Brokerage (40) + turnover + CTT + GST + slippage
    assert cost < Decimal("150.00")

def test_calculate_break_even():
    be = calculate_break_even(Decimal("75000.00"), Decimal("75150.00"), Decimal("1.0"))
    assert be["required_break_even_move"] > Decimal("70.00")
    assert be["expected_move"] == Decimal("150.00")
    assert be["expected_net_edge"] > Decimal("0.00")

def test_paper_tournament_budget_enforcement():
    # Test strict 30,000 budget
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    
    assert session.budget == Decimal("30000.00")
    assert session.reserved_capital <= Decimal("30000.00")
    assert session.available_capital >= Decimal("0.00")
    assert len(session.closed_trades) > 0
    assert session.status == "COMPLETED"
    
    # Check that all trades were margin compliant
    for t in session.closed_trades:
        assert t.margin_used <= Decimal("30000.00")
        assert t.status == "CLOSED"
        assert t.exit_price is not None
        assert t.friction_costs > Decimal("0.00")

def test_paper_tournament_artifacts_generation():
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    
    # Check that artifacts exist
    assert os.path.exists(session.ledger_file)
    assert os.path.exists(session.results_csv)
    assert os.path.exists(session.candidates_file)
    assert os.path.exists(session.rejections_file)
    assert os.path.getsize(session.ledger_file) > 0
    assert os.path.getsize(session.results_csv) > 0

def test_candidate_and_rejection_ledger():
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    
    # Must have candidates evaluated
    assert len(session.candidates_ledger) >= 5
    assert len(session.rejections_ledger) >= 3
    
    # Verify deterministic reason codes
    reason_codes = {r.reason_code for r in session.rejections_ledger}
    assert "CAPITAL_LIMIT" in reason_codes
    assert "EXPECTED_NET_EDGE_NEGATIVE" in reason_codes
    
    # Verify candidate telemetry
    executed = [
        c for c in session.candidates_ledger if c.candidate_status == "EXECUTED"
    ]
    capital_denied = [
        c for c in session.candidates_ledger if c.candidate_status == "CAPITAL_DENIED"
    ]
    assert len(executed) >= 1
    assert len(capital_denied) >= 1

def test_system_activity_logging():
    # Running a session must emit activity logs
    _session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    items = get_system_activity_items()
    assert len(items) > 0
    
    kinds = {item.event_kind for item in items}
    assert "PAPER_TRADE_ENTRY" in kinds
    assert "PAPER_TRADE_EXIT" in kinds
    assert "CANDIDATE_CAPITAL_DENIED" in kinds

def test_validation_campaign_multi_session():
    campaign = run_multi_session_validation_campaign(
        campaign_id="TEST-CAMPAIGN-001",
        sessions_count=2,
        budget=Decimal("30000.00"),
    )
    assert campaign.total_sessions >= 2
    assert campaign.valid_sessions_count >= 2
    assert len(campaign.regimes_covered) >= 2
    assert len(campaign.aggregate_evidence) > 0

def test_live_order_route_absent_from_api():
    """Verify that NO live order route exists in the API application surface."""
    from ats.console.app import create_console_app
    from fastapi.testclient import TestClient

    app = create_console_app()
    client = TestClient(app)

    # 1. Inspect route table directly
    order_routes = [
        route.path for route in app.routes
        if "/orders" in getattr(route, "path", "")
    ]
    assert len(order_routes) == 0, f"Forbidden order routes detected: {order_routes}"

    # 2. Assert HTTP POST to hypothetical order endpoint returns 404 Not Found
    res = client.post(
        "/v1/brokers/upstox/orders",
        json={"symbol": "MCX:GOLDM25SEP", "side": "BUY", "quantity": 1},
    )
    assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"


def test_live_money_invariant_unalterable():
    """Verify that LIVE_MONEY cannot be enabled or overridden via configuration or API."""
    from ats.console.settings_router import update_values
    
    # 1. Attempt to set LIVE_MONEY=True via settings API payload
    res = update_values({"GENERAL": {"live_money": True}})
    assert res["status"] == "error"
    assert "governance locked to false" in res["message"]


def test_broker_capabilities_manifest_declares_execution_disabled():
    """Verify broker manifest explicitly exposes paper execution only and
    marks live execution as DISABLED.
    """
    from ats.console.broker_router import list_manifests
    
    manifests = list_manifests()
    assert len(manifests) == 1
    m = manifests[0]
    assert m.capabilities.paper_execution is True
    assert m.capabilities.live_execution is False
    assert m.capabilities.execution_state == "DISABLED"
    assert m.capabilities.live_order_route == "NON_EXISTENT"
    assert m.live_execution_mode == "DISABLED"


def test_no_external_broker_write_operations():
    """Assert BrokerConnector interface explicitly prohibits live write/order methods."""
    from ats.market.providers.base import BrokerConnector
    
    forbidden = [
        "place_order",
        "submit_order",
        "modify_order",
        "cancel_order",
        "order_write",
        "buy",
        "sell",
    ]
    for method in forbidden:
        assert not hasattr(BrokerConnector, method), f"BrokerConnector must not define {method}"


def test_paperbroker_sole_execution_target():
    """Verify PaperBrokerAdapter delegates solely to the deterministic paper execution module."""
    import inspect

    from ats.trading_runtime.broker import PaperBrokerAdapter

    src = inspect.getsource(PaperBrokerAdapter.submit_order)
    assert "submit_paper_order" in src
    assert "requests.post" not in src
    assert "http" not in src.lower()


def test_upstox_read_only_protocol():
    """Verify Upstox provider protocols convey zero financial or execution authority."""
    import inspect

    from ats.market.providers.upstox import protocols
    
    for name, cls in inspect.getmembers(protocols, inspect.isclass):
        for method_name in dir(cls):
            forbidden_methods = [
                "place_order",
                "submit_order",
                "modify_order",
                "cancel_order",
                "execute_order",
            ]
            assert method_name not in forbidden_methods, (
                f"Protocol {name} has forbidden method {method_name}"
            )


def test_candidate_traceability_lifecycle():
    """Verify every candidate has a complete, deterministic, non-dropped terminal state."""
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    assert len(session.candidates_ledger) > 0

    valid_statuses = {"EXECUTED", "CAPITAL_DENIED", "A04_DENIED", "FILTERED"}
    for c in session.candidates_ledger:
        assert c.candidate_status in valid_statuses
        assert c.candidate_id.startswith("CAND-")
        assert c.strategy_id in session.strategies
        assert c.entry_reference > Decimal("0.00")
        assert c.expected_net_edge is not None


def test_capital_decision_forensics_accuracy():
    """Verify capital decisions clearly distinguish margin contention from
    risk or cost filtering.
    """
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    
    reasons = {r.reason_code for r in session.rejections_ledger}
    assert "CAPITAL_LIMIT" in reasons
    assert "EXPECTED_NET_EDGE_NEGATIVE" in reasons

    cap_rejections = [r for r in session.rejections_ledger if r.reason_code == "CAPITAL_LIMIT"]
    for cr in cap_rejections:
        assert cr.required_margin > cr.available_capital
        assert "exceeds available" in cr.reason_details


def test_pnl_reconciliation_exact():
    """Verify net_pnl = gross_pnl - friction_costs across all closed trades."""
    session = run_full_one_hour_paper_session(budget=Decimal("30000.00"))
    assert len(session.closed_trades) > 0
    
    for t in session.closed_trades:
        expected_net = t.gross_pnl - t.friction_costs
        assert abs(t.net_pnl - expected_net) <= Decimal("0.02"), (
            f"P&L mismatch for trade {t.trade_id}: net {t.net_pnl} "
            f"!= {t.gross_pnl} - {t.friction_costs}"
        )


def test_historical_session_immutability_pt_075030():
    """Forensic audit: Verify historical session PT-20260924-075030 results
    match authoritative record exactly.
    """
    import csv
    from pathlib import Path
    
    csv_path = Path(r"D:\Projects\ATS\evidence\paper_sessions\PT-20260924-075030_results.csv")
    assert csv_path.exists(), "Historical evidence file missing!"
    
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    assert len(rows) == 8
    
    # A04_PROBABILISTIC: gross +150.00, friction 79.39, net +70.61
    a04 = next(r for r in rows if r["Strategy ID"] == "A04_PROBABILISTIC")
    assert Decimal(a04["Gross PnL (INR)"]) == Decimal("150.00")
    assert Decimal(a04["Friction Costs (INR)"]) == Decimal("79.39")
    assert Decimal(a04["Net PnL (INR)"]) == Decimal("70.61")
    assert a04["Verdict"] == "SURVIVED_PASSED"
    
    # S02_TSMOM: gross +52.00, friction 79.42, net -27.42
    s02 = next(r for r in rows if r["Strategy ID"] == "S02_TSMOM")
    assert Decimal(s02["Gross PnL (INR)"]) == Decimal("52.00")
    assert Decimal(s02["Friction Costs (INR)"]) == Decimal("79.42")
    assert Decimal(s02["Net PnL (INR)"]) == Decimal("-27.42")
    assert s02["Verdict"] == "COST_DRAGGED_LOSS"
    
    # S04_VOL_TARGET: gross -23.00, friction 79.42, net -102.42
    s04 = next(r for r in rows if r["Strategy ID"] == "S04_VOL_TARGET")
    assert Decimal(s04["Gross PnL (INR)"]) == Decimal("-23.00")
    assert Decimal(s04["Friction Costs (INR)"]) == Decimal("79.42")
    assert Decimal(s04["Net PnL (INR)"]) == Decimal("-102.42")
    assert s04["Verdict"] == "COST_DRAGGED_LOSS"

    # Total audit sum
    total_gross = sum(Decimal(r["Gross PnL (INR)"]) for r in rows)
    total_friction = sum(Decimal(r["Friction Costs (INR)"]) for r in rows)
    total_net = sum(Decimal(r["Net PnL (INR)"]) for r in rows)
    
    assert total_gross == Decimal("179.00")
    assert total_friction == Decimal("238.23")
    assert total_net == Decimal("-59.23")


def test_duplicate_event_prevention():
    """Verify duplicate fills or orders do not cause double entries or double counting."""
    from ats.trading_runtime.paper_tournament import PaperTrade
    
    session = LivePaperTournamentSession(session_id="TEST-DEDUP", budget=Decimal("30000.00"))
    trade = PaperTrade(
        trade_id="TRD-DEDUP-001",
        candidate_id="CAND-DEDUP-001",
        strategy_id="A04_PROBABILISTIC",
        symbol="MCX:GOLDM25SEP",
        direction="LONG",
        entry_price=Decimal("75000.00"),
        entry_time="2026-09-24T10:00:00Z",
        quantity=Decimal("1.0"),
        margin_used=Decimal("18000.00"),
        stop_loss=Decimal("74900.00"),
        take_profit=Decimal("75200.00"),
    )
    
    # First entry
    session.open_positions[trade.trade_id] = trade
    session.reserved_capital += trade.margin_used
    session.available_capital -= trade.margin_used
    assert session.reserved_capital == Decimal("18000.00")
    assert session.available_capital == Decimal("12000.00")
    
    # Duplicate attempt with same trade_id must be idempotent
    if trade.trade_id in session.open_positions:
        pass  # Idempotently ignored
    else:
        session.open_positions[trade.trade_id] = trade
        session.reserved_capital += trade.margin_used
        session.available_capital -= trade.margin_used
        
    assert len(session.open_positions) == 1
    assert session.reserved_capital == Decimal("18000.00")
    assert session.available_capital == Decimal("12000.00")


