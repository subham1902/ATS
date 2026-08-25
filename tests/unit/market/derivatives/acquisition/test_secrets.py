from ats.market.derivatives.acquisition import load_upstox_runtime_secrets


def test_only_explicit_runtime_variables_are_loaded_and_repr_is_redacted() -> None:
    marker = "TEST_ONLY_SECRET_MARKER"
    secrets = load_upstox_runtime_secrets(
        {
            "ATS_UPSTOX_ACCESS_TOKEN": marker,
            "ATS_UPSTOX_CLIENT_ID": "TEST_ONLY_CLIENT",
            "ATS_UPSTOX_CLIENT_SECRET": "TEST_ONLY_CLIENT_SECRET",
            "ATS_UPSTOX_REDIRECT_URI": "http://127.0.0.1/test-callback",
            "UNRELATED_SECRET": "MUST_NOT_LOAD",
        }
    )
    assert secrets.access_token is not None
    assert marker not in repr(secrets)
    assert "MUST_NOT_LOAD" not in repr(secrets)


def test_absent_runtime_variables_remain_absent() -> None:
    secrets = load_upstox_runtime_secrets({})
    assert secrets.access_token is None
    assert secrets.client_id is None
    assert secrets.client_secret is None
    assert secrets.redirect_uri is None
