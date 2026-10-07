"""Official MT5 Python integration, wrapped with a read-only surface."""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any


class Mt5Transport:
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self._terminal: Any = None
        self._settings = settings

    @property
    def sdk(self) -> Any:
        return self._terminal

    def initialize(self) -> bool:
        self._terminal = importlib.import_module("MetaTrader5")
        if self._settings is not None:
            options = {key: value for key, value in self._settings.items() if key != "symbol"}
            return bool(self._terminal.initialize(**options))
        options = {"timeout": 5000}
        for key, env in (
            ("path", "ATS_MT5_TERMINAL_PATH"),
            ("password", "ATS_MT5_PASSWORD"),
            ("server", "ATS_MT5_SERVER"),
        ):
            if os.environ.get(env):
                options[key] = os.environ[env]
        if os.environ.get("ATS_MT5_LOGIN"):
            options["login"] = int(os.environ["ATS_MT5_LOGIN"])
        # No login arguments attaches to an already authenticated local terminal.
        return bool(self._terminal.initialize(**options))

    def symbol_info(self, symbol: str) -> Mapping[str, Any] | None:
        if not self._terminal.symbol_select(symbol, True):
            return None
        info = self._terminal.symbol_info(symbol)
        return dict(info._asdict()) if info is not None else None

    def latest_tick(self, symbol: str) -> Mapping[str, Any] | None:
        tick = self._terminal.symbol_info_tick(symbol)
        if tick is None:
            return None
        result = dict(tick._asdict())
        # The terminal's tick volume is broker reported; zero alone cannot prove a trade.
        if result.get("volume", 0) == 0:
            result.pop("volume", None)
        if result.get("volume_real", 0) > 0:
            result["real_volume"] = result["volume_real"]
        result.pop("volume_real", None)
        return result

    @staticmethod
    def _records(array: Any) -> list[Mapping[str, Any]]:
        if array is None:
            raise ValueError("TERMINAL_HISTORY_UNAVAILABLE")
        return [dict(zip(array.dtype.names, row, strict=True)) for row in array.tolist()]

    def historical_ticks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        rows = self._records(
            self._terminal.copy_ticks_range(symbol, start, end, self._terminal.COPY_TICKS_ALL)
        )
        for row in rows:
            if isinstance(row, dict):
                if row.get("volume", 0) == 0:
                    row.pop("volume", None)
                if row.get("volume_real", 0) > 0:
                    row["real_volume"] = row["volume_real"]
                row.pop("volume_real", None)
        return rows

    def historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        codes = {
            "1m": "TIMEFRAME_M1",
            "5m": "TIMEFRAME_M5",
            "15m": "TIMEFRAME_M15",
            "1h": "TIMEFRAME_H1",
            "1d": "TIMEFRAME_D1",
        }
        if timeframe not in codes:
            raise ValueError("UNSUPPORTED_TIMEFRAME")
        return self._records(
            self._terminal.copy_rates_range(
                symbol, getattr(self._terminal, codes[timeframe]), start, end
            )
        )

    def shutdown(self) -> None:
        if self._terminal is not None:
            self._terminal.shutdown()
