"""Live A2 paper stack — backend + harness (local Ollama) + autonomous paper loop + pipeline telemetry.

Starts the FastAPI app with:
  - A2PaperSessionController (PAPER, DISABLED)
  - HarnessBridge (ADVISORY_ONLY, local Ollama qwen3:14b)
  - LivePipelineBridge (truthful Universe/Fresh counters)
  - OperatorIntelligence hydrated from real pipeline (not empty)

No real orders are placed. No secrets are printed.
"""

from __future__ import annotations

import argparse
import time

try:
    import uvicorn
except ImportError:
    uvicorn = None  # type: ignore[assignment]

from ats.api.app import create_app
from ats.api.harness_bridge import HarnessBridge
from ats.intelligence.inference.advisory_llm_bridge import AdvisoryLlmBridge
from ats.intelligence.inference.ollama import OllamaConfiguration
from ats.intelligence.inference.ollama import OllamaInferenceProvider
from ats.intelligence.inference.ollama_transport import OllamaHttpTransport
from ats.observability.live_pipeline_bridge import LivePipelineBridge
from ats.observability.operator_provider import OperatorIntelligenceProvider
from ats.trading_runtime.a2_runner import (
    A2PaperSessionConfig,
    A2PaperSessionController,
    UpstoxMarketFeedAdapter,
    create_a2_paper_app,
)


def build_live_app(*, require_token: bool = False):
    cfg = OllamaConfiguration(
        model="qwen3:14b",
        fallback_model="qwen2.5:14b",
        max_tokens=256,
        timeout_ms=90_000,
    )
    transport = OllamaHttpTransport(endpoint="http://127.0.0.1:11434")

    def mono() -> int:
        return int(time.monotonic() * 1000)

    ollama_provider = OllamaInferenceProvider(
        configuration=cfg,
        transport=transport,
        monotonic_ms=mono,
        wait=lambda s: time.sleep(s),
    )
    advisory_bridge = AdvisoryLlmBridge(ollama_provider=ollama_provider)
    harness_bridge = HarnessBridge(ollama_provider=ollama_provider, advisory_bridge=advisory_bridge)
    live_bridge = LivePipelineBridge(instrument_keys=("NIFTY", "BANKNIFTY"))
    operator_provider = OperatorIntelligenceProvider()

    from ats.contracts.common import SystemClock

    now = SystemClock().now()
    initial_input = live_bridge.build_projection_input(as_of=now)
    from ats.api.models import StreamEvent
    from uuid import uuid4

    try:
        operator_provider.observe(
            initial_input,
            StreamEvent(
                stream_event_id=uuid4(),
                event_kind="MARKET_SNAPSHOT_READY",
                occurred_at=now,
                correlation_id=uuid4(),
                payload={"source": "LIVE_PIPELINE_BRIDGE_INIT"},
            ),
        )
    except Exception:
        pass

    a2_config = A2PaperSessionConfig(execution_target="PAPER", live_money="DISABLED")
    feed = UpstoxMarketFeedAdapter()
    controller = A2PaperSessionController(
        config=a2_config,
        market_feed=feed,
        operator_provider=operator_provider,
    )
    controller.start(require_token=require_token)

    app = create_app(
        trading_runtime_provider=controller.runtime_provider,
        operator_intelligence_provider=operator_provider,
        trading_runtime_engine=controller.engine or controller,
    )
    app.state.a2_session_controller = controller
    app.state.harness_bridge = harness_bridge
    app.state.live_pipeline_bridge = live_bridge
    app.state.ollama_provider = ollama_provider
    app.state.advisory_bridge = advisory_bridge
    app.state.operator_intelligence_provider = operator_provider
    return app, controller, harness_bridge, live_bridge, ollama_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Live A2 paper stack (PAPER only)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--require-token", action="store_true")
    args = parser.parse_args()
    app, controller, hb, lb, _ = build_live_app(require_token=args.require_token)
    print(f"Starting live A2 paper stack on {args.host}:{args.port} — PAPER/DISABLED/ADVISORY_ONLY")
    print(f"Harness LLM: LOCAL_OLLAMA qwen3:14b (fallback qwen2.5:14b) @ http://127.0.0.1:11434")
    print(f"Pipeline: NIFTY + BANKNIFTY Universe hydrated — scanner will show LIVE fresh counts")
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
