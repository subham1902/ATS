"""Start the pinned DeepSeek Harness sidecar and register the four A2 agents.

This is the production wiring for C3: it verifies the vendored harness build,
spawns the isolated ACP process, and registers SESSION_MARKET / POSITION /
PORTFOLIO_ANALYST / RESEARCH agent sessions. The Harness is ADVISORY_ONLY; every
runtime-change proposal is governor-gated. No orders are ever placed.

Usage:
    uv run python scripts/start_a2_harness.py \
        --harness-root tools/deepseek-harness \
        --node toolchains/node-v24.19.0-win-x64/node.exe
"""

from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

from ats.intelligence.harness.harness_integration import build_a2_harness_integration


def main() -> int:
    parser = argparse.ArgumentParser(description="Start A2 DeepSeek Harness sidecar")
    parser.add_argument("--harness-root", type=Path, default=Path("tools/deepseek-harness"))
    parser.add_argument(
        "--node",
        type=Path,
        default=Path("toolchains/node-v24.19.0-win-x64/node.exe"),
    )
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()

    integration = build_a2_harness_integration(
        node_exe=args.node, harness_root=args.harness_root
    )

    if args.check_config:
        print("HARNESS_CONFIG_VALID version=0.1.1-rc.2 authority=ADVISORY_ONLY")
        return 0

    integration.start()
    print(f"HARNESS_STARTED agents={len(integration.agent_sessions)}")

    stop = {"flag": False}

    def _handle(_signum, _frame):  # pragma: no cover
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    try:  # pragma: no cover
        while not stop["flag"]:
            health = integration.adapter.health()
            print(f"HARNESS_HEALTH state={health.state.value} active={health.active_sessions}")
            time.sleep(5)
    finally:  # pragma: no cover
        integration.stop()
        print("HARNESS_STOPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
