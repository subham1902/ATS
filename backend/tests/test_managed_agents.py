"""Managed research agents: CRUD, versioning, retention, and authority boundary.

Uses an isolated store file per module so no test touches the real
``data/agents/managed.json``.
"""

import pytest
from ats.agents import managed as managed_domain
from ats.agents.managed_router import reset_managed_store
from ats.console.app import create_console_app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reset_managed_store(path=tmp_path / "managed.json")
    yield TestClient(create_console_app())
    reset_managed_store()


def _create(client, **overrides):
    body = {
        "name": "Researcher One",
        "description": "Regime research",
        "agent_type": "RESEARCH",
        "provider": "acme",
        "model": "acme-large",
        "system_instructions": "Analyze, never execute.",
        "capabilities": ["READ_MARKET_DATA", "RUN_RESEARCH", "GENERATE_REPORT"],
        "data_scopes": ["MARKET_DATA", "HISTORICAL_DATA"],
        "research_scopes": ["REGIME"],
        "timeout_s": 300,
        "max_concurrency": 2,
        "credential_ref": "ACME_API_KEY",
    }
    body.update(overrides)
    return client.post("/v1/agents/managed", json=body)


def test_create_defaults_to_disabled(client):
    res = _create(client)
    assert res.status_code == 201, res.text
    agent = res.json()["agent"]
    assert agent["enabled"] is False
    assert agent["status"] == "DISABLED"
    assert agent["current_config_version"] == 1
    assert agent["agent_id"]


def test_duplicate_name_rejected(client):
    assert _create(client).status_code == 201
    res = _create(client)
    assert res.status_code == 409


def test_invalid_agent_type_rejected(client):
    res = _create(client, agent_type="TRADER")
    assert res.status_code == 422


def test_forbidden_capability_rejected(client):
    res = _create(client, capabilities=["READ_MARKET_DATA", "SUBMIT_ORDER"])
    assert res.status_code == 422
    assert "SUBMIT_ORDER" in res.text


def test_secret_value_as_credential_ref_rejected(client):
    res = _create(client, credential_ref="sk-live-abc123")
    assert res.status_code == 422


def test_responses_carry_reference_not_secret(client):
    res = _create(client, credential_ref="ACME_API_KEY")
    assert res.status_code == 201
    assert res.json()["agent"]["credential_ref"] == "ACME_API_KEY"


def test_get_and_list(client):
    created = _create(client, name="Listable").json()["agent"]
    assert client.get(f"/v1/agents/managed/{created['agent_id']}").status_code == 200
    assert client.get("/v1/agents/managed/nope").status_code == 404
    body = client.get("/v1/agents/managed").json()
    assert [a["name"] for a in body["agents"]] == ["Listable"]


def test_edit_appends_version_and_keeps_history(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    res = client.patch(f"/v1/agents/managed/{agent_id}", json={"model": "acme-xl"})
    assert res.status_code == 200
    assert res.json()["agent"]["current_config_version"] == 2
    versions = client.get(f"/v1/agents/managed/{agent_id}/versions").json()["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["snapshot"]["model"] == "acme-large"
    assert versions[1]["snapshot"]["model"] == "acme-xl"
    assert versions[1]["reason"] == "edited"


def test_noop_edit_does_not_bump_version(client):
    agent_id = _create(client, model="acme-xl").json()["agent"]["agent_id"]
    res = client.patch(f"/v1/agents/managed/{agent_id}", json={"model": "acme-xl"})
    assert res.json()["agent"]["current_config_version"] == 1


def test_edit_archived_refused(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    client.delete(f"/v1/agents/managed/{agent_id}")
    res = client.patch(f"/v1/agents/managed/{agent_id}", json={"model": "x"})
    assert res.status_code == 422


def test_enable_disable_run_lifecycle(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    # Disabled agents cannot start new work.
    assert client.post(f"/v1/agents/managed/{agent_id}/runs").status_code == 422
    assert client.post(f"/v1/agents/managed/{agent_id}/enable").json()["agent"]["status"] == "IDLE"
    run = client.post(f"/v1/agents/managed/{agent_id}/runs").json()["run"]
    assert run["status"] == "STARTED"
    assert run["config_version"] == 1
    finished = client.post(
        f"/v1/agents/managed/runs/{run['run_id']}/finish", json={"ok": True}
    ).json()["run"]
    assert finished["status"] == "COMPLETED"
    disabled = client.post(f"/v1/agents/managed/{agent_id}/disable").json()["agent"]
    assert disabled["status"] == "DISABLED"
    # Disabling stops new starts; finishing an in-flight run still works.
    assert client.post(f"/v1/agents/managed/{agent_id}/runs").status_code == 422


def test_failed_run_records_error_and_status(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    client.post(f"/v1/agents/managed/{agent_id}/enable")
    run_id = client.post(f"/v1/agents/managed/{agent_id}/runs").json()["run"]["run_id"]
    finished = client.post(
        f"/v1/agents/managed/runs/{run_id}/finish", json={"ok": False, "error": "boom"}
    ).json()["run"]
    assert finished["status"] == "FAILED"
    agent = client.get(f"/v1/agents/managed/{agent_id}").json()["agent"]
    assert agent["status"] == "ERROR"
    assert agent["last_error"] == "boom"


def test_duplicate_starts_fresh_and_disabled(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    client.post(f"/v1/agents/managed/{agent_id}/enable")
    client.post(f"/v1/agents/managed/{agent_id}/runs")
    res = client.post(f"/v1/agents/managed/{agent_id}/duplicate", json={"name": "Clone"})
    assert res.status_code == 201
    clone = res.json()["agent"]
    assert clone["agent_id"] != agent_id
    assert clone["enabled"] is False
    assert clone["status"] == "DISABLED"
    assert clone["current_config_version"] == 1
    assert client.get(f"/v1/agents/managed/{clone['agent_id']}/runs").json()["runs"] == []
    assert client.get(f"/v1/agents/managed/{clone['agent_id']}/versions").json()["versions"] != []


def test_archive_preserves_history(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    client.post(f"/v1/agents/managed/{agent_id}/enable")
    client.post(f"/v1/agents/managed/{agent_id}/runs")
    res = client.delete(f"/v1/agents/managed/{agent_id}")
    assert res.json()["mode"] == "archived"
    assert client.get("/v1/agents/managed").json()["agents"] == []
    archived = client.get("/v1/agents/managed", params={"include_archived": True}).json()["agents"]
    assert [a["name"] for a in archived] == ["Researcher One"]
    # History survives archival.
    assert client.get(f"/v1/agents/managed/{agent_id}/runs").json()["runs"] != []
    assert client.get(f"/v1/agents/managed/{agent_id}/versions").json()["versions"] != []


def test_hard_delete_requires_confirmation_and_no_history(client):
    agent_id = _create(client).json()["agent"]["agent_id"]
    # No confirm flag: refused even with nothing to preserve.
    res = client.delete(f"/v1/agents/managed/{agent_id}", params={"hard": True})
    assert res.status_code == 422
    # Runs exist: refused even with confirmation.
    client.post(f"/v1/agents/managed/{agent_id}/enable")
    client.post(f"/v1/agents/managed/{agent_id}/runs")
    res = client.delete(f"/v1/agents/managed/{agent_id}", params={"hard": True, "confirm": True})
    assert res.status_code == 422
    # Fresh agent with explicit confirmation: destroyed.
    fresh = _create(client, name="Ephemeral").json()["agent"]
    res = client.delete(
        f"/v1/agents/managed/{fresh['agent_id']}", params={"hard": True, "confirm": True}
    )
    assert res.json() == {"deleted": "Ephemeral", "mode": "hard"}
    assert client.get(f"/v1/agents/managed/{fresh['agent_id']}").status_code == 404


def test_domain_has_no_execution_surface() -> None:
    """Runtime complement to the source scan: nothing to call, full stop."""
    for name in (
        "submit_order",
        "place_order",
        "mint_token",
        "authorize",
        "execute",
        "broker",
        "portfolio",
    ):
        assert not hasattr(managed_domain.ManagedAgentStore, name), name
