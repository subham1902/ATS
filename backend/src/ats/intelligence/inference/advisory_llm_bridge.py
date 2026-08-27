"""Advisory-only LLM bridge — Ollama primary, OpenRouter optional, deterministic fallback.

The bridge NEVER places orders, mutates risk, or bypasses A04. It only answers
evidence-backed advisory questions. Inputs are evidence refs; outputs are
bounded text tied to those refs. Any malformed/timeout output degrades to the
deterministic evidence summary — ATS safety is never compromised.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ats.contracts.common import ATSBaseModel


class AdvisoryStructuredResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str = Field(min_length=1, max_length=4000)
    regime: str = Field(min_length=1, max_length=320)
    opportunity_status: str = Field(min_length=1, max_length=320)
    key_observations: list[str] = Field(default_factory=list, max_length=8)
    evidence_refs_cited: list[str] = Field(default_factory=list, max_length=20)
    confidence: str = Field(default="LOW")
    risks_or_caveats: list[str] = Field(default_factory=list, max_length=8)


class AdvisoryEvidencePayload(ATSBaseModel):
    prompt: str
    evidence_summary: str
    as_of: str
    data_cutoff: str
    evidence_refs: tuple[str, ...] = ()
    model_hint: str | None = None


class InferenceProviderLike(Protocol):
    def infer(self, *, prompt: str, response_type: type[BaseModel]) -> BaseModel: ...
    @property
    def metrics(self) -> object: ...


def build_advisory_prompt(payload: AdvisoryEvidencePayload) -> str:
    refs = ", ".join(payload.evidence_refs[:12]) if payload.evidence_refs else "NONE_SUPPLIED"
    return (
        "You are an ATS advisory assistant (ADVISORY_ONLY). You must NOT invent market data. "
        "Cite only supplied ATS evidence. If evidence is insufficient, say so explicitly.\n\n"
        "Respond with ONLY a JSON object with EXACTLY these keys and no others:\n"
        '{"summary": str, "regime": str, "opportunity_status": str, '
        '"key_observations": [str], "evidence_refs_cited": [str], '
        '"confidence": "LOW"|"MEDIUM"|"HIGH", "risks_or_caveats": [str]}\n'
        'Example: {"summary":"...","regime":"...","opportunity_status":"...",'
        '"key_observations":[],"evidence_refs_cited":[],"confidence":"LOW",'
        '"risks_or_caveats":[]}\n\n'
        f"EVIDENCE_SUMMARY:\n{payload.evidence_summary[:6000]}\n\n"
        f"EVIDENCE_REFS: [{refs}]\n"
        f"AS_OF: {payload.as_of}\n"
        f"DATA_CUTOFF: {payload.data_cutoff}\n\n"
        f"TASK: {payload.prompt}\n\n"
        "Return ONLY that JSON object. No markdown, no code fences, no extra keys."
    )


def deterministic_fallback_answer(payload: AdvisoryEvidencePayload) -> AdvisoryStructuredResponse:
    evidence_count = len(payload.evidence_refs)
    if payload.evidence_summary.strip().lower() in ("", "none", "no evidence", "unavailable"):
        return AdvisoryStructuredResponse(
            summary="Insufficient ATS evidence to assess market regime or opportunities.",
            regime="UNKNOWN — evidence insufficient",
            opportunity_status="NO QUALIFYING LIVE OPPORTUNITIES — evidence unavailable",
            key_observations=[],
            evidence_refs_cited=[],
            confidence="LOW",
            risks_or_caveats=[
                "ATS evidence was not supplied; defer any action until evidence is available."
            ],
        )
    return AdvisoryStructuredResponse(
        summary=(
            "ATS evidence was supplied but LLM inference was unavailable; advisory "
            "fell back to deterministic evidence summary."
        ),
        regime="UNKNOWN — defer to deterministic regime evidence",
        opportunity_status="NO QUALIFYING LIVE OPPORTUNITIES (deterministic fallback)"
        if evidence_count == 0
        else (
            f"EVIDENCE_PRESENT ({evidence_count} refs) — defer to deterministic candidate pipeline"
        ),
        key_observations=[payload.evidence_summary[:400]]
        if payload.evidence_summary.strip()
        else [],
        evidence_refs_cited=list(payload.evidence_refs[:6]),
        confidence="LOW",
        risks_or_caveats=["LLM unavailable; ATS deterministic controls remain authoritative."],
    )


def render_advisory_text(response: AdvisoryStructuredResponse) -> str:
    bullets = "\n".join(f"- {item}" for item in response.key_observations[:4]) or "- (none)"
    caveats = "\n".join(f"- {item}" for item in response.risks_or_caveats[:4]) or "- (none)"
    return (
        f"SUMMARY: {response.summary}\n"
        f"REGIME: {response.regime}\n"
        f"OPPORTUNITIES: {response.opportunity_status}\n"
        f"CONFIDENCE: {response.confidence}\n"
        f"OBSERVATIONS:\n{bullets}\n"
        f"CAVEATS:\n{caveats}\n"
        f"AUTHORITY: ADVISORY_ONLY — deterministic ATS governor remains authoritative."
    )


class AdvisoryLlmBridge:
    def __init__(
        self,
        *,
        ollama_provider: InferenceProviderLike | None = None,
        openrouter_provider: InferenceProviderLike | None = None,
        deterministic_advisor: object | None = None,
    ) -> None:
        self._ollama = ollama_provider
        self._openrouter = openrouter_provider
        self._deterministic = deterministic_advisor

    def providers(self) -> dict[str, object | None]:
        return {
            "ollama": self._ollama,
            "openrouter": self._openrouter,
            "deterministic": self._deterministic,
        }

    def advise(self, payload: AdvisoryEvidencePayload) -> tuple[str, str, dict[str, object]]:
        prompt = build_advisory_prompt(payload)
        if self._ollama is not None:
            try:
                result = self._ollama.infer(prompt=prompt, response_type=AdvisoryStructuredResponse)
                assert isinstance(result, AdvisoryStructuredResponse)
                metrics = (
                    _metrics_dict(self._ollama.metrics) if hasattr(self._ollama, "metrics") else {}
                )
                return (
                    render_advisory_text(result),
                    "LOCAL_OLLAMA",
                    {
                        "provider": "LOCAL_OLLAMA",
                        "model": getattr(metrics, "get", lambda *_: None)("selected_model")
                        if isinstance(metrics, dict)
                        else None,
                        **({"metrics": metrics} if metrics else {}),
                    },
                )
            except Exception:
                pass
        if self._openrouter is not None:
            try:
                result = self._openrouter.infer(
                    prompt=prompt, response_type=AdvisoryStructuredResponse
                )
                assert isinstance(result, AdvisoryStructuredResponse)
                metrics = (
                    _metrics_dict(self._openrouter.metrics)
                    if hasattr(self._openrouter, "metrics")
                    else {}
                )
                return (
                    render_advisory_text(result),
                    "OPENROUTER",
                    {"provider": "OPENROUTER", **({"metrics": metrics} if metrics else {})},
                )
            except Exception:
                pass
        fallback = deterministic_fallback_answer(payload)
        return (
            render_advisory_text(fallback),
            "DETERMINISTIC_FALLBACK",
            {"provider": "DETERMINISTIC_FALLBACK"},
        )


def _metrics_dict(metrics: object) -> dict[str, object]:
    if isinstance(metrics, BaseModel):
        try:
            return metrics.model_dump(mode="json")
        except Exception:
            pass
    if isinstance(metrics, dict):
        return {str(key): value for key, value in metrics.items()}
    return {}


__all__ = [
    "AdvisoryLlmBridge",
    "AdvisoryEvidencePayload",
    "AdvisoryStructuredResponse",
    "build_advisory_prompt",
    "deterministic_fallback_answer",
    "render_advisory_text",
]
