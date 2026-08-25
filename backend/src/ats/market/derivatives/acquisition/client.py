"""Narrow Upstox read client; it deliberately exposes no order/account mutation API."""

from __future__ import annotations

import json
from datetime import date
from typing import Protocol
from urllib.parse import quote

from pydantic import SecretStr

from .models import (
    AcquisitionPayload,
    ProviderAcquisitionError,
    ProviderErrorCode,
    ProviderResponse,
    UpstoxEndpointCatalog,
    secret_present,
)


class ReadTransport(Protocol):
    def get(
        self,
        *,
        path: str,
        query: tuple[tuple[str, str], ...],
        bearer_token: SecretStr | None,
    ) -> ProviderResponse: ...


class UpstoxReadOnlyClient:
    """Synchronous acquisition edge used outside trading authority and hot paths."""

    def __init__(
        self,
        *,
        transport: ReadTransport,
        endpoints: UpstoxEndpointCatalog,
        access_token: SecretStr | None,
    ) -> None:
        self._transport = transport
        self._endpoints = endpoints
        self._access_token = access_token

    def get_bod_instruments(self) -> AcquisitionPayload:
        return self._get(
            endpoint_class="BOD_INSTRUMENTS",
            path=self._endpoints.bod_instruments_url,
            query=(),
            authenticated=False,
        )

    def get_expiries(self, *, underlying_instrument_key: str) -> AcquisitionPayload:
        return self._get(
            endpoint_class="EXPIRED_EXPIRIES",
            path=self._endpoints.expiries_path,
            query=(("instrument_key", underlying_instrument_key),),
        )

    def get_expired_option_contracts(
        self, *, underlying_instrument_key: str, expiry: date
    ) -> AcquisitionPayload:
        return self._get(
            endpoint_class="EXPIRED_OPTION_CONTRACTS",
            path=self._endpoints.expired_options_path,
            query=(
                ("instrument_key", underlying_instrument_key),
                ("expiry_date", expiry.isoformat()),
            ),
        )

    def get_expired_future_contracts(
        self, *, underlying_instrument_key: str, expiry: date
    ) -> AcquisitionPayload:
        return self._get(
            endpoint_class="EXPIRED_FUTURE_CONTRACTS",
            path=self._endpoints.expired_futures_path,
            query=(
                ("instrument_key", underlying_instrument_key),
                ("expiry_date", expiry.isoformat()),
            ),
        )

    def get_expired_historical_candles_1m(
        self, *, expired_instrument_key: str, from_date: date, to_date: date
    ) -> AcquisitionPayload:
        _validate_date_range(from_date, to_date)
        path = "/".join(
            (
                self._endpoints.expired_history_prefix.rstrip("/"),
                quote(expired_instrument_key, safe=""),
                "1minute",
                to_date.isoformat(),
                from_date.isoformat(),
            )
        )
        return self._get(endpoint_class="EXPIRED_HISTORY_1M", path=path, query=())

    def get_underlying_historical_candles(
        self,
        *,
        instrument_key: str,
        unit: str,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> AcquisitionPayload:
        _validate_date_range(from_date, to_date)
        if unit not in {"minutes", "hours", "days", "weeks", "months"}:
            raise ValueError("unsupported historical unit")
        if interval <= 0:
            raise ValueError("historical interval must be positive")
        path = "/".join(
            (
                self._endpoints.underlying_history_prefix.rstrip("/"),
                quote(instrument_key, safe=""),
                unit,
                str(interval),
                to_date.isoformat(),
                from_date.isoformat(),
            )
        )
        return self._get(endpoint_class="UNDERLYING_HISTORY", path=path, query=())

    def _get(
        self,
        *,
        endpoint_class: str,
        path: str,
        query: tuple[tuple[str, str], ...],
        authenticated: bool = True,
    ) -> AcquisitionPayload:
        if authenticated and not secret_present(self._access_token):
            raise ProviderAcquisitionError(ProviderErrorCode.AUTHORIZATION_REQUIRED, status_code=0)
        response = self._transport.get(
            path=path,
            query=query,
            bearer_token=self._access_token if authenticated else None,
        )
        if not 200 <= response.status_code < 300:
            raise ProviderAcquisitionError(
                _normalize_error(response), status_code=response.status_code
            )
        return AcquisitionPayload(
            endpoint_class=endpoint_class,
            semantic_parameters=query,
            status_code=response.status_code,
            content_type=response.content_type,
            body=response.body,
        )


def _normalize_error(response: ProviderResponse) -> ProviderErrorCode:
    provider_code = ""
    try:
        document = json.loads(response.body)
        if isinstance(document, dict):
            provider_code = str(document.get("code", ""))
            errors = document.get("errors")
            if not provider_code and isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    provider_code = str(first.get("errorCode", first.get("code", "")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        if response.status_code < 500:
            return ProviderErrorCode.BAD_RESPONSE
    if provider_code == "UDAPI1149":
        return ProviderErrorCode.ENTITLEMENT_REQUIRED
    if response.status_code in {401, 403}:
        return ProviderErrorCode.AUTHORIZATION_REQUIRED
    if response.status_code == 404:
        return ProviderErrorCode.DATA_NOT_FOUND
    if response.status_code == 429:
        return ProviderErrorCode.RATE_LIMITED
    if response.status_code >= 500:
        return ProviderErrorCode.PROVIDER_UNAVAILABLE
    return ProviderErrorCode.UNKNOWN_PROVIDER_ERROR


def _validate_date_range(from_date: date, to_date: date) -> None:
    if from_date > to_date:
        raise ValueError("from_date must be <= to_date")


__all__ = ["ReadTransport", "UpstoxReadOnlyClient"]
