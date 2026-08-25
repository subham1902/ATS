"""Memory-only loading of the explicitly approved Upstox runtime variables."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import SecretStr

from ats.contracts.common import ATSBaseModel
from ats.contracts.domain.types import NonEmptyStr


class UpstoxRuntimeSecrets(ATSBaseModel):
    access_token: SecretStr | None
    client_id: SecretStr | None
    client_secret: SecretStr | None
    redirect_uri: NonEmptyStr | None


def load_upstox_runtime_secrets(
    environment: Mapping[str, str] | None = None,
) -> UpstoxRuntimeSecrets:
    source = os.environ if environment is None else environment
    return UpstoxRuntimeSecrets(
        access_token=_secret(source.get("ATS_UPSTOX_ACCESS_TOKEN")),
        client_id=_secret(source.get("ATS_UPSTOX_CLIENT_ID")),
        client_secret=_secret(source.get("ATS_UPSTOX_CLIENT_SECRET")),
        redirect_uri=source.get("ATS_UPSTOX_REDIRECT_URI") or None,
    )


def _secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value else None


__all__ = ["UpstoxRuntimeSecrets", "load_upstox_runtime_secrets"]
