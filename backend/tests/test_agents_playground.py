"""Unit tests for Agents Playground: 10 Agents, Dynamic Guidelines, Markets, and Upstox Trade Ledger."""

from ats.agents.config import AgentsConfigManager
from ats.agents.trade_ledger import UpstoxLiveTradeLedger
from ats.console.app import create_console_app
from fastapi.testclient import TestClient


def test_default_principals_configuration():
    """Verify that 8 agents have 1 Lac (100,000) and 2 agents have 2 Lac (200,000)."""
    cfg_mgr = AgentsConfigManager()
    configs = cfg_mgr.get_all()

    assert len(configs) == 10

    # 8 agents with 1 Lac
    lac_1_agents = [name for name, cfg in configs.items() if cfg["max_principal"] == 100_000.0]
    # 2 agents with 2 Lac (Echo and Juliet)
    lac_2_agents = [name for name, cfg in configs.items() if cfg["max_principal"] == 200_000.0]

    assert len(lac_1_agents) == 8, f"Expected 8 agents with 1 Lac, found: {lac_1_agents}"
    assert len(lac_2_agents) == 2, f"Expected 2 agents with 2 Lac, found: {lac_2_agents}"
    assert "Echo" in lac_2_agents
    assert "Juliet" in lac_2_agents


def test_dynamic_guidelines_and_principal_update():
    """Verify dynamic update of agent guidelines and principals."""
    cfg_mgr = AgentsConfigManager()

    # Update Alpha to custom guidelines
    updated = cfg_mgr.update_agent_guidelines(
        agent_name="Alpha",
        mode="CUSTOM",
        strategy_id="S01_ORB_NR7",
        max_principal=150_000.0,
        lots=2,
        direction_bias="LONG_ONLY",
        profit_target_pts=50.0,
        stop_loss_pts=25.0,
    )
    assert updated.max_principal == 150_000.0
    assert updated.mode == "CUSTOM"
    assert updated.lots == 2
    assert updated.direction_bias == "LONG_ONLY"
    assert cfg_mgr.get_principal("Alpha") == 150_000.0

    # Reset Alpha to AUTO
    reset_alpha = cfg_mgr.reset_agent_guidelines("Alpha")
    assert reset_alpha.mode == "AUTO"
    assert reset_alpha.max_principal == 100_000.0

    # Reset all back to defaults
    reset = cfg_mgr.reset_to_defaults()
    assert reset["Alpha"]["max_principal"] == 100_000.0
    assert reset["Echo"]["max_principal"] == 200_000.0
    assert reset["Juliet"]["max_principal"] == 200_000.0


def test_target_market_selection():
    """Verify playground target market setting and retrieval."""
    cfg_mgr = AgentsConfigManager()
    assert cfg_mgr.get_target_market() in {"AUTO", "MCX_GOLDM", "MCX_GOLD", "GLOBAL_XAU"}

    cfg_mgr.set_target_market("MCX_GOLDM")
    assert cfg_mgr.get_target_market() == "MCX_GOLDM"

    cfg_mgr.set_target_market("GLOBAL_XAU")
    assert cfg_mgr.get_target_market() == "GLOBAL_XAU"

    cfg_mgr.set_target_market("AUTO")
    assert cfg_mgr.get_target_market() == "AUTO"


def test_upstox_live_trade_ledger_capacity_and_lots(tmp_path):
    """Verify Upstox Trade Ledger records full lot details and enforces 1,000 capacity."""
    test_file = tmp_path / "test_ledger.json"
    ledger = UpstoxLiveTradeLedger(capacity=1000, ledger_path=test_file)

    # Record a trade with full lot details
    record = ledger.record_trade(
        agent_id="agt-alpha-1",
        agent_name="Alpha",
        strategy_id="S01_ORB_NR7",
        strategy_name="Opening Range Breakout",
        exchange="MCX",
        instrument_key="MCX_FO|569003",
        symbol="MCX:GOLDM FUT",
        direction="LONG",
        lot_size=100,  # 100g per lot
        lots=1,
        entry_price=75400.0,
        exit_price=75460.0,
        margin_utilized=45000.0,
        agent_max_principal=100000.0,
        post_trade_balance=100550.0,
        lot_unit="grams",
    )

    # Lot details verified
    assert record.lot_size == 100
    assert record.lots == 1
    assert record.total_quantity == 100
    assert record.lot_unit == "grams"

    # Gross PnL on 100g (10x quote multiplier) for 60 points = ₹600.0
    assert record.gross_pnl == 600.0

    # Upstox charges deducted
    assert record.brokerage == 40.0
    assert record.total_charges > 40.0
    assert record.net_pnl == round(600.0 - record.total_charges, 2)
    assert record.net_pnl < record.gross_pnl  # Confirms fees deducted

    # Verify buffer query
    res = ledger.get_trades(limit=10)
    assert res["total_trades"] == 1
    assert res["capacity"] == 1000
    assert len(res["trades"]) == 1
    assert res["trades"][0]["lots"] == 1
    assert res["trades"][0]["lot_size"] == 100

    # CSV export contains lot headers
    csv_out = ledger.export_csv()
    assert "lots" in csv_out
    assert "lot_size" in csv_out
    assert "total_quantity" in csv_out
    assert "MCX:GOLDM FUT" in csv_out


def test_api_agents_endpoints():
    """Verify REST API endpoints for 10 agents, market selection, and guidelines."""
    app = create_console_app()
    client = TestClient(app)

    # 1. GET /v1/agents/status
    res = client.get("/v1/agents/status")
    assert res.status_code == 200
    data = res.json()
    assert "agents" in data
    # The fleet is now four agents, one per structurally distinct family.
    assert len(data["agents"]) == 4
    assert all(a["max_principal"] == 100_000.0 for a in data["agents"].values())

    # 2. GET /v1/agents/market & PUT /v1/agents/market
    mkt_res = client.get("/v1/agents/market")
    assert mkt_res.status_code == 200
    assert "available_markets" in mkt_res.json()

    put_mkt = client.put("/v1/agents/market", json={"target_market": "MCX_GOLDM"})
    assert put_mkt.status_code == 200
    assert put_mkt.json()["target_market"] == "MCX_GOLDM"

    # Reset market back to AUTO
    client.put("/v1/agents/market", json={"target_market": "AUTO"})

    # 3. GET /v1/agents/guidelines & PUT /v1/agents/{name}/guidelines
    g_res = client.get("/v1/agents/guidelines")
    assert g_res.status_code == 200
    assert len(g_res.json()["guidelines"]) == 10

    put_g = client.put(
        "/v1/agents/Alpha/guidelines",
        json={"mode": "CUSTOM", "lots": 2, "direction_bias": "LONG_ONLY"},
    )
    assert put_g.status_code == 200
    assert put_g.json()["guidelines"]["mode"] == "CUSTOM"
    assert put_g.json()["guidelines"]["direction_bias"] == "LONG_ONLY"

    # Reset guidelines
    reset_g = client.post("/v1/agents/Alpha/guidelines/reset")
    assert reset_g.status_code == 200
    assert reset_g.json()["guidelines"]["mode"] == "AUTO"

    # 4. GET /v1/agents/upstox-trades
    trades_res = client.get("/v1/agents/upstox-trades?limit=10")
    assert trades_res.status_code == 200
    trades_data = trades_res.json()
    assert "trades" in trades_data
    assert trades_data["capacity"] == 1000

    # 5. GET /v1/agents/upstox-trades/export
    export_res = client.get("/v1/agents/upstox-trades/export")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]


def test_allowed_lot_size_ceiling():
    """Verify allowed lot ceiling configuration and runtime updates."""
    cfg_mgr = AgentsConfigManager()

    # Update allowed lot size ceiling on Bravo to 0.2
    updated = cfg_mgr.update_agent_guidelines(
        agent_name="Bravo",
        allowed_lot_size=0.2,
        max_principal=120000.0,
    )
    assert updated.allowed_lot_size == 0.2
    assert updated.max_principal == 120000.0

    app = create_console_app()
    client = TestClient(app)

    # Test API endpoint supports allowed_lot_size
    res = client.put(
        "/v1/agents/Bravo/guidelines",
        json={"allowed_lot_size": 0.1, "max_principal": 90000.0},
    )
    assert res.status_code == 200
    assert res.json()["guidelines"]["allowed_lot_size"] == 0.1

    # Reset Bravo
    client.post("/v1/agents/Bravo/guidelines/reset")


def test_history_wipe_and_fresh_start():
    """Verify POST /v1/agents/history/reset and POST /v1/agents/reset wipe all metrics cleanly to 0 for fresh start."""
    app = create_console_app()
    client = TestClient(app)

    # Trigger reset via /v1/agents/reset
    res = client.post("/v1/agents/reset")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "fresh" in data["message"].lower()

    # Status check: all 10 agents must have 0 trades, 0 P&L, 0 win rate, 0 margins, and cleared positions
    status_res = client.get("/v1/agents/status")
    assert status_res.status_code == 200
    status_data = status_res.json()

    for name, agent in status_data["agents"].items():
        assert len(agent["history"]) == 0, f"Agent {name} should have 0 history items"
        assert agent["pnl"] == 0.0, f"Agent {name} PnL should be 0.0"
        assert agent["win_rate"] == 0.0, f"Agent {name} win_rate should be 0.0"
        assert agent["total_tests"] == 0, f"Agent {name} total_tests should be 0"
        assert agent["winning_tests"] == 0, f"Agent {name} winning_tests should be 0"
        assert agent["allocated_margin"] == 0.0, f"Agent {name} allocated_margin should be 0.0"
        assert agent["strategy_retests"] == 0, f"Agent {name} strategy_retests should be 0"
        assert agent["strategy_net_pnl"] == 0.0, f"Agent {name} strategy_net_pnl should be 0.0"
        assert agent["strategy_wins"] == 0, f"Agent {name} strategy_wins should be 0"
        assert agent["strategy_losses"] == 0, f"Agent {name} strategy_losses should be 0"
        assert agent["net_pnl_increment"] == 0.0, f"Agent {name} net_pnl_increment should be 0.0"
        assert agent["goal_progress_pct"] == 0.0, f"Agent {name} goal_progress_pct should be 0.0"
        assert agent["position"] is None, f"Agent {name} position should be None"

    # Delta must be active with S17
    assert status_data["agents"]["Delta"]["guidelines"]["strategy_id"] == "S17_OI_VOLUME_MACHINE"

    # Test single agent reset endpoint
    single_res = client.post("/v1/agents/Alpha/reset")
    assert single_res.status_code == 200
    assert single_res.json()["status"] == "success"


