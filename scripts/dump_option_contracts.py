"""Dump full option/contract listings for NIFTY and BANKNIFTY to local files.

This gives real instrument_key + strike/expiry/type/lot/tick for resolver use.
Never prints token. Saves compact JSON for offline analysis.
"""

from __future__ import annotations

import json
import os
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

BASE = "https://api.upstox.com/v2"


def get_json(url: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ATS-Research-Client/1.0",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


out_dir = Path(__file__).resolve().parents[1] / "data" / "raw" / "upstox" / "instrument_cache"
out_dir.mkdir(parents=True, exist_ok=True)

for name, idx in [("NIFTY", "NSE_INDEX|Nifty 50"), ("BANKNIFTY", "NSE_INDEX|Nifty Bank")]:
    url = f"{BASE}/option/contract?instrument_key={urllib.parse.quote(idx)}"
    data = get_json(url)
    arr = data.get("data", [])
    # keep only fields we need, and parse trading_symbol
    compact = []
    for c in arr:
        ts = c.get("trading_symbol", "")
        compact.append(
            {
                "ik": c.get("instrument_key"),
                "sym": ts,
                "expiry": c.get("expiry"),
                "weekly": c.get("weekly"),
                "type": c.get("instrument_type"),
                "tick": c.get("tick_size"),
                "lot": c.get("lot_size"),
                "exchange_token": c.get("exchange_token"),
            }
        )
    f = out_dir / f"{name}_option_contracts.json"
    f.write_text(
        json.dumps({"count": len(compact), "contracts": compact}, indent=2), encoding="utf-8"
    )
    # show summary of expiries present
    expiries = sorted({c["expiry"] for c in compact if c["expiry"]})
    print(f"{name}: {len(compact)} contracts; expiries sample: {expiries[:12]}")
    print(f"  saved -> {f}")
