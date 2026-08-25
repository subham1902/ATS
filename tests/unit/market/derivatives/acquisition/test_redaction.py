from ats.market.derivatives.acquisition import redact_headers, redact_text


def test_sensitive_headers_and_bearer_text_are_redacted() -> None:
    value = "TEST_ONLY_REDACTION_VALUE"
    headers = redact_headers({"Authorization": f"Bearer {value}", "Accept": "application/json"})
    assert headers == {"Authorization": "[REDACTED]", "Accept": "application/json"}
    rendered = redact_text(f"request failed Bearer {value}; token={value}", (value,))
    assert value not in rendered
    assert rendered.count("[REDACTED]") == 2
