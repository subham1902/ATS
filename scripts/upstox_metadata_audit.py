"""Round-2 capability audit: resolve instrument METADATA for option keys.

Goal: find a read-only way to map instrument_key -> strike/expiry/CE-PE/lot_size/tick_size.
Never prints the token.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import winreg
from pathlib import Path

token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
if not token:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        token = winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0]
    except Exception:
        token = ""


def redact(msg: str) -> str:
    return msg.replace(token, "<REDACTED>") if token else msg


BASE = "https://api.upstox.com/v2"


def get_raw(url: str, binary: bool = False, timeout: int = 30):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ATS-Research-Client/1.0",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return data if binary else json.loads(data.decode("utf-8"))


def try_endpoint(label: str, url: str, binary: bool = False):
    if not token:
        return {label: "NO_TOKEN"}
    try:
        data = get_raw(url, binary=binary)
        if binary:
            text = data.decode("utf-8", "replace")
            lines = text.splitlines()
            return {
                label: "AVAILABLE_BINARY",
                "first_line": lines[0][:200] if lines else "",
                "num_lines": len(lines),
            }
        if isinstance(data, dict) and data.get("status") == "error":
            return {
                label: "API_ERROR",
                "detail": redact(str(data.get("errors", data.get("message", ""))))[:200],
            }
        return {label: "AVAILABLE", "sample": json.dumps(data, default=str)[:600]}
    except urllib.error.HTTPError as e:
        return {label: f"HTTP_{e.code}", "reason": redact(str(e.reason))[:150]}
    except Exception as e:  # noqa: BLE001
        return {label: "ERR", "reason": redact(str(e))[:200]}


# 1. Expiry list for BANKNIFTY
exp_bn = try_endpoint(
    "option_contract_BANKNIFTY",
    f"{BASE}/option/contract?instrument_key={urllib.parse.quote('NSE_INDEX|Nifty Bank')}",
)
print("EXPIRIES BANKNIFTY:", json.dumps(exp_bn)[:500])

# 2. Single instrument metadata by key
inst_69824 = try_endpoint(
    "instrument_meta_69824", f"{BASE}/market-quote/instrument/{urllib.parse.quote('NSE_FO|69824')}"
)
print("INST 69824:", json.dumps(inst_69824)[:600])

# 3. Option chain for BANKNIFTY with a plausible expiry (will fix after seeing expiries)
chain = try_endpoint(
    "option_chain_2026-08-27",
    f"{BASE}/option/option-chain?instrument_key={urllib.parse.quote('NSE_INDEX|Nifty Bank')}&expiry_date=2026-08-27",
)
print("CHAIN 0827:", json.dumps(chain)[:600])

# 4. Instrument master csv
master = try_endpoint(
    "instrument_master_csv", f"{BASE}/market-quote/instrument/master?format=csv", binary=True
)
print("MASTER CSV:", json.dumps(master)[:300])

# 5. Instrument master json
master_j = try_endpoint(
    "instrument_master_json", f"{BASE}/market-quote/instrument/master?format=json", binary=True
)
print("MASTER JSON:", json.dumps(master_j)[:200])

report = {
    "option_contract_BANKNIFTY": exp_bn,
    "instrument_meta_69824": inst_69824,
    "option_chain_2026-08-27": chain,
    "instrument_master_csv": master,
    "instrument_master_json": master_j,
}
out = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "raw"
    / "upstox"
    / "capability_audit_metadata.json"
)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"\nWrote {out}")
