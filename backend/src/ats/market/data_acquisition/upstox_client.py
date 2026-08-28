"""Read-only Upstox Analytics market-data client (no static-IP dependency).

This client only touches market-data endpoints (market quote, historical
candle, option chain). It never calls account APIs (profile, portfolio,
orders, funds). The access token is loaded from the process environment or
the Windows User environment and is never printed, logged, or persisted.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import winreg
from typing import Any, cast

_UPSTOX_BASE = "https://api.upstox.com"
_USER_AGENT = "ATS-Research-Client/1.0"


def _load_token() -> str | None:
    token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN")
    if token:
        return token
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        return cast("str", winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0])
    except Exception:
        return None


class UpstoxReadOnlyClient:
    """Minimal read-only market-data client for the Analytics token class."""

    def __init__(self, token: str | None = None) -> None:
        resolved = token or _load_token()
        if not resolved:
            raise RuntimeError("ATS_UPSTOX_ACCESS_TOKEN is not configured")
        self._token = resolved

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = _UPSTOX_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60.0) as response:
            return cast("dict[str, Any]", json.loads(response.read().decode("utf-8", "replace")))

    def ltp(self, instrument_key: str) -> dict[str, Any]:
        return self._get("/v3/market-quote/ltp", {"instrument_key": instrument_key})

    def historical_candle(
        self,
        instrument_key: str,
        interval: str = "1minute",
        from_date: str = "2026-08-25",
        to_date: str = "2026-08-25",
    ) -> dict[str, Any]:
        key = urllib.parse.quote(instrument_key)
        return self._get(f"/v2/historical-candle/{key}/{interval}/{to_date}/{from_date}")

    def intraday_candles(
        self, instrument_key: str, *, unit: str = "minutes", interval: int = 5
    ) -> dict[str, Any]:
        """Return current-session V3 candles from the read-only market-data API."""

        if unit not in {"minutes", "hours", "days"} or interval <= 0:
            raise ValueError("invalid intraday candle unit or interval")
        key = urllib.parse.quote(instrument_key, safe="")
        return self._get(
            f"/v3/historical-candle/intraday/{key}/{unit}/{interval}"
        )

    def option_chain(self, instrument_key: str) -> dict[str, Any]:
        return self._get("/v2/option/contract", {"instrument_key": instrument_key})

    def fetch_raw_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """Return raw response bytes (for immutable raw-artifact storage)."""
        url = _UPSTOX_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=120.0) as response:
            return bytes(response.read())


__all__ = ["UpstoxReadOnlyClient"]
