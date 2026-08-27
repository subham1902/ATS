"""Wires advisory_llm_bridge + HarnessRuntimeAdapter into a single observability facade.

ADVISORY_ONLY — no order placement, no risk mutation, no A04 bypass.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ats.contracts.common import SystemClock

from .harness_router import AdvisoryResponse, AgentHealthView, HarnessHealthView, HarnessStatusView, LlmProviderView


def _now_iso() -> str:
    return SystemClock().now().isoformat()


@dataclass
class HarnessBridge:
    """Facade over ollama provider, optional Harness adapter, and advisory history."""

    ollama_provider: Any | None = None
    harness_adapter: Any | None = None
    agent_registry: Any | None = None
    advisory_bridge: Any | None = None
    _advisory_history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    _last_advisory_at: str | None = None
    _last_advisory_latency_ms: int | None = None
    _last_provider_label: str | None = None

    def status_view(self) -> HarnessStatusView:
        harness_view = self._harness_view()
        llm_view = self._llm_view()
        agents = self._agent_views()
        return HarnessStatusView(
            harness=harness_view,
            llm=llm_view,
            agents=agents,
            advisory_recent=tuple(self._advisory_history),
            safety={
                "HARNESS_AUTHORITY": "ADVISORY_ONLY",
                "REAL_ORDER_AUTHORITY": "NONE",
                "LIVE_MONEY": "DISABLED",
                "EXECUTION_TARGET": "PAPER",
                "REAL_ORDERS_PLACED": "0",
            },
        )

    def advisory(
        self,
        *,
        prompt: str,
        evidence_summary: str = "",
        evidence_refs: tuple[str, ...] = (),
        as_of: str | None = None,
        data_cutoff: str | None = None,
    ) -> AdvisoryResponse:
        if not prompt.strip():
            raise ValueError("advisory prompt must not be empty")
        started = time.monotonic()
        if self.advisory_bridge is not None:
            from ats.intelligence.inference.advisory_llm_bridge import AdvisoryEvidencePayload

            payload = AdvisoryEvidencePayload(
                prompt=prompt,
                evidence_summary=evidence_summary or "No specific evidence supplied; summarize regime and opportunity availability from general ATS state.",
                as_of=as_of or _now_iso(),
                data_cutoff=data_cutoff or _now_iso(),
                evidence_refs=evidence_refs,
            )
            text, provider_label, meta = self.advisory_bridge.advise(payload)
            latency_ms = int((time.monotonic() - started) * 1000)
            self._record_advisory(prompt=prompt, answer=text, provider=provider_label, latency_ms=latency_ms, evidence_refs=evidence_refs)
            model = None
            if isinstance(meta, dict):
                metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else None
                if isinstance(metrics, dict):
                    model = metrics.get("selected_model")
            return AdvisoryResponse(provider=provider_label, model=str(model) if model else None, latency_ms=latency_ms, answer=text)
        if self.ollama_provider is not None:
            from ats.intelligence.inference.advisory_llm_bridge import (
                AdvisoryEvidencePayload,
                AdvisoryStructuredResponse,
                build_advisory_prompt,
                render_advisory_text,
            )

            payload = AdvisoryEvidencePayload(
                prompt=prompt,
                evidence_summary=evidence_summary or "No evidence.",
                as_of=as_of or _now_iso(),
                data_cutoff=data_cutoff or _now_iso(),
                evidence_refs=evidence_refs,
            )
            advisory_prompt = build_advisory_prompt(payload)
            try:
                result = self.ollama_provider.infer(prompt=advisory_prompt, response_type=AdvisoryStructuredResponse)
                text = render_advisory_text(result)  # type: ignore[arg-type]
                latency_ms = int((time.monotonic() - started) * 1000)
                self._record_advisory(prompt=prompt, answer=text, provider="LOCAL_OLLAMA", latency_ms=latency_ms, evidence_refs=evidence_refs)
                return AdvisoryResponse(provider="LOCAL_OLLAMA", model=getattr(self.ollama_provider, "_configuration", None) and getattr(self.ollama_provider._configuration, "model", None), latency_ms=latency_ms, answer=text)
            except Exception:
                pass
        latency_ms = int((time.monotonic() - started) * 1000)
        fallback = f"SUMMARY: Advisory fallback — evidence refs: {len(evidence_refs)} | prompt: {prompt[:200]}\nAUTHORITY: ADVISORY_ONLY"
        self._record_advisory(prompt=prompt, answer=fallback, provider="DETERMINISTIC_FALLBACK", latency_ms=latency_ms, evidence_refs=evidence_refs)
        return AdvisoryResponse(provider="DETERMINISTIC_FALLBACK", latency_ms=latency_ms, answer=fallback)

    def _harness_view(self) -> HarnessHealthView:
        now = _now_iso()
        if self.harness_adapter is not None:
            try:
                health = self.harness_adapter.health()
                state = getattr(getattr(health, "state", None), "value", str(getattr(health, "state", "UNKNOWN")))
                return HarnessHealthView(
                    state=str(state),
                    checked_at=getattr(health, "checked_at", now).isoformat() if hasattr(getattr(health, "checked_at", None), "isoformat") else now,
                    active_sessions=int(getattr(health, "active_sessions", 0)),
                    reason_codes=tuple(getattr(health, "reason_codes", ()) or ()),
                )
            except Exception:
                pass
        return HarnessHealthView(state="STOPPED", checked_at=now, active_sessions=0, reason_codes=("HARNESS_NOT_STARTED",))

    def _llm_view(self) -> LlmProviderView | None:
        provider = self.ollama_provider
        if provider is None:
            return None
        cfg = getattr(provider, "_configuration", None) or getattr(provider, "ollama_configuration", None)
        metrics = None
        try:
            metrics = provider.metrics  # type: ignore[union-attr]
        except Exception:
            metrics = None
        md = metrics.model_dump(mode="json") if hasattr(metrics, "model_dump") else (metrics if isinstance(metrics, dict) else {})
        md = md if isinstance(md, dict) else {}
        endpoint = getattr(cfg, "endpoint", "http://127.0.0.1:11434") if cfg is not None else "http://127.0.0.1:11434"
        primary = getattr(cfg, "model", "qwen3:14b") if cfg is not None else "qwen3:14b"
        fallback = getattr(cfg, "fallback_model", None) if cfg is not None else "qwen2.5:14b"
        availability = md.get("availability") if isinstance(md, dict) else None
        if hasattr(availability, "value"):
            availability = availability.value
        return LlmProviderView(
            provider="LOCAL_OLLAMA",
            primary_model=str(primary),
            fallback_model=str(fallback) if fallback else None,
            endpoint=str(endpoint),
            health="HEALTHY" if md.get("availability", "AVAILABLE") in ("AVAILABLE", None) or availability == "AVAILABLE" else str(availability or "UNKNOWN"),
            availability=str(availability) if availability else None,
            last_latency_ms=getattr(provider, "last_latency_ms", None),
            last_error_code=getattr(provider, "last_error_code", None),
            requests=int(md.get("requests", 0)),
            successes=int(md.get("successes", 0)),
            failures=int(md.get("failures", 0)),
            retries=int(md.get("retries", 0)),
            fallback_count=int(getattr(provider, "fallback_count", 0) or 0),
        )

    def _agent_views(self) -> tuple[AgentHealthView, ...]:
        registry = self.agent_registry
        if registry is None:
            try:
                from ats.intelligence.harness.agent_registry import HARNESS_AGENT_REGISTRY

                registry = HARNESS_AGENT_REGISTRY
            except Exception:
                return ()
        views: list[AgentHealthView] = []
        try:
            for agent_type, policy in registry.items():
                name = getattr(agent_type, "value", str(agent_type))
                model = getattr(self.ollama_provider, "_configuration", None)
                model_name = getattr(model, "model", None) if model is not None else None
                views.append(
                    AgentHealthView(
                        agent_type=str(name),
                        status="IDLE" if self.harness_adapter is None else "ACTIVE",
                        last_trigger_at=self._last_advisory_at,
                        last_latency_ms=self._last_advisory_latency_ms,
                        model=str(model_name) if model_name else None,
                    )
                )
        except Exception:
            return tuple(views)
        return tuple(views)

    def _record_advisory(self, *, prompt: str, answer: str, provider: str, latency_ms: int, evidence_refs: tuple[str, ...]) -> None:
        now = _now_iso()
        self._last_advisory_at = now
        self._last_advisory_latency_ms = latency_ms
        self._last_provider_label = provider
        self._advisory_history.append(
            {
                "timestamp": now,
                "prompt_preview": prompt[:200],
                "provider": provider,
                "latency_ms": latency_ms,
                "evidence_refs_count": len(evidence_refs),
                "answer_preview": answer[:400],
            }
        )


__all__ = ["HarnessBridge"]
