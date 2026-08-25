from __future__ import annotations

from datetime import date

import pytest
from ats.market.derivatives.acquisition import (
    ProviderAcquisitionError,
    ProviderErrorCode,
    ProviderResponse,
    UpstoxEndpointCatalog,
    UpstoxReadOnlyClient,
)
from pydantic import SecretStr


class FakeTransport:
    def __init__(self, response: ProviderResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, tuple[tuple[str, str], ...], bool]] = []

    def get(
        self,
        *,
        path: str,
        query: tuple[tuple[str, str], ...],
        bearer_token: SecretStr | None,
    ) -> ProviderResponse:
        self.calls.append((path, query, bearer_token is not None))
        return self.response


def client(
    response: ProviderResponse, *, authenticated: bool = True
) -> tuple[UpstoxReadOnlyClient, FakeTransport]:
    transport = FakeTransport(response)
    result = UpstoxReadOnlyClient(
        transport=transport,
        endpoints=UpstoxEndpointCatalog(
            bod_instruments_url="https://example.invalid/recorded-provider-shape.json.gz"
        ),
        access_token=SecretStr("TEST_ONLY_REDACTION_VALUE") if authenticated else None,
    )
    return result, transport


def ok() -> ProviderResponse:
    return ProviderResponse(status_code=200, content_type="application/json", body=b'{"data":[]}')


def test_read_only_paths_and_one_minute_expired_interval() -> None:
    api, transport = client(ok())
    api.get_expiries(underlying_instrument_key="TEST_INDEX|NIFTY")
    api.get_expired_option_contracts(
        underlying_instrument_key="TEST_INDEX|NIFTY", expiry=date(2026, 8, 24)
    )
    api.get_expired_historical_candles_1m(
        expired_instrument_key="TEST_FO|123|24-08-2026",
        from_date=date(2026, 8, 24),
        to_date=date(2026, 8, 24),
    )
    assert transport.calls[0][0] == "/expired-instruments/expiries"
    assert transport.calls[2][0].split("/")[-3] == "1minute"
    assert not hasattr(api, "place_order")
    assert not hasattr(api, "cancel_order")


def test_public_bod_request_does_not_receive_bearer() -> None:
    api, transport = client(ok())
    api.get_bod_instruments()
    assert transport.calls == [
        ("https://example.invalid/recorded-provider-shape.json.gz", (), False)
    ]


def test_missing_authorization_fails_before_transport() -> None:
    api, transport = client(ok(), authenticated=False)
    with pytest.raises(ProviderAcquisitionError) as raised:
        api.get_expiries(underlying_instrument_key="TEST_INDEX|NIFTY")
    assert raised.value.code is ProviderErrorCode.AUTHORIZATION_REQUIRED
    assert not transport.calls


@pytest.mark.parametrize(
    ("status", "body", "code"),
    (
        (403, b'{"code":"UDAPI1149"}', ProviderErrorCode.ENTITLEMENT_REQUIRED),
        (401, b'{"code":"INVALID_TOKEN"}', ProviderErrorCode.AUTHORIZATION_REQUIRED),
        (429, b'{"code":"RATE"}', ProviderErrorCode.RATE_LIMITED),
        (503, b"unavailable", ProviderErrorCode.PROVIDER_UNAVAILABLE),
        (404, b'{"code":"MISSING"}', ProviderErrorCode.DATA_NOT_FOUND),
        (400, b"not-json", ProviderErrorCode.BAD_RESPONSE),
    ),
)
def test_provider_errors_are_typed_and_bounded(
    status: int, body: bytes, code: ProviderErrorCode
) -> None:
    api, transport = client(
        ProviderResponse(status_code=status, content_type="application/json", body=body)
    )
    with pytest.raises(ProviderAcquisitionError) as raised:
        api.get_expiries(underlying_instrument_key="TEST_INDEX|NIFTY")
    assert raised.value.code is code
    assert body.decode(errors="ignore") not in str(raised.value)
    assert len(transport.calls) == 1


def test_historical_date_range_and_unit_are_fail_closed() -> None:
    api, transport = client(ok())
    with pytest.raises(ValueError, match="from_date"):
        api.get_expired_historical_candles_1m(
            expired_instrument_key="TEST_FO|1",
            from_date=date(2026, 8, 25),
            to_date=date(2026, 8, 24),
        )
    with pytest.raises(ValueError, match="unsupported historical unit"):
        api.get_underlying_historical_candles(
            instrument_key="TEST_INDEX|1",
            unit="fortnights",
            interval=1,
            from_date=date(2026, 8, 24),
            to_date=date(2026, 8, 24),
        )
    assert not transport.calls
