"""Fake read-only account sessions: CI never connects an account or places orders."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ats.console.app import create_console_app
from ats.market.metatrader.account_service import AccountService
from ats.market.metatrader.accounts import AdoptAccount, ConnectAccount
from ats.market.metatrader.credentials import WindowsCredentialVault
from ats.market.metatrader.registry import AccountRegistry
from fastapi.testclient import TestClient

from backend.tests.test_xauusd_foundation import FakeTransport


class FakeVault:
    def __init__(self):
        self.values = {}

    def store(self, login, password):
        reference = "ref-" + str(len(self.values))
        self.values[reference] = (login, password)
        return reference

    def load(self, reference):
        return self.values[reference]

    def delete(self, reference):
        self.values.pop(reference, None)


class FakeSession(FakeTransport):
    def __init__(self, account, login, password):
        self.account, self.login = account, login
        self.failed = False
        self.connected = password == "test" + "-password"
        self.tick = {**FakeTransport.tick, "time_msc": int(datetime.now(UTC).timestamp() * 1000)}

    def snapshot(self, symbol):
        if self.failed:
            raise ValueError("secret should never escape " + self.login)
        return {
            "account_mode": "DEMO" if self.login == "1" else "LIVE",
            "terminal_profile": self.account.terminal_path,
            "balance": "10000",
            "equity": "10001",
            "margin": "10",
            "free_margin": "9991",
            "currency": "USD",
            "positions": [],
            "orders": [],
        }


def request(login="1", **changes):
    return ConnectAccount(
        login=login,
        password="test" + "-password",
        server="TestServer",
        display_name="Test Account",
        terminal_path=f"C:/terminal-{login}/terminal64.exe",
        **changes,
    )


def test_adoption_private_identity_handoff_and_monitor_only(service, monkeypatch):
    class AdoptionProbe:
        def __init__(self, settings):
            assert "password" not in settings and "login" not in settings

        def initialize(self):
            return True

        def authenticated_reference(self):
            return "1", "TestServer"

        def shutdown(self):
            pass

    monkeypatch.setattr("ats.market.metatrader.account_service.Mt5AccountSession", AdoptionProbe)
    service.factory = lambda account, login, password: FakeSession(account, login, "test-password")
    result = service.adopt_authenticated(
        AdoptAccount(display_name="Cached session", terminal_path="C:/terminal-1/terminal64.exe")
    )
    assert result["account"]["connection_state"] == "CONNECTED"
    assert not result["account"]["execution_enabled"]
    assert "credential_reference" not in result["account"]
    assert next(iter(service.vault.values.values())) == ("1", "")


@pytest.fixture
def service(tmp_path):
    result = AccountService(
        AccountRegistry(tmp_path / "registry"), FakeVault(), tmp_path, FakeSession
    )
    yield result
    result.shutdown()


def test_connect_demo_live_consent_and_secret_redaction(service):
    demo = service.connect_new(request())
    live = service.connect_new(request("2", action="CONNECT_AND_ENABLE_EXECUTION"))
    assert demo["account"]["account_mode"] == "DEMO"
    assert not demo["account"]["execution_enabled"]
    assert live["account"]["account_mode"] == "LIVE"
    assert live["account"]["execution_enabled"]
    assert live["execution_gate"] == "EXTERNAL_ROUTING_NOT_IMPLEMENTED"
    assert demo["account"]["account_id"] != live["account"]["account_id"]
    payload = json.dumps(service.list())
    assert "password" not in payload and "credential_reference" not in payload
    assert "test-password" not in payload
    assert live["market"]["state"] == "LIVE"


def test_account_failure_isolated_and_reconnect_disables_consent(service):
    first = service.connect_new(request(action="CONNECT_AND_ENABLE_EXECUTION"))["account"][
        "account_id"
    ]
    second = service.connect_new(request("2", action="CONNECT_AND_ENABLE_EXECUTION"))["account"][
        "account_id"
    ]
    service._connections[first].session.failed = True
    service.poll(first)
    assert service.view(first)["account"]["connection_state"] == "ERROR"
    assert not service.view(first)["account"]["execution_enabled"]
    assert service.view(second)["account"]["connection_state"] == "CONNECTED"
    assert service.view(second)["account"]["execution_enabled"]
    assert not service.connect(first)["account"]["execution_enabled"]
    service.set_execution(first, True)
    assert service.disconnect(first)["account"]["connection_state"] == "DISCONNECTED"
    with pytest.raises(ValueError, match="CONNECTED_ACCOUNT_REQUIRED"):
        service.set_execution(first, True)


def test_duplicate_terminal_rejected_transactionally(service):
    service.connect_new(request())
    with pytest.raises(ValueError, match="TERMINAL_ALREADY_ASSIGNED"):
        service.connect_new(request())
    assert len(service.registry.list()) == 1
    assert len(service.vault.values) == 1


def test_shared_observed_profile_fails_closed(service):
    original = service.factory

    def shared(account, login, password):
        result = original(account, login, password)
        snapshot = result.snapshot
        result.snapshot = lambda symbol: {**snapshot(symbol), "terminal_profile": "SHARED"}
        return result

    service.factory = shared
    first = service.connect_new(request())
    second = service.connect_new(request("2"))
    assert first["account"]["connection_state"] == "CONNECTED"
    assert second["account"]["connection_state"] == "ERROR"


def test_invalid_credentials_missing_terminal_mt4_and_restart(service):
    invalid = request().model_copy(update={"password": request().login})
    assert service.connect_new(invalid)["account"]["connection_state"] == "ERROR"
    mt4 = service.connect_new(request("4", platform="MT4"))
    assert mt4["account"]["connection_state"] == "NOT_CONFIGURED"
    result = service.connect_new(request("2", action="CONNECT_AND_ENABLE_EXECUTION"))
    service.shutdown()
    restarted = AccountService(service.registry, service.vault, service.root, FakeSession)
    assert (
        restarted.view(result["account"]["account_id"])["account"]["connection_state"]
        == "DISCONNECTED"
    )
    assert not restarted.view(result["account"]["account_id"])["account"]["execution_enabled"]


def test_accounts_api_never_echoes_password_or_login_on_validation_failure(service):
    client = TestClient(create_console_app(account_service=service))
    body = request().model_dump(mode="json")
    body["login"] = "1"
    body["password"] = "test" + "-password"
    response = client.post("/v1/accounts", json=body)
    assert response.status_code == 201
    assert "test-password" not in response.text
    body["login"] = "private-invalid-login"
    response = client.post("/v1/accounts", json=body)
    assert response.status_code == 422
    assert "private-invalid-login" not in response.text
    assert "test-password" not in response.text


@pytest.mark.skipif(os.name != "nt", reason="Windows user-bound DPAPI integration")
def test_dpapi_vault_persists_ciphertext_only(tmp_path: Path):
    vault = WindowsCredentialVault(tmp_path)
    secret = "local-test" + "-password"
    reference = vault.store("12345", secret)
    assert vault.load(reference) == ("12345", secret)
    contents = (tmp_path / (reference + ".dpapi")).read_bytes()
    assert secret.encode() not in contents
    assert b"12345" not in contents
    with pytest.raises(ValueError):
        vault.load("../../outside")
    vault.delete(reference)


def test_registered_disconnected_account_does_not_fall_back(service):
    result = service.connect_new(request())
    account_id = result["account"]["account_id"]
    service.disconnect(account_id)
    with pytest.raises(ValueError, match="REGISTERED_ACCOUNT_CONNECTION_REQUIRED"):
        service.market_connection()


def test_unregistered_offline_mode_can_use_standalone(service):
    assert service.market_connection() is None


def test_control_configuration_versions_and_consent_reset(service):
    from ats.market.metatrader.control_config import AccountControlConfig

    result = service.connect_new(request(action="CONNECT_AND_ENABLE_EXECUTION"))
    account_id = result["account"]["account_id"]
    config = AccountControlConfig(
        revision=1,
        risk_per_trade="0.005",
        daily_loss_fraction="0.03",
        monthly_loss_fraction="0.08",
        max_open_risk_fraction="0.01",
        max_strategy_risk_fraction="0.01",
        max_volume="0.1",
        max_positions=1,
        margin_fraction="0.30",
    )
    service.registry.configure(account_id, config, 0)
    assert service.registry.control_config(account_id) == config
    assert not service.registry.get(account_id).execution_enabled
    with pytest.raises(ValueError, match="CONFIGURATION_REVISION_CONFLICT"):
        service.registry.configure(account_id, config, 0)
    with pytest.raises(ValueError):
        AccountControlConfig.model_validate(
            {**config.model_dump(), "monthly_loss_fraction": "0.09"}
        )


def test_readiness_does_not_treat_consent_as_authority(service):
    result = service.connect_new(request(action="CONNECT_AND_ENABLE_EXECUTION"))
    app = create_console_app(account_service=service)
    with TestClient(app) as client:
        response = client.get(f"/v1/accounts/{result['account']['account_id']}/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["effective_execution_enabled"] is False
        assert "EXTERNAL_ROUTING_NOT_COMMISSIONED" in data["reason_codes"]
        assert "RISK_CONFIGURATION_REQUIRED" in data["reason_codes"]


def test_native_state_is_observation_only_and_checks_identity(service):
    result = service.connect_new(request())
    account_id = result["account"]["account_id"]
    connection = service._connections[account_id]
    profile = service.root / "fake-profile"
    connection.snapshot["terminal_profile"] = str(profile)
    target = profile / "MQL5/Files/ATS/SmallAccount" / account_id / "account-state.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "account_id": account_id,
                "canonical_symbol": "XAUUSD",
                "source_server": "TestServer",
                "identity_matches": True,
                "execution_authority": "NONE",
                "signal_status": "CLOCK_PROFILE_REQUIRED",
            }
        )
    )
    state = service.native_observer(account_id)
    assert state["state"] == "OBSERVING"
    assert state["observations"]["execution_authority"] == "NONE"
    target.write_text(json.dumps({"account_id": "other"}))
    assert service.native_observer(account_id)["state"] == "UNKNOWN"


def test_clock_refresh_requires_unexpired_account_evidence(service):
    from ats.market.metatrader.clock import BrokerClockEvidence

    result = service.connect_new(request())
    account_id = result["account"]["account_id"]
    now = datetime.now(UTC)
    epoch = int(now.timestamp())
    evidence = BrokerClockEvidence(
        server="TestServer",
        terminal_gmt_epoch=epoch,
        terminal_server_epoch=epoch,
        tick_epoch_ms=epoch * 1000,
        independent_utc_epoch=epoch,
        captured_at=now,
        probe_hash="a" * 64,
        independent_source="unit-test",
        valid_seconds=900,
    )
    target = service.clock_evidence_path(account_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(evidence.model_dump_json())
    refreshed = service.refresh_clock(account_id)
    assert refreshed["scope"] == "LIVE_ONLY_NOT_HISTORICAL_TIMEZONE"
    assert not service.registry.get(account_id).execution_enabled
    target.write_text(evidence.model_copy(update={"server": "another-server"}).model_dump_json())
    with pytest.raises(ValueError, match="CLOCK_SERVER_MISMATCH"):
        service.refresh_clock(account_id)


def test_loss_budget_projection_cannot_inject_evidence(service):
    from ats.market.metatrader.control_config import AccountControlConfig

    result = service.connect_new(request())
    account_id = result["account"]["account_id"]
    with TestClient(create_console_app(account_service=service)) as client:
        path = f"/v1/accounts/{account_id}/loss-budget"
        empty = client.get(path).json()
        assert empty["state"] == "UNKNOWN"
        assert empty["reason_codes"] == ["RISK_CONFIGURATION_REQUIRED"]
        config = AccountControlConfig(
            revision=1,
            risk_per_trade=".005",
            daily_loss_fraction=".03",
            monthly_loss_fraction=".08",
            max_open_risk_fraction=".01",
            max_strategy_risk_fraction=".01",
            max_volume=".1",
            max_positions=1,
            margin_fraction=".30",
        )
        service.registry.configure(account_id, config, 0)
        data = client.get(path).json()
        assert data["state"] == "UNKNOWN"
        assert data["monthly_remaining"] is None
        assert data["grants_authority"] is False
        assert client.post(path, json={"monthly_remaining": 80}).status_code == 405
        assert client.get("/v1/accounts/ACC-missing/loss-budget").status_code == 404
        assert not service.registry.get(account_id).execution_enabled
