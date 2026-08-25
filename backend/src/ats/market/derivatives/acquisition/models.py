"""Strict read-only acquisition inputs, responses, and normalized failures."""

from __future__ import annotations

from enum import StrEnum

from pydantic import SecretStr

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr, NonNegativeInt


class ProviderErrorCode(StrEnum):
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    BAD_RESPONSE = "BAD_RESPONSE"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class ProviderResponse(ATSBaseModel):
    status_code: NonNegativeInt
    content_type: NonEmptyStr
    body: bytes


class AcquisitionPayload(ATSBaseModel):
    endpoint_class: NonEmptyStr
    semantic_parameters: tuple[tuple[str, str], ...]
    status_code: NonNegativeInt
    content_type: NonEmptyStr
    body: bytes


class UpstoxEndpointCatalog(ATSBaseModel):
    """Verified endpoint shapes isolated from provider-neutral ATS records."""

    bod_instruments_url: NonEmptyStr
    expiries_path: NonEmptyStr = "/expired-instruments/expiries"
    expired_options_path: NonEmptyStr = "/expired-instruments/option/contract"
    expired_futures_path: NonEmptyStr = "/expired-instruments/future/contract"
    expired_history_prefix: NonEmptyStr = "/expired-instruments/historical-candle"
    underlying_history_prefix: NonEmptyStr = "/historical-candle"


class ProviderAcquisitionError(RuntimeError):
    """A bounded provider failure whose text never includes response or credentials."""

    def __init__(self, code: ProviderErrorCode, *, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(f"provider acquisition failed: {code.value}")


def secret_present(value: SecretStr | None) -> bool:
    return value is not None and bool(value.get_secret_value())


__all__ = [
    "AcquisitionPayload",
    "ProviderAcquisitionError",
    "ProviderErrorCode",
    "ProviderResponse",
    "UpstoxEndpointCatalog",
    "secret_present",
]
