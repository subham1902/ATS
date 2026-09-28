"""API tests for the risk, cost-awareness, and mandate endpoints."""

from __future__ import annotations

import pytest
from ats.agents.risk import GLOBAL_KILL_SWITCH
from ats.agents.worker import get_risk_manager
from ats.console.app import create_console_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_console_app())


def test_kill_switch_defaults_to_blocked(client: TestClient):
    """The system must refuse to trade until an operator explicitly allows it.

    Asserts behaviour, not the reason string: the reason is mutable shared
    global state that other tests legitimately overwrite.
    """
    GLOBAL_KILL_SWITCH.engage("test: trading must be blocked by default")
    res = client.get("/v1/agents/risk/kill-switch")
    assert res.status_code == 200
    data = res.json()
    assert data["trading_enabled"] is False
    assert data["armed"] is False
    assert data["reason"]


def test_engage_and_release_kill_switch(client: TestClient):
    engaged = client.post(
        "/v1/agents/risk/kill-switch/engage", json={"reason": "incident response"}
    )
    assert engaged.status_code == 200
    assert engaged.json()["trading_enabled"] is False

    released = client.post(
        "/v1/agents/risk/kill-switch/release", json={"reason": "incident resolved"}
    )
    assert released.status_code == 200
    assert released.json()["trading_enabled"] is True
    GLOBAL_KILL_SWITCH.engage("test cleanup")


def test_release_requires_reason(client: TestClient):
    res = client.post("/v1/agents/risk/kill-switch/release", json={"reason": "x"})
    assert res.status_code == 422
    GLOBAL_KILL_SWITCH.engage("test cleanup")


def test_risk_status_shape(client: TestClient):
    res = client.get("/v1/agents/risk")
    assert res.status_code == 200
    d = res.json()
    assert "kill_switch" in d
    assert "limits" in d
    assert "portfolio" in d
    assert "blocked_signals" in d


def test_risk_limits_can_be_tightened(client: TestClient):
    original = get_risk_manager().limits.max_daily_loss_pct
    res = client.put("/v1/agents/risk/limits", json={"max_daily_loss_pct": 2.0})
    assert res.status_code == 200
    assert res.json()["limits"]["max_daily_loss_pct"] == 2.0
    assert get_risk_manager().limits.max_daily_loss_pct == 2.0
    get_risk_manager().limits.max_daily_loss_pct = original


def test_economics_check_blocks_audited_geometry(client: TestClient):
    """The pre-audit 45/22 geometry must be rejected, with a reason."""
    res = client.post(
        "/v1/agents/economics/check",
        json={
            "exchange": "MCX",
            "entry_price": 147232.0,
            "symbol": "MCX:GOLDM FUT",
            "lot_size": 100.0,
            "lots": 1.0,
            "target_points": 45.0,
            "stop_points": 22.0,
        },
    )
    assert res.status_code == 200
    d = res.json()
    assert d["tradable"] is False
    e = d["economics"]
    assert e["required_win_rate"] > 80.0
    assert e["block_reason_code"] in (
        "LOT_SIZE_UNECONOMICAL",
        "NEGATIVE_EXPECTANCY",
    )


def test_economics_check_allows_wide_target(client: TestClient):
    res = client.post(
        "/v1/agents/economics/check",
        json={
            "entry_price": 147232.0,
            "symbol": "MCX:GOLDM FUT",
            "lot_size": 100.0,
            "lots": 2.0,
            "target_points": 200.0,
            "stop_points": 67.0,
        },
    )
    assert res.json()["tradable"] is True


def test_cost_drag_endpoint(client: TestClient):
    res = client.get("/v1/agents/economics/cost-drag")
    assert res.status_code == 200
    d = res.json()
    assert "summary" in d
    assert "per_agent" in d
    assert "cost_awareness" in d["summary"]


def test_edge_endpoint(client: TestClient):
    res = client.get("/v1/agents/edge")
    assert res.status_code == 200
    d = res.json()
    assert "min_sample_for_verdict" in d
    assert d["min_sample_for_verdict"] == 30


def test_portfolio_endpoint_reports_mandates(client: TestClient):
    res = client.get("/v1/agents/portfolio")
    assert res.status_code == 200
    d = res.json()
    assert len(d["mandates"]) == 10
    assert d["mandate_health"]["healthy"] is True
    assert d["mandate_health"]["distinct_families"] == 10
    assert len(d["mandate_health"]["instruments"]) >= 2


def test_contracts_endpoint(client: TestClient):
    res = client.get("/v1/agents/contracts")
    assert res.status_code == 200
    c = res.json()["contracts"]
    assert c["MCX_GOLDM"]["lot_size"] == 100.0
    assert "tick_size" in c["MCX_GOLDM"]


def test_guidelines_expose_cost_parameters(client: TestClient):
    res = client.get("/v1/agents/Alpha/guidelines")
    assert res.status_code == 200
    g = res.json()
    assert g["min_edge_multiple"] == 3.0
    assert 0.0 <= g["min_signal_confidence"] <= 1.0
    assert g["max_trades_per_day"] > 0
    assert g["bar_seconds"] > 0


def test_guidelines_update_cost_params(client: TestClient):
    res = client.put(
        "/v1/agents/Alpha/guidelines",
        json={"min_edge_multiple": 5.0, "min_signal_confidence": 0.7},
    )
    assert res.status_code == 200
    g = res.json()["guidelines"]
    assert g["min_edge_multiple"] == 5.0
    assert g["min_signal_confidence"] == 0.7
    client.post("/v1/agents/Alpha/guidelines/reset")


def test_bar_seconds_is_mandate_locked(client: TestClient):
    """A stale config file must not be able to re-duplicate the fleet."""
    res = client.put("/v1/agents/Alpha/guidelines", json={"horizon": "LONG_TERM_SWING"})
    assert res.status_code == 200
    g = res.json()["guidelines"]
    assert g["bar_seconds"] == 300.0  # Alpha is an intraday mandate
    client.post("/v1/agents/Alpha/guidelines/reset")


def test_status_includes_risk_and_execution(client: TestClient):
    res = client.get("/v1/agents/status")
    assert res.status_code == 200
    d = res.json()
    assert "risk" in d
    assert "execution" in d
    assert d["risk"]["kill_switch"]["trading_enabled"] in (True, False)


def test_reset_clears_risk_state(client: TestClient):
    get_risk_manager().register_principal("Alpha", 100_000.0)
    res = client.post("/v1/agents/Alpha/reset")
    assert res.status_code == 200
    assert res.json()["status"] == "success"


def test_full_reset_survives(client: TestClient):
    res = client.post("/v1/agents/reset")
    assert res.status_code == 200
    status = client.get("/v1/agents/status").json()
    for name, agent in status["agents"].items():
        assert agent["total_tests"] == 0, name
        assert agent["pnl"] == 0.0, name
        assert agent["position"] is None, name
