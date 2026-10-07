"""One bounded read-only IPC process per MT5 account; no execution capability."""

from __future__ import annotations

import multiprocessing
from collections.abc import Mapping
from datetime import datetime
from multiprocessing.connection import _ConnectionBase
from multiprocessing.process import BaseProcess
from threading import RLock
from typing import Any, Protocol

from ats.market.metatrader.mt5 import Mt5Transport


class AccountSession(Protocol):
    def initialize(self) -> bool: ...
    def symbol_info(self, symbol: str) -> Mapping[str, Any] | None: ...
    def latest_tick(self, symbol: str) -> Mapping[str, Any] | None: ...
    def historical_ticks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]: ...
    def historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]: ...
    def snapshot(self, symbol: str) -> dict[str, Any]: ...
    def shutdown(self) -> None: ...


def _safe_snapshot(sdk: Any, symbol: str, login: int, server: str) -> dict[str, Any]:
    terminal = sdk.terminal_info()
    account = sdk.account_info()
    if terminal is None or not terminal.connected or account is None:
        raise ValueError("ACCOUNT_SESSION_DISCONNECTED")
    if account.login != login or account.server != server:
        raise ValueError("AUTHENTICATED_ACCOUNT_MISMATCH")
    positions = sdk.positions_get(symbol=symbol)
    orders = sdk.orders_get(symbol=symbol)
    if positions is None or orders is None:
        raise ValueError("ACCOUNT_STATE_UNKNOWN")
    mode = {sdk.ACCOUNT_TRADE_MODE_DEMO: "DEMO", sdk.ACCOUNT_TRADE_MODE_REAL: "LIVE"}.get(
        account.trade_mode, "UNKNOWN"
    )
    return {
        "account_mode": mode,
        "balance": str(account.balance),
        "equity": str(account.equity),
        "margin": str(account.margin),
        "free_margin": str(account.margin_free),
        "currency": account.currency,
        "terminal_profile": terminal.data_path,
        "positions": [
            {
                key: getattr(position, key)
                for key in (
                    "ticket",
                    "symbol",
                    "type",
                    "volume",
                    "price_open",
                    "price_current",
                    "sl",
                    "tp",
                    "profit",
                    "swap",
                    "time_msc",
                )
            }
            for position in positions
        ],
        "orders": [
            {
                key: getattr(order, key)
                for key in (
                    "ticket",
                    "symbol",
                    "type",
                    "state",
                    "volume_initial",
                    "volume_current",
                    "price_open",
                    "sl",
                    "tp",
                    "time_setup_msc",
                )
            }
            for order in orders
        ],
    }


def _worker(pipe: _ConnectionBase, settings: dict[str, Any]) -> None:
    transport = Mt5Transport(settings=settings)
    try:
        while True:
            command, arguments = pipe.recv()
            try:
                if command == "initialize":
                    if not transport.initialize():
                        raise ValueError("ACCOUNT_INITIALIZATION_FAILED")
                    # Initialization may attach to the wrong cached terminal account.
                    _safe_snapshot(
                        transport.sdk, settings["symbol"], settings["login"], settings["server"]
                    )
                    result: Any = True
                elif command == "shutdown":
                    transport.shutdown()
                    pipe.send((True, None))
                    break
                elif command in {
                    "symbol_info",
                    "latest_tick",
                    "historical_ticks",
                    "historical_bars",
                    "snapshot",
                }:
                    _safe_snapshot(
                        transport.sdk, settings["symbol"], settings["login"], settings["server"]
                    )
                    if command == "snapshot":
                        result = _safe_snapshot(
                            transport.sdk, arguments[0], settings["login"], settings["server"]
                        )
                    else:
                        result = getattr(transport, command)(*arguments)
                else:
                    raise ValueError("UNSUPPORTED_READ_OPERATION")
                pipe.send((True, result))
            except Exception:
                # Vendor exceptions can include login/password; never send their text.
                pipe.send((False, "ACCOUNT_SESSION_OPERATION_FAILED"))
    except (EOFError, OSError):
        pass
    finally:
        transport.shutdown()
        pipe.close()


class Mt5AccountSession:
    def __init__(self, settings: dict[str, Any], timeout: float = 8) -> None:
        self._settings = settings
        self._timeout = timeout
        self._lock = RLock()
        self._process: BaseProcess | None = None
        self._pipe: _ConnectionBase | None = None

    def _request(self, operation: str, *arguments: object) -> Any:
        with self._lock:
            if self._pipe is None:
                raise ValueError("ACCOUNT_WORKER_NOT_RUNNING")
            try:
                self._pipe.send((operation, arguments))
                if not self._pipe.poll(self._timeout):
                    raise TimeoutError("ACCOUNT_IPC_TIMEOUT")
                success, result = self._pipe.recv()
                if not success:
                    raise ValueError("ACCOUNT_SESSION_OPERATION_FAILED")
                return result
            except (EOFError, OSError, TimeoutError):
                self._terminate()
                raise ValueError("ACCOUNT_IPC_UNAVAILABLE") from None

    def initialize(self) -> bool:
        with self._lock:
            self._terminate()
            context = multiprocessing.get_context("spawn")
            self._pipe, child = context.Pipe()
            self._process = context.Process(
                target=_worker, args=(child, self._settings), daemon=True
            )
            self._process.start()
            child.close()
            return bool(self._request("initialize"))

    def symbol_info(self, symbol: str) -> Mapping[str, Any] | None:
        result: Mapping[str, Any] | None = self._request("symbol_info", symbol)
        return result

    def latest_tick(self, symbol: str) -> Mapping[str, Any] | None:
        result: Mapping[str, Any] | None = self._request("latest_tick", symbol)
        return result

    def historical_ticks(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        result: list[Mapping[str, Any]] = self._request("historical_ticks", symbol, start, end)
        return result

    def historical_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Mapping[str, Any]]:
        result: list[Mapping[str, Any]] = self._request(
            "historical_bars", symbol, timeframe, start, end
        )
        return result

    def snapshot(self, symbol: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request("snapshot", symbol)
        return result

    def _terminate(self) -> None:
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=1)
            self._process.close()
        if self._pipe is not None:
            self._pipe.close()
        self._process = None
        self._pipe = None

    def shutdown(self) -> None:
        with self._lock:
            try:
                if self._pipe is not None:
                    self._request("shutdown")
            finally:
                self._terminate()
