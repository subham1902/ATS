"""Read-only local MT5 probe; output excludes login, password and personal metadata."""
from __future__ import annotations

import argparse
import importlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import platform
import struct


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = {"observed_at": datetime.now(UTC).isoformat(), "python": platform.python_version(),
              "architecture_bits": struct.calcsize("P") * 8,
              "terminal_present": Path(arguments.terminal).is_file(), "orders_submitted": 0,
              "canonical_symbol": "XAUUSD", "broker_symbol": arguments.symbol}
    sdk = None
    try:
        sdk = importlib.import_module("MetaTrader5")
        report["sdk_version"] = sdk.__version__
        initialized = sdk.initialize(path=arguments.terminal, timeout=5000)
        report["ipc_initialized"] = bool(initialized)
        if initialized:
            terminal, account = sdk.terminal_info(), sdk.account_info()
            report["terminal_connected"] = bool(terminal and terminal.connected)
            report["authenticated"] = bool(account)
            report["account_mode"] = ({sdk.ACCOUNT_TRADE_MODE_DEMO: "DEMO", sdk.ACCOUNT_TRADE_MODE_REAL: "LIVE"}.get(account.trade_mode, "UNKNOWN") if account else "UNKNOWN")
            selected = sdk.symbol_select(arguments.symbol, True)
            metadata = sdk.symbol_info(arguments.symbol) if selected else None
            tick = sdk.symbol_info_tick(arguments.symbol) if selected else None
            report["symbol_metadata"] = ({key: getattr(metadata, key) for key in
                ("name", "digits", "point", "trade_tick_size", "trade_contract_size", "volume_min", "volume_max", "volume_step", "trade_mode", "currency_base", "currency_profit")} if metadata else None)
            now = datetime.now(UTC)
            stamp = datetime.fromtimestamp(tick.time_msc / 1000, UTC) if tick else None
            report["local_receive_timestamp"] = now.isoformat()
            report["source_timestamp_as_epoch_utc"] = stamp.isoformat() if stamp else None
            age = (now - stamp).total_seconds() if stamp else None
            report["source_age_seconds"] = age
            report["time_status"] = ("FUTURE_SOURCE_TIMESTAMP" if age is not None and age < 0 else "STALE" if age is not None and age > 15 else "OBSERVED_UTC" if age is not None else "NO_TICK")
            report["observed_bid"] = str(tick.bid) if tick and tick.bid > 0 else None
            report["observed_ask"] = str(tick.ask) if tick and tick.ask > 0 else None
            report["observed_spread"] = str(Decimal(str(tick.ask)) - Decimal(str(tick.bid))) if tick and tick.bid > 0 and tick.ask >= tick.bid else None
    except Exception:
        report["error"] = "MT5_ENVIRONMENT_PROBE_FAILED"
    finally:
        if sdk is not None:
            sdk.shutdown()
    encoded = json.dumps(report, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
