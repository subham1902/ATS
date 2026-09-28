"""Tests for ATS Governance, Autonomy, and Multi-Agent Execution Workflow Router."""

import pytest
from ats.console.app import create_console_app
from ats.console.providers import LiveControlPlaneReader
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    app = create_console_app(reader=LiveControlPlaneReader())
    return TestClient(app)


def test_governance_workflow_structure_and_invariants(client: TestClient) -> None:
    """Verifies that the 7-stage workflow definition is authoritative and
    preserves LIVE_MONEY=False.
    """
    resp = client.get("/v1/governance/workflow")
    assert resp.status_code == 200
    data = resp.json()

    assert data["authority_mode"] == "A2_PAPER"
    assert data["live_money"] is False
    assert len(data["stages"]) == 7

    stage_names = [s["name"] for s in data["stages"]]
    assert "Market Ingestion & Microstructure" in stage_names[0]
    assert "Multi-Agent Alpha Generation" in stage_names[1]
    assert "Gate 1: A04 Probabilistic Filter" in stage_names[2]
    assert "Gate 2: Capital Governor" in stage_names[3]
    assert "Gate 3: Risk Governor & Circuit Breakers" in stage_names[4]
    assert "Gate 4: Autonomy Token Authority" in stage_names[5]
    assert "Simulated Execution (PaperBroker)" in stage_names[6]

    assert data["system_metrics"]["live_money_hardware_locked"] is True
    assert data["system_metrics"]["active_autonomy_level"] == "A2_PAPER"


def test_simulate_candidate_approval_and_execution(client: TestClient) -> None:
    """Tests candidate simulation where candidate passes all gates and receives
    an autonomy token.
    """
    payload = {
        "strategy_id": "ATS-S17",
        "instrument": "MCX:GOLDM26OCTFUT",
        "direction": "BUY",
        "entry_price": 74250.0,
        "target_price": 74650.0,
        "stop_loss": 74050.0,
        "expected_edge_r": 1.85,
        "calibrated_prob": 0.62,
        "margin_required": 25000.0,
        "available_capital": 100000.0,
        "max_loss_limit": 5000.0,
        "current_drawdown": 850.0,
        "current_concurrent_positions": 1,
        "max_concurrent_positions": 4,
        "autonomy_level": "A2_PAPER",
    }
    resp = client.post("/v1/governance/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_outcome"] == "APPROVED_AND_EXECUTED"
    assert data["rejection_reason"] is None
    assert len(data["stage_results"]) == 7
    for res in data["stage_results"]:
        assert res["passed"] is True
        assert res["status"] == "PASSED"

    assert data["issued_token"] is not None
    assert data["issued_token"]["scope"] == "A2_PAPER"
    assert data["issued_token"]["nonce_guarded"] is True
    assert data["execution_preview"] is not None
    assert "PaperBroker" in data["execution_preview"]["broker"]


def test_simulate_candidate_gate1_prob_rejection(client: TestClient) -> None:
    """Tests that candidate with probability below hurdle (0.52) is rejected at Gate 1."""
    payload = {
        "strategy_id": "ATS-S02",
        "instrument": "MCX:GOLDM26OCTFUT",
        "direction": "SELL",
        "entry_price": 74300.0,
        "target_price": 74100.0,
        "stop_loss": 74450.0,
        "expected_edge_r": 0.85,
        "calibrated_prob": 0.46,  # Below 0.52
        "margin_required": 25000.0,
        "available_capital": 100000.0,
        "max_loss_limit": 5000.0,
        "current_drawdown": 500.0,
        "current_concurrent_positions": 0,
        "max_concurrent_positions": 4,
    }
    resp = client.post("/v1/governance/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_outcome"] == "REJECTED_AT_PROBABILISTIC_FILTER"
    assert "failed minimum hurdle" in data["rejection_reason"]
    assert data["issued_token"] is None
    assert data["execution_preview"] is None


def test_simulate_candidate_gate2_capital_rejection(client: TestClient) -> None:
    """Tests that candidate requiring more margin than available capital is rejected at Gate 2."""
    payload = {
        "strategy_id": "ATS-S17",
        "instrument": "MCX:GOLDM26OCTFUT",
        "direction": "BUY",
        "entry_price": 74250.0,
        "target_price": 74650.0,
        "stop_loss": 74050.0,
        "expected_edge_r": 2.0,
        "calibrated_prob": 0.70,
        "margin_required": 150000.0,  # Exceeds 100k
        "available_capital": 100000.0,
        "max_loss_limit": 5000.0,
        "current_drawdown": 500.0,
        "current_concurrent_positions": 0,
        "max_concurrent_positions": 4,
    }
    resp = client.post("/v1/governance/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_outcome"] == "REJECTED_AT_CAPITAL_GOVERNOR"
    assert "exceeds available session capital" in data["rejection_reason"]
    assert data["issued_token"] is None


def test_simulate_candidate_gate3_risk_rejection(client: TestClient) -> None:
    """Tests that candidate is rejected when drawdown has breached session limit."""
    payload = {
        "strategy_id": "ATS-S17",
        "instrument": "MCX:GOLDM26OCTFUT",
        "direction": "BUY",
        "entry_price": 74250.0,
        "target_price": 74650.0,
        "stop_loss": 74050.0,
        "expected_edge_r": 1.9,
        "calibrated_prob": 0.65,
        "margin_required": 25000.0,
        "available_capital": 100000.0,
        "max_loss_limit": 5000.0,
        "current_drawdown": 5200.0,  # Breached 5000 limit
        "current_concurrent_positions": 1,
        "max_concurrent_positions": 4,
    }
    resp = client.post("/v1/governance/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall_outcome"] == "REJECTED_AT_RISK_GOVERNOR"
    assert "reached max loss circuit breaker" in data["rejection_reason"]


def test_autonomy_overview_and_tiers(client: TestClient) -> None:
    """Tests /v1/governance/autonomy overview and tier specifications."""
    resp = client.get("/v1/governance/autonomy")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_level"] == "A2_PAPER"
    assert data["live_money_invariant"] is False
    assert "PaperBroker" in data["broker_target"]
    assert len(data["tiers"]) == 6
    assert len(data["security_guarantees"]) >= 4

    active_tier = next(t for t in data["tiers"] if t["is_active"])
    assert active_tier["level"] == "A2_PAPER"
    assert active_tier["live_trading_allowed"] is False


def test_policies_candidates_advisories_endpoints(client: TestClient) -> None:
    """Tests policies, candidates, advisories list and acknowledge endpoints."""
    resp_pol = client.get("/v1/governance/policies")
    assert resp_pol.status_code == 200
    policies = resp_pol.json()
    assert len(policies) >= 3
    assert any(p["is_active"] for p in policies)

    resp_cand = client.get("/v1/governance/candidates")
    assert resp_cand.status_code == 200
    candidates = resp_cand.json()
    assert len(candidates) >= 4

    resp_adv = client.get("/v1/governance/advisories")
    assert resp_adv.status_code == 200
    advisories = resp_adv.json()
    assert len(advisories) >= 2

    # Acknowledge an advisory
    adv_id = advisories[1]["advisory_id"]
    resp_ack = client.post(f"/v1/governance/advisories/{adv_id}/acknowledge")
    assert resp_ack.status_code == 200
    assert resp_ack.json()["acknowledged"] is True
