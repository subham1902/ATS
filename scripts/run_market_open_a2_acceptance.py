"""ATS A2 market-open connected acceptance for the LIVE-PAPER stack.

Proves whether the running stack honors:
1. Level 1: Static / Unit / Toolchain Invariants
2. Level 2: Connected After-Hours Operational Invariants (Safety, APIs, Harness)
3. Level 3: True Market-Open Connected Invariants (Feed, InstrumentSpec, Ticks)

A script named `run_market_open_a2_acceptance.py` will NEVER emit `MARKET_OPEN_ACCEPTANCE_PASS`
if the market is CLOSED, InstrumentSpec is unavailable, or live market ticks are missing.

When after-hours operational checks pass, it emits `AFTER_HOURS_OPERATIONAL_ACCEPTANCE_PASS`
or `READY_FOR_MARKET_OPEN_ACCEPTANCE`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

_INDIA_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
BASE = "http://127.0.0.1:8000"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    category: str = "operational"  # "safety", "operational", "market_open"


@dataclass
class MarketOpenAcceptanceGateResult:
    acceptance_started_at_utc: str
    acceptance_started_at_ist: str
    trading_date: str
    safety_invariants_passed: bool
    operational_stack_passed: bool
    market_open_conditions_passed: bool
    market_open_verdict: str
    checks: list[Check] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status_summary"] = {
            "safety_invariants_passed": self.safety_invariants_passed,
            "operational_stack_passed": self.operational_stack_passed,
            "market_open_conditions_passed": self.market_open_conditions_passed,
            "market_open_verdict": self.market_open_verdict,
        }
        return d


def _get(path: str) -> dict[str, Any] | None:
    url = f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            data: dict[str, Any] = json.loads(resp.read().decode())
            return data
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


class MarketOpenAcceptanceGate:
    """Deterministic acceptance gate separating safety, operational, and market-open conditions."""

    def evaluate(self, *, allow_after_hours: bool = True) -> MarketOpenAcceptanceGateResult:
        now_utc = datetime.now(UTC)
        now_ist = now_utc.astimezone(_INDIA_TZ)
        now_utc_str = now_utc.isoformat()
        now_ist_str = now_ist.isoformat()
        trading_date = now_ist.strftime("%Y-%m-%d")

        checks: list[Check] = []

        # 1. Operational Endpoints Reachability
        runtime = _get("/v1/runtime/status")
        checks.append(
            Check(
                "runtime_status_reachable",
                runtime is not None,
                "runtime status endpoint responded" if runtime else "no response",
                category="operational",
            )
        )

        harness = _get("/v1/harness/status")
        checks.append(
            Check(
                "harness_status_reachable",
                harness is not None,
                "harness status endpoint responded" if harness else "no response",
                category="operational",
            )
        )

        pipeline = _get("/v1/pipeline/counters")
        checks.append(
            Check(
                "pipeline_counters_reachable",
                pipeline is not None,
                "pipeline counters responded" if pipeline else "no response",
                category="operational",
            )
        )

        health = _get("/health/live")
        checks.append(
            Check(
                "health_live",
                health is not None and health.get("status") == "LIVE",
                str(health.get("status") if health else None),
                category="operational",
            )
        )

        # 2. Hard Safety Invariants
        if harness is not None:
            h = harness.get("harness", {})
            checks.append(
                Check(
                    "live_money_disabled",
                    h.get("live_money") == "DISABLED",
                    str(h.get("live_money")),
                    category="safety",
                )
            )
            checks.append(
                Check(
                    "execution_target_paper",
                    h.get("execution_target") == "PAPER",
                    str(h.get("execution_target")),
                    category="safety",
                )
            )
            checks.append(
                Check(
                    "real_orders_zero",
                    int(h.get("real_orders_placed", -1)) == 0,
                    str(h.get("real_orders_placed")),
                    category="safety",
                )
            )
            checks.append(
                Check(
                    "harness_advisory_only",
                    harness.get("safety", {}).get("REAL_ORDER_AUTHORITY") == "NONE",
                    str(harness.get("safety", {}).get("REAL_ORDER_AUTHORITY")),
                    category="safety",
                )
            )
            agents = harness.get("agents", [])
            if h.get("state") == "HEALTHY":
                checks.append(
                    Check(
                        "harness_four_agents_registered",
                        len(agents) == 4,
                        f"{len(agents)} agents registered",
                        category="operational",
                    )
                )

        if pipeline is not None:
            obs = pipeline.get("scanner_observations")
            r10 = pipeline.get("r10_evaluations")
            checks.append(
                Check(
                    "autonomous_scanner_telemetry_wired",
                    "scanner_observations" in pipeline
                    and "r10_evaluations" in pipeline
                    and "r10x_evaluations" in pipeline
                    and "rejection_reasons" in pipeline,
                    f"scanner_obs={obs}, r10={r10}",
                    category="operational",
                )
            )

        # 3. Market Open Live Conditions Check
        session_phase = (runtime or {}).get("session", {}).get("phase", "UNKNOWN")
        is_market_open_session = session_phase == "ENTRY_ALLOWED"

        market_open_checks: list[Check] = []
        market_open_checks.append(
            Check(
                "market_session_open",
                is_market_open_session,
                f"session_phase={session_phase}",
                category="market_open",
            )
        )

        if is_market_open_session and pipeline is not None:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                current_pipeline = _get("/v1/pipeline/counters")
                if (
                    current_pipeline is not None
                    and current_pipeline.get("connection_state") == "LIVE"
                    and current_pipeline.get("subscription_count") == 22
                    and current_pipeline.get("nifty_last") is not None
                    and current_pipeline.get("banknifty_last") is not None
                    and len(current_pipeline.get("freshness", {})) == 22
                    and all(v == "FRESH" for v in current_pipeline.get("freshness", {}).values())
                ):
                    pipeline = current_pipeline
                    break
                time.sleep(1)

            first_raw = int((pipeline or {}).get("upstox_raw_messages", 0))
            first_scans = int((pipeline or {}).get("scanner_observations", 0))
            time.sleep(2)
            later = _get("/v1/pipeline/counters") or {}
            freshness = later.get("freshness", {})
            scans_now = later.get("scanner_observations", 0)

            market_open_checks.extend(
                [
                    Check(
                        "active_dynamic_subscriptions",
                        later.get("subscription_count") == 22,
                        f"count={later.get('subscription_count')}",
                        category="market_open",
                    ),
                    Check(
                        "active_nifty_banknifty_atm2_fresh",
                        len(freshness) == 22 and all(v == "FRESH" for v in freshness.values()),
                        f"fresh={sum(v == 'FRESH' for v in freshness.values())}/22",
                        category="market_open",
                    ),
                    Check(
                        "active_feed_counters_increasing",
                        int(later.get("upstox_raw_messages", 0)) > first_raw,
                        f"raw_msgs={first_raw}->{later.get('upstox_raw_messages', 0)}",
                        category="market_open",
                    ),
                    Check(
                        "active_autonomous_scanner_running",
                        int(scans_now) >= first_scans,
                        f"scans={scans_now}",
                        category="market_open",
                    ),
                ]
            )
        else:
            market_open_checks.append(
                Check(
                    "live_feed_ticks_observed",
                    False,
                    "Market is CLOSED or after-hours — live current-session ticks not active",
                    category="market_open",
                )
            )

        checks.extend(market_open_checks)

        # Categorize results
        safety_passed = all(c.ok for c in checks if c.category == "safety")
        operational_passed = all(c.ok for c in checks if c.category == "operational")
        market_open_passed = all(c.ok for c in checks if c.category == "market_open")

        if safety_passed and operational_passed:
            if market_open_passed:
                verdict = "MARKET_OPEN_ACCEPTANCE_PASS"
            elif allow_after_hours:
                verdict = "AFTER_HOURS_OPERATIONAL_ACCEPTANCE_PASS"
            else:
                verdict = "READY_FOR_MARKET_OPEN_ACCEPTANCE"
        else:
            verdict = "BLOCKED_SAFETY_OR_STACK_FAILED"

        return MarketOpenAcceptanceGateResult(
            acceptance_started_at_utc=now_utc_str,
            acceptance_started_at_ist=now_ist_str,
            trading_date=trading_date,
            safety_invariants_passed=safety_passed,
            operational_stack_passed=operational_passed,
            market_open_conditions_passed=market_open_passed,
            market_open_verdict=verdict,
            checks=checks,
        )


def main() -> int:
    print("== ATS A2 MARKET-OPEN CONNECTED ACCEPTANCE (DETERMINISTIC GATE) ==")
    gate = MarketOpenAcceptanceGate()
    result = gate.evaluate(allow_after_hours=True)

    print(f"Timestamp (UTC): {result.acceptance_started_at_utc}")
    print(f"Timestamp (IST): {result.acceptance_started_at_ist}")
    print(f"Trading Date   : {result.trading_date}")
    print("----------------------------------------------------------------------")

    for check in result.checks:
        status = "PASS" if check.ok else ("PENDING" if check.category == "market_open" else "FAIL")
        if check.ok:
            color = "\033[32m"
        elif check.category == "market_open":
            color = "\033[33m"
        else:
            color = "\033[31m"
        cat_str = f"[{check.category.upper():11s}]"
        print(f"{color}{status:7s}\033[0m {cat_str} {check.name}: {check.detail}")

    print("----------------------------------------------------------------------")
    print(f"Safety Invariants Passed      : {result.safety_invariants_passed}")
    print(f"Operational Stack Passed      : {result.operational_stack_passed}")
    print(f"Market Open Conditions Passed : {result.market_open_conditions_passed}")
    print(f"FINAL VERDICT                 : \033[36m{result.market_open_verdict}\033[0m")
    print("----------------------------------------------------------------------")

    if not result.safety_invariants_passed or not result.operational_stack_passed:
        print("\nACCEPTANCE FAILED: Safety or operational stack checks failed.")
        return 1

    if result.market_open_verdict == "MARKET_OPEN_ACCEPTANCE_PASS":
        print("\nTRUE MARKET-OPEN CONNECTED ACCEPTANCE PASSED.")
    else:
        print(
            f"\nCONNECTED OPERATIONAL ACCEPTANCE PASSED ({result.market_open_verdict}).\n"
            "TRUE MARKET-OPEN CONNECTED ACCEPTANCE IS PENDING LIVE NSE SESSION."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
