"""Fake read-only account sessions: CI never connects an account or places orders."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ats.console.app import create_console_app
from ats.market.metatrader.account_service import AccountService
from ats.market.metatrader.accounts import ConnectAccount
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
