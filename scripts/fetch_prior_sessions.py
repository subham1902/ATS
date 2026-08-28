"""Fetch raw historical underlying candles for prior sessions from Upstox Analytics API."""

from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
import winreg
from pathlib import Path

sessions = [
    "2026-08-24",
    "2026-08-21",
    "2026-08-20",
    "2026-08-19",
    "2026-08-18",
    "2026-08-17",
    "2026-08-14",
    "2026-08-13",
    "2026-08-12",
    "2026-08-11",
    "2026-08-10",
    "2026-08-07",
    "2026-08-06",
    "2026-08-05",
    "2026-08-04",
]

token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
if not token:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
    token = winreg.QueryValueEx(key, "ATS_UPSTOX_ACCESS_TOKEN")[0]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "User-Agent": "ATS-Research-Client/1.0",
}

data_root = Path(r"D:\Projects\ATS\ats\data\raw\upstox\sessions")

for s in sessions:
    s_dir = data_root / s
    s_dir.mkdir(parents=True, exist_ok=True)

    nifty_file = s_dir / "NIFTY_underlying.json"
    if not nifty_file.exists():
        url = f"https://api.upstox.com/v2/historical-candle/{urllib.parse.quote('NSE_INDEX|Nifty 50')}/1minute/{s}/{s}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            nifty_file.write_bytes(resp.read())
        time.sleep(0.1)

    bn_file = s_dir / "BANKNIFTY_underlying.json"
    if not bn_file.exists():
        url = f"https://api.upstox.com/v2/historical-candle/{urllib.parse.quote('NSE_INDEX|Nifty Bank')}/1minute/{s}/{s}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            bn_file.write_bytes(resp.read())
        time.sleep(0.1)

    print(f"Fetched/Verified {s}: NIFTY & BANKNIFTY 1m candles saved.")
