"""Credentialed CORS is an explicit allowlist, never a wildcard."""

import pytest
from ats.console.app import create_console_app
from ats.console.cors import (
    DEFAULT_LOCAL_ORIGINS,
    InvalidCorsConfiguration,
    resolve_cors_origins,
)
from fastapi.testclient import TestClient


def test_defaults_are_local_control_center_origins_only():
    origins = resolve_cors_origins({})
    assert origins == list(DEFAULT_LOCAL_ORIGINS)
    assert "*" not in origins


def test_configured_origins_are_normalised_and_deduplicated():
    env = {
        "ATS_CORS_ORIGINS": "https://ops.example.com/, https://ops.example.com ,http://localhost:3001"
    }
    assert resolve_cors_origins(env) == ["https://ops.example.com", "http://localhost:3001"]


@pytest.mark.parametrize(
    "bad",
    [
        "*",
        "https://*.example.com",
        "ops.example.com",
        "ftp://x.test",
        "https://x.test/path",
        "https://u:p@x.test",
        ",",
    ],
)
def test_unsafe_or_malformed_origins_fail_at_startup(bad):
    with pytest.raises(InvalidCorsConfiguration):
        resolve_cors_origins({"ATS_CORS_ORIGINS": bad})


def test_app_refuses_to_start_with_a_wildcard(monkeypatch):
    monkeypatch.setenv("ATS_CORS_ORIGINS", "*")
    with pytest.raises(InvalidCorsConfiguration):
        create_console_app()


def test_preflight_allows_listed_origin_and_denies_others(monkeypatch):
    monkeypatch.delenv("ATS_CORS_ORIGINS", raising=False)
    client = TestClient(create_console_app())
    headers = {"Access-Control-Request-Method": "GET"}
    ok = client.options("/health/live", headers={**headers, "Origin": "http://localhost:3001"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3001"
    assert ok.headers.get("access-control-allow-credentials") == "true"
    bad = client.options("/health/live", headers={**headers, "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_unrelated_origin_cannot_issue_operator_mutation():
    client = TestClient(create_console_app())
    response = client.post(
        "/v1/runtime/command",
        headers={"Origin": "http://localhost:3000"},
        json={"command": "HALT_SYSTEM"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "OPERATOR_ORIGIN_REJECTED"
