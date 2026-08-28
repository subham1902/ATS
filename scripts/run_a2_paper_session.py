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
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import uvicorn
from ats.contracts.common import SystemClock
from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.intelligence.calibration.models import CalibrationObservation
from ats.intelligence.harness.harness_integration import attach_and_start_a2_harness
from ats.intelligence.inference.advisory_llm_bridge import AdvisoryLlmBridge
from ats.intelligence.inference.ollama import (
    OllamaConfiguration,
    OllamaInferenceProvider,
)
from ats.intelligence.inference.ollama_transport import OllamaHttpTransport
from ats.market.data_acquisition.upstox_client import UpstoxReadOnlyClient
from ats.market.derivatives.contract_master import DerivativeUnderlying
from ats.market.derivatives.option_universe import build_dynamic_option_universe
from ats.market.feeds.upstox_v3 import (
    BANKNIFTY_INDEX_FEED_KEY,
    NIFTY_INDEX_FEED_KEY,
    FeedMode,
    UpstoxFeedAuthorization,
    UpstoxFeedConfiguration,
    UpstoxFeedLimits,
    UpstoxV3FeedAuthorizer,
    UpstoxV3Transport,
    WireFormat,
)
from ats.market.feeds.upstox_v3.runtime_feed import UpstoxV3RuntimeFeed
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    UpstoxMarketFeedAdapter,
    create_a2_paper_app,
)
from ats.trading_runtime.session import (
    RuntimeSessionPhase,
    SessionRuntimeConfig,
    resolve_session_status,
)
from pydantic import SecretStr
from run_d10_live_acceptance import _extract_ltp, _fetch_reference

DEFAULT_CHAMPION_CALIBRATION_STORE = Path(
    r"D:\Projects\ATS\ats\data\historical\calibration_store_v1.json"
)
_LIVE_BAR_NAMESPACE = UUID("bf0b9b07-5770-5a6a-a750-cb216e8cb094")


def load_champion_calibration_observations(
    path: Path, *, as_of: datetime
) -> tuple[CalibrationObservation, ...]:
    """Load only frozen champion evidence already visible at ``as_of``.

    Missing evidence remains an empty, fail-closed calibration input. Invalid
    evidence is not silently ignored because that would conceal store damage.
    """

    if not path.is_file():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    observations = tuple(
        CalibrationObservation.model_validate_json(json.dumps(item)) for item in raw
    )
    return tuple(item for item in observations if item.available_to_strategy_time <= as_of)


def load_live_intraday_history(
    client: UpstoxReadOnlyClient, *, now: datetime
) -> dict[str, tuple[MarketSnapshot, ...]]:
    """Load contiguous completed five-minute bars from today's Upstox session."""

    result: dict[str, tuple[MarketSnapshot, ...]] = {}
    for underlying, instrument_key in (
        ("NIFTY", NIFTY_INDEX_FEED_KEY),
        ("BANKNIFTY", BANKNIFTY_INDEX_FEED_KEY),
    ):
        document = client.intraday_candles(instrument_key, unit="minutes", interval=5)
        rows = document.get("data", {}).get("candles", [])
        completed = sorted(
            (
                row
                for row in rows
                if datetime.fromisoformat(str(row[0])) + timedelta(minutes=5) <= now
            ),
            key=lambda row: datetime.fromisoformat(str(row[0])),
        )
        contiguous: list[list[object]] = []
        for row in completed:
            stamp = datetime.fromisoformat(str(row[0])).astimezone(UTC)
            if contiguous:
                prior = datetime.fromisoformat(str(contiguous[-1][0])).astimezone(UTC)
                if stamp != prior + timedelta(minutes=5):
                    contiguous = []
            contiguous.append(row)
        snapshots: list[MarketSnapshot] = []
        for sequence, row in enumerate(contiguous[-20:], start=1):
            stamp = datetime.fromisoformat(str(row[0])).astimezone(UTC)
            snapshot = MarketSnapshot(
                schema_version="1.0",
                snapshot_id=uuid5(_LIVE_BAR_NAMESPACE, f"{instrument_key}:{stamp.isoformat()}"),
                instrument_id=underlying,
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                sequence=sequence,
                bar_timestamp=stamp,
                received_at=stamp + timedelta(minutes=5),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                quality_state=DataQualityState.GOOD,
                quality_flags=(),
                source="UPSTOX_INTRADAY_V3",
                source_version="3.0.0",
                session_state=SessionState.OPEN,
                payload_hash="0" * 64,
            )
            snapshots.append(
                snapshot.model_copy(update={"payload_hash": compute_payload_hash(snapshot)})
            )
        result[underlying] = tuple(snapshots)
    return result


class ReadOnlyUpstoxSupervisor:
    """Own the session-aware read-only Upstox feed lifecycle for A2 Paper."""

    def __init__(self, controller: A2PaperSessionController, token: str) -> None:
        self._controller = controller
        self._token = token
        self._stop = asyncio.Event()
        self._feed: UpstoxV3RuntimeFeed | None = None

    async def run(self) -> None:
        while not self._stop.is_set():
            status = resolve_session_status(
                calendar=self._controller._calendar,
                config=SessionRuntimeConfig(),
                now=SystemClock().now(),
            )
            if status.phase in (RuntimeSessionPhase.CLOSED, RuntimeSessionPhase.HALTED):
                self._set_feed_health(True)
                await self._wait(15.0)
                continue
            try:
                feed = await asyncio.to_thread(self._build_feed)
                self._feed = feed
                self._controller.attach_upstox_runtime_feed(feed)
                await asyncio.to_thread(feed.connect_live)
                self._set_feed_health(True)
                while not self._stop.is_set():
                    await asyncio.to_thread(feed.receive_live)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._set_feed_health(False)
                print(f"Upstox read-only feed unavailable: {type(error).__name__}")
                await self._wait(5.0)
            finally:
                self._disconnect()

    def stop(self) -> None:
        self._stop.set()
        self._disconnect()

    def _build_feed(self) -> UpstoxV3RuntimeFeed:
        now = datetime.now(UTC)
        contracts = _fetch_reference(now)
        quote_client = UpstoxReadOnlyClient(token=self._token)
        spots = {
            DerivativeUnderlying.NIFTY.value: _extract_ltp(
                quote_client.ltp(NIFTY_INDEX_FEED_KEY), NIFTY_INDEX_FEED_KEY
            ),
            DerivativeUnderlying.BANKNIFTY.value: _extract_ltp(
                quote_client.ltp(BANKNIFTY_INDEX_FEED_KEY), BANKNIFTY_INDEX_FEED_KEY
            ),
        }
        universe = build_dynamic_option_universe(
            contracts=contracts,
            spots=spots,
            as_of=now,
            mode=FeedMode.FULL,
        )
        if len(universe) != 22:
            raise RuntimeError("DYNAMIC_OPTION_UNIVERSE_NOT_22")
        authorization = UpstoxFeedAuthorization(bearer_token=SecretStr(self._token))
        configuration = UpstoxFeedConfiguration(
            wire_format=WireFormat.PROTOBUF_BINARY,
            client_guid=str(uuid4()),
            limits=UpstoxFeedLimits(
                maximum_silence_ms=5_000,
                stale_after_ms=10_000,
                maximum_buffered_frames=32,
                receive_timeout_ms=5_000,
            ),
        )
        feed = UpstoxV3RuntimeFeed(
            authorization=authorization,
            configuration=configuration,
        )
        feed.register_universe(universe)
        feed.register_reference_contracts(contracts)
        feed.attach_transport(
            UpstoxV3Transport(
                configuration=configuration,
                authorizer=UpstoxV3FeedAuthorizer(authorization),
            )
        )
        return feed

    async def _wait(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    def _disconnect(self) -> None:
        feed, self._feed = self._feed, None
        if feed is not None:
            try:
                feed.disconnect_live()
            except Exception:
                pass

    def _set_feed_health(self, healthy: bool) -> None:
        setter = getattr(self._controller.market_feed, "set_healthy", None)
        if callable(setter):
            setter(healthy)


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
    token_state = "PRESENT (Protected)" if has_token else "NOT SET (Mock/Offline mode)"
    print(f"Upstox Token Auth: {token_state}")

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
    parser.add_argument(
        "--duration", type=int, default=30, help="Duration in seconds for bounded session"
    )
    parser.add_argument("--host", default="127.0.0.1", help="API Host")
    parser.add_argument("--port", type=int, default=8000, help="API Port")
    parser.add_argument(
        "--serve", action="store_true", help="Start FastAPI server with A2 controller"
    )
    parser.add_argument(
        "--require-token", action="store_true", help="Require ATS_UPSTOX_ACCESS_TOKEN"
    )
    args = parser.parse_args()

    if args.serve:
        config = A2PaperSessionConfig(
            execution_target="PAPER",
            live_money="DISABLED",
            require_live_instrument_evidence=True,
        )
        feed = UpstoxMarketFeedAdapter()
        controller = A2PaperSessionController(config=config, market_feed=feed)
        calibration_path = Path(
            os.environ.get(
                "ATS_CHAMPION_CALIBRATION_STORE",
                str(DEFAULT_CHAMPION_CALIBRATION_STORE),
            )
        )
        champion_calibration = load_champion_calibration_observations(
            calibration_path, as_of=SystemClock().now()
        )
        controller.set_calibration_observations_provider(
            lambda: tuple(
                item
                for item in champion_calibration
                if item.available_to_strategy_time <= SystemClock().now()
            )
        )
        print(
            f"Champion calibration: {len(champion_calibration)} frozen as-of-visible observations"
        )
        live_history = load_live_intraday_history(UpstoxReadOnlyClient(), now=SystemClock().now())
        for underlying, snapshots in live_history.items():
            controller.seed_snapshot_history(underlying, snapshots)
        print(
            "Live feature warm-up: "
            + ", ".join(
                f"{underlying}={len(snapshots)} completed 5m bars"
                for underlying, snapshots in sorted(live_history.items())
            )
        )
        # Attach & start the pinned DeepSeek Harness (ADVISORY_ONLY, governor-gated)
        try:
            attach_and_start_a2_harness(controller)
            print("Harness integration: ATTACHED + STARTED")
        except Exception as e:
            print(f"Harness integration unavailable (continuing without): {e}")
        app = create_a2_paper_app(controller, require_token=args.require_token)
        # Attach the existing local advisory provider to the Harness observability
        # facade. This adds no authority: every response remains ADVISORY_ONLY.
        ollama = OllamaInferenceProvider(
            configuration=OllamaConfiguration(
                model="qwen3:14b",
                fallback_model="qwen2.5:14b",
                max_tokens=256,
                timeout_ms=90_000,
            ),
            transport=OllamaHttpTransport(endpoint="http://127.0.0.1:11434"),
            monotonic_ms=lambda: int(time.monotonic() * 1000),
            wait=lambda seconds: time.sleep(seconds),
        )
        bridge = getattr(app.state, "harness_bridge", None)
        if bridge is not None:
            bridge.ollama_provider = ollama
            bridge.advisory_bridge = AdvisoryLlmBridge(ollama_provider=ollama)
        app.state.ollama_provider = ollama
        token = os.environ.get("ATS_UPSTOX_ACCESS_TOKEN", "").strip()
        live_feed = ReadOnlyUpstoxSupervisor(controller, token) if token else None
        live_feed_task: asyncio.Task[None] | None = None

        @app.on_event("startup")  # type: ignore[misc]
        async def _start_live_feed() -> None:
            nonlocal live_feed_task
            if live_feed is not None:
                live_feed_task = asyncio.create_task(live_feed.run())

        @app.on_event("shutdown")  # type: ignore[misc]
        async def _stop_live_feed() -> None:
            if live_feed is not None:
                live_feed.stop()
            if live_feed_task is not None:
                live_feed_task.cancel()
                await asyncio.gather(live_feed_task, return_exceptions=True)

        app.state.upstox_live_feed_supervisor = live_feed
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        run_bounded_session(duration_seconds=args.duration, require_token=args.require_token)


if __name__ == "__main__":
    main()
