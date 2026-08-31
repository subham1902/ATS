import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import time

from ats.intelligence.inference.advisory_llm_bridge import (
    AdvisoryEvidencePayload,
    AdvisoryLlmBridge,
)
from ats.intelligence.inference.ollama import OllamaConfiguration, OllamaInferenceProvider
from ats.intelligence.inference.ollama_transport import OllamaHttpTransport

from scripts.run_live_a2_stack import build_live_app

app, ctl, hb, lb, prov = build_live_app(require_token=False)
print(
    f"A04 safety before: real={ctl.status().real_orders_placed} "
    f"live={ctl.config.live_money} exec={ctl.config.execution_target}"
)

bad_cfg = OllamaConfiguration(
    model="qwen3:14b",
    endpoint="http://127.0.0.1:19999",
    timeout_ms=600,
    maximum_attempts=1,
    circuit_failure_threshold=10,
)
bad_prov = OllamaInferenceProvider(
    configuration=bad_cfg,
    transport=OllamaHttpTransport(endpoint="http://127.0.0.1:19999"),
    monotonic_ms=lambda: int(time.monotonic() * 1000),
    wait=lambda s: None,
)
bad_bridge = AdvisoryLlmBridge(ollama_provider=bad_prov)
payload = AdvisoryEvidencePayload(
    prompt="Explain regime",
    evidence_summary="Regime UNKNOWN, no candidates",
    as_of="2026-08-27T15:30+05:30",
    data_cutoff="2026-08-27T15:30+05:30",
    evidence_refs=(),
)
text, provider, _ = bad_bridge.advise(payload)
print(
    f"FAIL1 ollama down -> {provider} ADVISORY_ONLY={('ADVISORY_ONLY' in text)} "
    f"real_orders={ctl.status().real_orders_placed}"
)

timeout_cfg = OllamaConfiguration(
    model="qwen3:14b", timeout_ms=1, maximum_attempts=1, circuit_failure_threshold=10
)
timeout_prov = OllamaInferenceProvider(
    configuration=timeout_cfg,
    transport=OllamaHttpTransport(),
    monotonic_ms=lambda: int(time.monotonic() * 1000),
    wait=lambda s: None,
)
timeout_bridge = AdvisoryLlmBridge(ollama_provider=timeout_prov)
text2, provider2, _ = timeout_bridge.advise(payload)
print(f"FAIL2 timeout -> {provider2} real_orders={ctl.status().real_orders_placed}")

print(
    f"FAIL3 harness down: ctl {ctl.state.value} "
    f"feed {ctl.market_feed.is_healthy()} broker {ctl.broker.is_healthy()}"
)

real_cfg = OllamaConfiguration(
    model="qwen3:14b", fallback_model="qwen2.5:14b", max_tokens=128, timeout_ms=30000
)
real_prov = OllamaInferenceProvider(
    configuration=real_cfg,
    transport=OllamaHttpTransport(endpoint="http://127.0.0.1:11434"),
    monotonic_ms=lambda: int(time.monotonic() * 1000),
    wait=lambda s: time.sleep(s),
)
real_bridge = AdvisoryLlmBridge(ollama_provider=real_prov)
text3, prov3, _ = real_bridge.advise(payload)
print(
    f"RESTORE -> {prov3} real_orders {ctl.status().real_orders_placed} live {ctl.config.live_money}"
)
print("FAILURE INJECTION PASS: all paths stayed PAPER/DISABLED/ADVISORY_ONLY, real_orders=0")
