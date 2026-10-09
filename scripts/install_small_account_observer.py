"""Install versioned observation files into a verified flat DEMO terminal.

No attachment, terminal toggle, order submission or credential export occurs here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ats.datasets.ingestion import data_root
from ats.market.metatrader.credentials import WindowsCredentialVault
from ats.market.metatrader.registry import AccountRegistry
from ats.strategies.small_account_presets import SmallAccountPreset

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--build-s3-profile", action="store_true")
    options = parser.parse_args()
    root = data_root()
    account = AccountRegistry(root / "system/accounts").get(options.account_id)
    login, _ = WindowsCredentialVault(root / "system/credentials").load(
        account.credential_reference
    )
    sdk = importlib.import_module("MetaTrader5")
    try:
        if not sdk.initialize(path=account.terminal_path, timeout=5000):
            raise ValueError("TERMINAL_NOT_AVAILABLE")
        observed, terminal = sdk.account_info(), sdk.terminal_info()
        if (
            observed is None
            or terminal is None
            or not terminal.connected
            or observed.login != int(login)
            or observed.server != account.server
            or observed.trade_mode != sdk.ACCOUNT_TRADE_MODE_DEMO
        ):
            raise ValueError("EXPECTED_AUTHENTICATED_DEMO_IDENTITY_REQUIRED")
        positions, orders = sdk.positions_get(), sdk.orders_get()
        if positions is None or orders is None or positions or orders:
            raise ValueError("ACCOUNT_WIDE_FLAT_OBSERVATION_REQUIRED")
        source = ROOT / "metatrader/Experts/ATSSmallAccount"
        compiled = source / "ATSSmallAccountObserver.ex5"
        sources = list(source.glob("*.mq5")) + list(source.glob("*.mqh"))
        if not compiled.is_file() or compiled.stat().st_mtime < max(
            p.stat().st_mtime for p in sources
        ):
            raise ValueError("CURRENT_METAEDITOR_BUILD_REQUIRED")
        mql = Path(terminal.data_path).resolve() / "MQL5"
        destination = (mql / "Experts/ATSManaged/ATSSmallAccount").resolve()
        if not destination.is_relative_to(mql.resolve() / "Experts"):
            raise ValueError("INSTALL_DESTINATION_INVALID")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        recovery = ROOT / "reports/small-account-research/native-install-recovery" / stamp
        recovery.mkdir(parents=True)
        # Preserve the active profile so the previous chart attachment is recoverable.
        charts = mql / "Profiles/Charts"
        if charts.is_dir():
            shutil.copytree(charts, recovery / "charts")
        if destination.exists():
            shutil.copytree(destination, recovery / "previous-observer")
        destination.mkdir(parents=True, exist_ok=True)
        files = sources + [compiled, source / "README.md"]
        files += list((source / "presets").glob("*.set"))
        files += list((source / "presets").glob("*.json"))
        installed = {}
        for path in files:
            relative = path.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if digest(target) != digest(path):
                raise ValueError("INSTALL_CONTENT_MISMATCH")
            installed[str(relative)] = digest(path)
        if options.build_s3_profile:
            preset = SmallAccountPreset.model_validate_json(
                (source / "presets/gold-triple-s3-1000-v3.json").read_text()
            )
            if observed.currency != preset.account_currency or observed.equity != 1000:
                raise ValueError("RESEARCH_PROFILE_REQUIRES_1000_USD_DEMO_START")
            profile_text = (source / "ATSSmallAccountObserver.mq5").read_text()
            for key, value in preset.native_inputs(
                account.account_id, account.broker_symbol
            ).items():
                pattern = rf"(input\s+(string|bool|int|double)\s+{re.escape(key)}\s*=)[^;]*;"
                match = re.search(pattern, profile_text)
                if match is None:
                    raise ValueError("NATIVE_PROFILE_INPUT_NOT_FOUND")
                literal = json.dumps(value) if match.group(2) == "string" else value
                profile_text, count = re.subn(
                    pattern, lambda m, literal=literal: m.group(1) + literal + ";", profile_text
                )
                if count != 1:
                    raise ValueError("AMBIGUOUS_NATIVE_PROFILE_INPUT")
            profile = destination / "ATSSmallAccountS3_1000.mq5"
            profile.write_text(profile_text, encoding="utf-8")
            log = recovery / "profile-build.log"
            build_process = subprocess.run(
                [
                    r"C:\Program Files\MetaTrader 5\metaeditor64.exe",
                    f"/compile:{profile}",
                    f"/log:{log}",
                ],
                check=False,
                timeout=60,
            )
            build = log.read_text(encoding="utf-16")
            binary = profile.with_suffix(".ex5")
            if "0 errors, 0 warnings" not in build or not binary.is_file():
                raise ValueError("NATIVE_PROFILE_BUILD_NOT_GREEN")
            installed[profile.name], installed[binary.name] = digest(profile), digest(binary)
        report = {
            "installed_at_utc": datetime.now(UTC).isoformat(),
            "account_id": account.account_id,
            "account_mode": "DEMO",
            "balance_observed": observed.balance,
            "equity_observed": observed.equity,
            "positions_observed": len(positions),
            "orders_observed": len(orders),
            "native_algo_allowed": terminal.trade_allowed,
            "destination": str(destination),
            "recovery": str(recovery),
            "files": installed,
            "attached": False,
            "orders_submitted": 0,
            "execution_authority": "NONE",
        }
        if options.build_s3_profile:
            report["compiler"] = {
                "return_code": build_process.returncode,
                "result": "0 errors, 0 warnings",
                "log": str(log),
            }
        output = ROOT / "reports/small-account-research/native-install.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "installed_files": len(installed),
                    "destination": str(destination),
                    "account_mode": "DEMO",
                    "attached": False,
                    "orders_submitted": 0,
                }
            )
        )
    finally:
        sdk.shutdown()


if __name__ == "__main__":
    main()
