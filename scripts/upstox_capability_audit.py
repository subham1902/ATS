"""Read-only audit of Upstox historical OPTION capability.

Uses the same token source as scripts/fetch_prior_sessions.py (env or Windows
registry) but NEVER prints the token. Classifies each capability as
AVAILABLE / AVAILABLE_WITH_LIMITATIONS / NOT_AVAILABLE and writes a JSON report.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import winreg
from pathlib import Path

# --- token (do NOT print) -------------------------------------------------
token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
if not token:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        token = winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0]
    except Exception:
        token = ""


# Redact any accidental leakage in exception text below.
def redact(msg: str) -> str:
    if token:
        msg = msg.replace(token, "<REDACTED>")
    return msg


BASE = "https://api.upstox.com/v2"


def get_json(url: str, timeout: int = 30):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ATS-Research-Client/1.0",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def classify(name: str, url: str, notes: str = ""):
    if not token:
        return {
            "capability": name,
            "status": "NOT_AVAILABLE",
            "reason": "NO_TOKEN",
            "url": url,
            "notes": notes,
        }
    try:
        data = get_json(url)
        # Upstox error envelope: {"status":"error","errors":[...]}
        if isinstance(data, dict) and data.get("status") == "error":
            err = redact(str(data.get("errors", data.get("message", ""))))
            return {
                "capability": name,
                "status": "NOT_AVAILABLE",
                "reason": f"API_ERROR:{err}",
                "url": url,
                "notes": notes,
            }
        return {
            "capability": name,
            "status": "AVAILABLE",
            "reason": "OK",
            "url": url,
            "notes": notes,
            "sample_keys": list(data.keys())[:8] if isinstance(data, dict) else "list",
        }
    except urllib.error.HTTPError as e:
        return {
            "capability": name,
            "status": "NOT_AVAILABLE",
            "reason": f"HTTP_{e.code}:{redact(e.reason)}",
            "url": url,
            "notes": notes,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "capability": name,
            "status": "NOT_AVAILABLE",
            "reason": redact(str(e))[:300],
            "url": url,
            "notes": notes,
        }


results = []
underlying_key = urllib.parse.quote("NSE_INDEX|Nifty 50")
banknifty_key = urllib.parse.quote("NSE_INDEX|Nifty Bank")
option_key = urllib.parse.quote("NSE_FO|69824")

# 1. Control: underlying historical candle (known to work)
results.append(
    classify(
        "historical_candle_underlying",
        f"{BASE}/historical-candle/{underlying_key}/1minute/2026-08-25/2026-08-25",
        "Control probe; should be AVAILABLE.",
    )
)

# 2. Option historical candle for a known real instrument key (NSE_FO|69824)
results.append(
    classify(
        "historical_candle_option",
        f"{BASE}/historical-candle/{option_key}/1minute/2026-08-25/2026-08-25",
        "Real BANKNIFTY option key from local 2026-08-25 evidence; tests refetchability.",
    )
)

# 3. Option contract (expiry list) for BANKNIFTY
results.append(
    classify(
        "option_contract_expiries",
        f"{BASE}/option/contract?instrument_key={banknifty_key}",
        "Returns available expiry dates for underlying; needed to resolve historical expiries.",
    )
)

# 4. Option chain (live) for BANKNIFTY at a known expiry (informational)
results.append(
    classify(
        "option_chain_live",
        f"{BASE}/option/option-chain?instrument_key={banknifty_key}&expiry_date=2026-08-27",
        "Live option chain; informational only (not historical).",
    )
)

# 5. Instruments master (resolve strike/expiry/CE-PE/lot/tick for expired keys)
results.append(
    classify(
        "instrument_master",
        f"{BASE}/market-quote/instrument/master?format=json",
        "Master resolves historical strike, expiry, type, lot size, and tick size.",
    )
)

# 6. Intraday candle for option (determines if intraday option history available)
results.append(
    classify(
        "intraday_candle_option",
        f"{BASE}/historical-candle/{option_key}/1minute/2026-08-25/2026-08-25",
        "Same as #2 (intraday minute candle for option).",
    )
)

report = {
    "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "token_present": bool(token),
    "capabilities": results,
}
out = Path(__file__).resolve().parents[1] / "data" / "raw" / "upstox" / "capability_audit.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Audit complete. Token present: {bool(token)}. Report -> {out}")
for r in results:
    print(f"  {r['capability']:28s} -> {r['status']:22s} {r.get('reason', '')[:80]}")
