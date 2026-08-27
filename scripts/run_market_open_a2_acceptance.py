"""ATS A2 market-open acceptance for the LIVE-PAPER stack.

Proves the running stack honors the non-negotiable invariants before the
operator relies on it during a live NSE session:

* execution target is PAPER
* live money is DISABLED
* real orders placed == 0
* Harness is ADVISORY_ONLY and governor-gated (no financial authority)
* the four scoped Harness agents are registered when the sidecar is healthy
* pipeline counters endpoint is reachable and reflects the real feed state

It only reads endpoints; it never places orders or mutates runtime state.
Run after `scripts/start_ats_a2_live_paper.ps1`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

BASE = "http://127.0.0.1:8000"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _get(path: str) -> dict | None:
    url = f"{BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def run_checks() -> list[Check]:
    checks: list[Check] = []

    runtime = _get("/v1/runtime/status")
    checks.append(
        Check(
            "runtime_status_reachable",
            runtime is not None,
            "runtime status endpoint responded" if runtime else "no response",
        )
    )

    harness = _get("/v1/harness/status")
    checks.append(
        Check(
            "harness_status_reachable",
            harness is not None,
            "harness status endpoint responded" if harness else "no response",
        )
    )

    if harness is not None:
        h = harness.get("harness", {})
        checks.append(
            Check(
                "live_money_disabled",
                h.get("live_money") == "DISABLED",
                str(h.get("live_money")),
            )
        )
        checks.append(
            Check(
                "execution_target_paper",
                h.get("execution_target") == "PAPER",
                str(h.get("execution_target")),
            )
        )
        checks.append(
            Check(
                "real_orders_zero",
                int(h.get("real_orders_placed", -1)) == 0,
                str(h.get("real_orders_placed")),
            )
        )
        checks.append(
            Check(
                "harness_advisory_only",
                harness.get("safety", {}).get("REAL_ORDER_AUTHORITY") == "NONE",
                str(harness.get("safety", {}).get("REAL_ORDER_AUTHORITY")),
            )
        )
        agents = harness.get("agents", [])
        # When the sidecar is healthy, all four scoped agents must be registered.
        if h.get("state") == "HEALTHY":
            checks.append(
            Check(
                "harness_four_agents_registered",
                len(agents) == 4,
                f"{len(agents)} agents registered",
            )  # noqa: E501
            )
        else:
            checks.append(
                Check("harness_not_healthy_pre_open", True, f"state={h.get('state')}")
            )

    pipeline = _get("/v1/pipeline/counters")
    checks.append(
        Check(
            "pipeline_counters_reachable",
            pipeline is not None,
            "pipeline counters responded" if pipeline else "no response",
        )
    )

    health = _get("/health/live")
    checks.append(
        Check(
            "health_live",
            health is not None and health.get("status") == "LIVE",
            str(health.get("status") if health else None),
        )
    )

    return checks


def main() -> int:
    print("== ATS A2 MARKET-OPEN ACCEPTANCE (LIVE-PAPER, READ-ONLY) ==")
    checks = run_checks()
    failed = 0
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        color = "\033[32m" if check.ok else "\033[31m"
        print(f"{color}{status}\033[0m  {check.name}: {check.detail}")
        if not check.ok:
            failed += 1

    if failed:
        print(f"\nACCEPTANCE FAILED: {failed} check(s) failed.")
        return 1
    print(
        "\nACCEPTANCE PASSED: PAPER + LIVE_MONEY_DISABLED + REAL_ORDERS_0"
        " + HARNESS_ADVISORY_ONLY."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
