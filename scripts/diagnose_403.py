"""One minimal, safe request to classify the Upstox HTTP 403 (mission section 2).

Captures sanitized response ONLY: status, Upstox error code/category, Retry-After,
rate-limit headers, endpoint, timestamp, body fields. Never prints the token or
Authorization header. Aborts immediately after one request.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import winreg
from datetime import UTC, datetime
from pathlib import Path

token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
if not token:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        token = winreg.QueryValueEx(k, "ATS_UPSTOX_ACCESS_TOKEN")[0]
    except Exception:
        token = ""


# Sanitizer: never leak token anywhere
def redact(msg: str) -> str:
    return msg.replace(token, "<REDACTED>") if token else msg


BASE = "https://api.upstox.com/v2"
# One minimal request: underlying historical candle, single day, small payload.
instrument = urllib.parse.quote("NSE_INDEX|Nifty 50")
url = f"{BASE}/historical-candle/{instrument}/1minute/2026-08-25/2026-08-25"
req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ATS-Research-Client/1.0",
    },
)

ts = datetime.now(UTC).isoformat()
classification = "UNKNOWN_403"
status = None
headers_out = {}
body_fields = {}
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = resp.status
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        headers_out = {
            k: v
            for k, v in resp.headers.items()
            if k.lower()
            in {
                "retry-after",
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
                "x-ratelimit-reset",
                "x-ratelimit-reset-epoch",
                "date",
            }
        }
        body_fields = {k: v for k, v in data.items() if k != "data"}
        classification = "OK"
except urllib.error.HTTPError as e:
    status = e.code
    raw = e.read().decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw[:300]}
    headers_out = {
        k: v
        for k, v in e.headers.items()
        if k.lower()
        in {
            "retry-after",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "x-ratelimit-reset-epoch",
            "date",
        }
    }
    body_fields = {k: v for k, v in data.items() if k != "data"}
    if status == 403:
        # Refine classification from error envelope if present
        errs = data.get("errors") or []
        msg = str(data.get("message", "")).lower()
        code = str(data.get("code", "")).lower()
        combined = f"{msg} {code} {errs}".lower()
        if "rate" in combined or "too many" in combined or "throttle" in combined:
            classification = "RATE_LIMIT"
        elif "quota" in combined or "limit exceeded" in combined or "daily" in combined:
            classification = "DAILY_QUOTA"
        elif "permission" in combined or "scope" in combined or "unauthorized" in combined:
            classification = "TOKEN_PERMISSION"
        elif "expired" in combined or "invalid token" in combined or "token expired" in combined:
            classification = "TOKEN_EXPIRED"
        elif "static ip" in combined or "ip" in combined:
            classification = "STATIC_IP_REQUIREMENT"
        elif "not allowed" in combined or "endpoint" in combined or "restricted" in combined:
            classification = "ENDPOINT_RESTRICTION"
        elif "entitlement" in combined or "subscription" in combined or "plan" in combined:
            classification = "ACCOUNT_ENTITLEMENT"
        else:
            classification = "UNKNOWN_403"
    elif status == 400:
        classification = "REQUEST_FORMAT"
    elif status == 429:
        classification = "RATE_LIMIT"

report = {
    "probe_timestamp_utc": ts,
    "endpoint": url,
    "http_status": status,
    "classification": classification,
    "response_headers": headers_out,
    "error_body_fields": redact(json.dumps(body_fields))
    if isinstance(body_fields, str)
    else {k: redact(str(v)) for k, v in body_fields.items()},
}
out = Path("data/raw/upstox/provider_failure_report.json")
out.parent.mkdir(parents=True, exist_ok=True)
# merge into existing failure report list
if out.exists():
    try:
        existing = json.loads(out.read_text())
        if isinstance(existing, list):
            existing.append(report)
        else:
            existing = [existing, report]
    except Exception:
        existing = [report]
else:
    existing = [report]
out.write_text(json.dumps(existing, indent=2), encoding="utf-8")
print("CLASSIFICATION:", classification, "STATUS:", status)
print("HEADERS:", json.dumps(headers_out))
print("BODY:", json.dumps(report["error_body_fields"])[:400])
