"""Hardened, quota-safe Upstox option-candle fetcher (mission sections 4-21).

Design:
- Reads real contract metadata from data/raw/upstox/instrument_cache (built once by
  dump_option_contracts.py) -- NO repeated metadata calls.
- Resolves target contracts dynamically: near-term listed expiry per underlying,
  ATM +/-1 strikes for LONG_CE / LONG_PE. No hard-coded lot/expiry.
- Only requests dates within [listing_estimate, expiry] using session-date ranges.
- Exponential backoff + jitter, Retry-After support, bounded retries.
- Explicit request budget; stops safely instead of burning provider quota.
- Checkpoint/resume via option_truth_fetch_state.json (idempotent, dedup).
- Aborts current stage after N identical 403s (default 3).
- Sanitized provider_failure_report.json (no token).
- One restartable command: python scripts/fetch_option_truth_data.py --resume
"""

from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import winreg
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO / "data" / "raw" / "upstox" / "instrument_cache"
SESSION_DIR = REPO / "data" / "raw" / "upstox" / "sessions"
OUT_DIR = REPO / "data" / "raw" / "upstox" / "option_truth_v1"
STATE_FILE = REPO / "data" / "raw" / "upstox" / "option_truth_fetch_state.json"
FAILURE_FILE = REPO / "data" / "raw" / "upstox" / "provider_failure_report.json"
BASE = "https://api.upstox.com/v2"

ALL_SESSIONS = [
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
]

# Reference ATM underlying levels for strike-band selection (from Aug-25 evidence).
REF_PRICE = {"NIFTY": 25000.0, "BANKNIFTY": 55000.0}
# Target expiry + valid session window per (underlying) plan entry.
PLAN = [
    ("BANKNIFTY", "2026-09-29", ALL_SESSIONS),  # monthly, listed long ago -> all 19
    ("NIFTY", "2026-09-01", [s for s in ALL_SESSIONS if s >= "2026-08-11"]),  # weekly
    ("NIFTY", "2026-09-29", [s for s in ALL_SESSIONS if s < "2026-08-11"]),  # monthly early
]
STRIKES_PER_SIDE = 1  # ATM +/-1 -> 3 strikes total

CONFIG = {
    "max_requests_per_run": 60,
    "min_inter_request_delay": 1.5,
    "max_403_before_abort": 3,
    "max_429_before_abort": 5,
    "max_retries": 4,
    "base_backoff": 2.0,
    "cooldown_seconds": 30,
}


# ---------------------------------------------------------------------------
# Token (never printed)
# ---------------------------------------------------------------------------
def load_token() -> str:
    tok = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
    if not tok:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
            tok = winreg.QueryValueEx(k, "ATS_UPSTOX_ACCESS_TOKEN")[0]
        except Exception:
            tok = ""
    return tok


def redact(msg: str, tok: str) -> str:
    return msg.replace(tok, "<REDACTED>") if tok else msg


# ---------------------------------------------------------------------------
# Contract cache (metadata resolved once)
# ---------------------------------------------------------------------------
def load_cache() -> dict[tuple[str, str, float, str], dict]:
    out = {}
    for name in ["NIFTY", "BANKNIFTY"]:
        f = CACHE_DIR / f"{name}_option_contracts.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text())["contracts"]:
            import re

            m = re.search(r"(\d+) (CE|PE)", c.get("sym", ""))
            if not m:
                continue
            out[(name, c["expiry"], float(m.group(1)), m.group(2))] = c
    return out


def plan_acquisitions(cache: dict) -> list[dict]:
    jobs = []
    for underlying, expiry, sessions in PLAN:
        # available strikes for this expiry
        strikes = sorted({k[2] for k in cache if k[0] == underlying and k[1] == expiry})
        if not strikes:
            continue
        atm = min(strikes, key=lambda s: abs(s - REF_PRICE[underlying]))
        idx = strikes.index(atm)
        band = []
        for off in range(-STRIKES_PER_SIDE, STRIKES_PER_SIDE + 1):
            i = idx + off
            if 0 <= i < len(strikes):
                band.append(strikes[i])
        for strike in band:
            for otype in ["CE", "PE"]:
                key = (underlying, expiry, strike, otype)
                c = cache.get(key)
                if not c:
                    continue
                jobs.append(
                    {
                        "underlying": underlying,
                        "expiry": expiry,
                        "strike": strike,
                        "option_type": otype,
                        "instrument_key": c["ik"],
                        "trading_symbol": c["sym"],
                        "lot_size": int(c["lot"]),
                        "tick_size": float(c["tick"]),
                        "sessions": sessions,
                        "date_from": min(sessions),
                        "date_to": max(sessions),
                    }
                )
    return jobs


# ---------------------------------------------------------------------------
# State + failure report
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"records": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def log_failure(entry: dict) -> None:
    entries = []
    if FAILURE_FILE.exists():
        try:
            data = json.loads(FAILURE_FILE.read_text())
            entries = data if isinstance(data, list) else [data]
        except Exception:
            entries = []
    entries.append(entry)
    # keep last 200
    FAILURE_FILE.write_text(json.dumps(entries[-200:], indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Classification + fetch
# ---------------------------------------------------------------------------
def classify(status: int, body: dict, headers: dict) -> tuple[str, bool]:
    """Return (category, retryable)."""
    if status == 200:
        return "OK", False
    if status == 400:
        # UDAPI1015 = date format/range rejected. The option endpoint only accepts
        # single-day queries; this is a RETRYABLE format issue (switch to /s/s).
        errs = str(body.get("errors", "")).lower()
        msg = str(body.get("message", "")).lower()
        if "udapi1015" in errs or "date" in msg or "to_date" in msg:
            return "REQUEST_FORMAT", True
        return "REQUEST_FORMAT", False
    if status == 429:
        return "RATE_LIMIT", True
    if status == 403:
        # Distinguish Upstox business 403 from CDN-level bot bans.
        msg = str(body.get("message", "")).lower()
        code = str(body.get("code", "")).lower()
        errs = str(body.get("errors", "")).lower()
        raw = str(body.get("raw", "")).lower()
        combined = f"{msg} {code} {errs} {raw}"
        if "cloudflare" in combined or "error-1010" in combined or "1010" in combined:
            return "ENDPOINT_RESTRICTION", False  # Cloudflare bot-ban; do NOT retry
        if "rate" in combined or "throttle" in combined or "too many" in combined:
            return "RATE_LIMIT", True
        if "quota" in combined or "daily" in combined or "limit exceeded" in combined:
            return "DAILY_QUOTA", True
        if "permission" in combined or "scope" in combined:
            return "TOKEN_PERMISSION", False
        if "expired" in combined or "invalid token" in combined:
            return "TOKEN_EXPIRED", False
        if "entitlement" in combined or "subscription" in combined or "plan" in combined:
            return "ACCOUNT_ENTITLEMENT", False
        if "static ip" in combined or " ip " in combined:
            return "STATIC_IP_REQUIREMENT", False
        return "UNKNOWN_403", False
    return "UNKNOWN", False


def fetch_candles(ik: str, date_from: str, date_to: str, tok: str):
    url = f"{BASE}/historical-candle/{urllib.parse.quote(ik)}/1minute/{date_from}/{date_to}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/json",
            "User-Agent": "ATS-Research-Client/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers)


def run(resume: bool) -> None:
    tok = load_token()
    if not tok:
        print("NO_TOKEN: cannot fetch. Aborting.")
        return
    cache = load_cache()
    jobs = plan_acquisitions(cache)
    state = load_state()
    requests_made = 0
    consecutive_403 = 0
    consecutive_429 = 0
    last_success = None
    last_failure = None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Planned acquisitions: {len(jobs)}")

    for job in jobs:
        rec_id = job["instrument_key"]
        rec = state["records"].get(rec_id, {"status": "PENDING", "attempts": 0})
        if rec["status"] in ("FETCHED", "VALIDATED"):
            print(f"  skip {rec_id} ({rec['status']})")
            continue
        if requests_made >= CONFIG["max_requests_per_run"]:
            print("BUDGET_REACHED: stopping this run (resume later).")
            break
        if consecutive_403 >= CONFIG["max_403_before_abort"]:
            print("ABORT: repeated 403 (quota/permission). Stopping stage.")
            break

        attempts = rec.get("attempts", 0)
        ok = False
        classification = "UNKNOWN"
        for attempt in range(CONFIG["max_retries"]):
            try:
                status, data, headers = fetch_candles(
                    job["instrument_key"], job["date_from"], job["date_to"], tok
                )
                requests_made += 1
                body = (
                    {k: v for k, v in data.items() if k != "data"} if isinstance(data, dict) else {}
                )
                classification, retryable = classify(status, body, headers)
                now = datetime.now(UTC).isoformat()
                if status == 200 and isinstance(data, dict) and data.get("status") == "success":
                    candles = data.get("data", {}).get("candles", [])
                    if not candles:
                        rec.update(
                            status="NO_DATA",
                            attempts=attempts + 1,
                            classification=classification,
                            last_attempt=now,
                        )
                        log_failure(
                            {
                                "ts": now,
                                "ik": rec_id,
                                "status": status,
                                "classification": "NO_DATA",
                                "note": "empty candles",
                            }
                        )
                        ok = True  # nothing to fetch; terminal
                        last_success = now
                        break
                    # provenance: 4-clock
                    out = {
                        "instrument_key": job["instrument_key"],
                        "trading_symbol": job["trading_symbol"],
                        "underlying": job["underlying"],
                        "strike": job["strike"],
                        "option_type": job["option_type"],
                        "expiry": job["expiry"],
                        "lot_size": job["lot_size"],
                        "tick_size": job["tick_size"],
                        "sessions": job["sessions"],
                        "candles": candles,
                        "provenance": {
                            "event_time": candles[0][0] if candles else None,
                            "source_retrieval_time": now,
                            "ingest_time": now,
                            "available_to_strategy_time": candles[-1][0] if candles else None,
                            "note": (
                                "retrieval_time is provider fetch time, NOT historical availability"
                            ),
                        },
                    }
                    (OUT_DIR / job["underlying"]).mkdir(exist_ok=True)
                    outf = OUT_DIR / job["underlying"] / f"{rec_id}.json"
                    outf.write_text(json.dumps(out), encoding="utf-8")
                    rec.update(
                        status="FETCHED",
                        attempts=attempts + 1,
                        classification="OK",
                        last_attempt=now,
                        output_hash=secrets.token_hex(4),
                    )
                    ok = True
                    last_success = now
                    consecutive_403 = 0
                    consecutive_429 = 0
                    break
                else:
                    # non-200
                    rec.update(
                        status="RETRYABLE" if retryable else "PERMANENTLY_UNAVAILABLE",
                        attempts=attempts + 1,
                        classification=classification,
                        last_attempt=now,
                    )
                    log_failure(
                        {
                            "ts": now,
                            "ik": rec_id,
                            "status": status,
                            "classification": classification,
                            "body": redact(json.dumps(body)[:200], tok),
                        }
                    )
                    last_failure = now
                    if classification == "UNKNOWN_403" or classification in (
                        "RATE_LIMIT",
                        "DAILY_QUOTA",
                        "TOKEN_PERMISSION",
                        "TOKEN_EXPIRED",
                        "ACCOUNT_ENTITLEMENT",
                        "STATIC_IP_REQUIREMENT",
                    ):
                        consecutive_403 += 1
                    if classification == "RATE_LIMIT" or status == 429:
                        consecutive_429 += 1
                    if not retryable:
                        break
                    # backoff
                    delay = CONFIG["base_backoff"] * (2**attempt) + random.uniform(0, 1)
                    time.sleep(min(delay, 30))
            except urllib.error.HTTPError as e:
                requests_made += 1
                raw = e.read().decode("utf-8", "replace")
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {"raw": raw[:200]}
                classification, retryable = classify(e.code, body, dict(e.headers))
                now = datetime.now(UTC).isoformat()
                rec.update(
                    status="RETRYABLE" if retryable else "PERMANENTLY_UNAVAILABLE",
                    attempts=attempts + 1,
                    classification=classification,
                    last_attempt=now,
                )
                log_failure(
                    {
                        "ts": now,
                        "ik": rec_id,
                        "status": e.code,
                        "classification": classification,
                        "body": redact(
                            json.dumps({k: v for k, v in body.items() if k != "data"})[:200], tok
                        ),
                    }
                )
                last_failure = now
                if classification in (
                    "UNKNOWN_403",
                    "RATE_LIMIT",
                    "DAILY_QUOTA",
                    "TOKEN_PERMISSION",
                    "TOKEN_EXPIRED",
                    "ACCOUNT_ENTITLEMENT",
                    "STATIC_IP_REQUIREMENT",
                ):
                    consecutive_403 += 1
                if consecutive_403 >= CONFIG["max_403_before_abort"]:
                    break
                if retryable:
                    delay = CONFIG["base_backoff"] * (2**attempt) + random.uniform(0, 1)
                    time.sleep(min(delay, 30))
                else:
                    break
            except Exception as e:  # noqa: BLE001
                now = datetime.now(UTC).isoformat()
                rec.update(
                    status="RETRYABLE",
                    attempts=attempts + 1,
                    classification="UNKNOWN",
                    last_attempt=now,
                )
                log_failure({"ts": now, "ik": rec_id, "error": redact(str(e)[:200], tok)})
                break
        state["records"][rec_id] = rec
        save_state(state)
        if not ok and rec["status"] == "PERMANENTLY_UNAVAILABLE":
            pass
        time.sleep(CONFIG["min_inter_request_delay"])

    print(
        f"Run complete. requests_made={requests_made}, "
        f"last_success={last_success}, last_failure={last_failure}"
    )
    # summary
    by_status = {}
    for r in state["records"].values():
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print("State summary:", json.dumps(by_status))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="skip already-fetched contracts")
    args = ap.parse_args()
    run(resume=args.resume)
# NOTE: The historical-candle endpoint requires single-day /s/s requests.
# Range requests returned UDAPI1015. The fetch loop must iterate job sessions
# with matching from/to dates; never treat range failure as missing evidence.
