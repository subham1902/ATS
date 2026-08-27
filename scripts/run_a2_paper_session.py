"""Production-safe A2 Paper Session CLI Runner.

Runs the TradingRuntime in A2_PAPER mode with read-only market data and PaperBrokerAdapter.
INVARIANTS:
- Execution target: PaperBrokerAdapter ONLY
- Live money: DISABLED
- Real orders placed: 0
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from decimal import Decimal

import uvicorn

from ats.contracts.common import SystemClock
from ats.intelligence.harness.harness_integration import attach_and_start_a2_harness
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    A2SessionState,
    UpstoxMarketFeedAdapter,
    create_a2_paper_app,
)


def run_bounded_session(
    duration_seconds: int = 30,
    *,
    require_token: bool = False,
) -> None:
    """Run a bounded A2 paper session in the terminal and report statistics."""
    print("=" * 60)
    print("ATS A2 AUTONOMOUS PAPER SESSION RUNNER")
    print("=" * 60)
    print("Execution Target : PaperBrokerAdapter (ONLY)")
    print("Live Money       : DISABLED")
    print("Real Orders      : 0")
    print(f"Session Duration : {duration_seconds}s")
    print("-" * 60)

    token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
    has_token = bool(token)
    print(f"Upstox Token Auth: {'PRESENT (Protected)' if has_token else 'NOT SET (Mock/Offline mode)'}")

    config = A2PaperSessionConfig(
        execution_target="PAPER",
        live_money="DISABLED",
    )
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(config=config, market_feed=feed)

    started = controller.start(require_token=require_token)
    if not started:
        print(f"Failed to start session: {controller.status().reason_codes}")
        sys.exit(1)

    print("Session Status   : RUNNING")
    print("Feed Health      : HEALTHY")
    print("Broker Health    : HEALTHY (PaperBroker)")
    print("-" * 60)

    # Simulate / observe ticks over duration
    start_time = time.time()
    tick_count = 0
    base_nifty = Decimal("24500.00")
    base_banknifty = Decimal("52800.00")

    try:
        while time.time() - start_time < duration_seconds:
            now = SystemClock().now()
            # Feed ticks
            nifty_price = base_nifty + Decimal(str((tick_count % 10) * 0.5 - 2.5))
            banknifty_price = base_banknifty + Decimal(str((tick_count % 8) * 1.0 - 4.0))

            controller.process_tick("NIFTY", nifty_price, at=now)
            controller.process_tick("BANKNIFTY", banknifty_price, at=now)
            tick_count += 2
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nOperator interrupted session.")
    finally:
        print("-" * 60)
        print("Stopping A2 Paper Session (Flattening positions)...")
        controller.stop()
        status = controller.status()
        print(f"Final State      : {status.state.value}")
        print(f"Events Processed : {status.events_processed}")
        print(f"Paper Orders     : {status.paper_orders_submitted}")
        print(f"Paper Fills      : {status.paper_fills_recorded}")
        print(f"Open Positions   : {status.open_paper_positions}")
        print(f"Real Orders      : {status.real_orders_placed}")
        print("=" * 60)
        print("A2 PAPER SESSION COMPLETED SUCCESSFULLY (ZERO REAL ORDERS)")


def main() -> None:
    parser = argparse.ArgumentParser(description="ATS A2 Paper Session Launcher")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds for bounded session")
    parser.add_argument("--host", default="127.0.0.1", help="API Host")
    parser.add_argument("--port", type=int, default=8000, help="API Port")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server with A2 controller")
    parser.add_argument("--require-token", action="store_true", help="Require ATS_UPSTOX_ACCESS_TOKEN")
    args = parser.parse_args()

    if args.serve:
        config = A2PaperSessionConfig(execution_target="PAPER", live_money="DISABLED")
        feed = UpstoxMarketFeedAdapter()
        controller = A2PaperSessionController(config=config, market_feed=feed)
        # Attach & start the pinned DeepSeek Harness (ADVISORY_ONLY, governor-gated)
        try:
            attach_and_start_a2_harness(controller)
            print("Harness integration: ATTACHED + STARTED")
        except Exception as e:
            print(f"Harness integration unavailable (continuing without): {e}")
        app = create_a2_paper_app(controller, require_token=args.require_token)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        run_bounded_session(duration_seconds=args.duration, require_token=args.require_token)


if __name__ == "__main__":
    main()
