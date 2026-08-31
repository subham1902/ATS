"""Live pipeline telemetry bridge — makes the scanner truthful without fabricating trades.

Connects real Upstox freshness/board + runtime provider into the OperatorIntelligence
projection. No candidate is invented; rejections are explained. Pipeline counters
remain honest: if no candidate qualifies, scanner shows qualified=0 with reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from ats.contracts.common import SystemClock, UTCDateTime
from ats.observability.operator_intelligence import ProvenanceType, SourceState
from ats.observability.operator_projection import (
    AgentObservation,
    CandidateObservation,
    InstrumentObservation,
    OperatorProjectionInput,
)

try:
    from ats.market.derivatives.providers.models import SourceFreshness

    _FRESH = SourceFreshness.FRESH
    _STALE = SourceFreshness.STALE
    _UNKNOWN = SourceFreshness.UNKNOWN
    _RESYNC = SourceFreshness.RESYNC_REQUIRED
except Exception:
    _FRESH = _STALE = _UNKNOWN = _RESYNC = None  # type: ignore[assignment]


class FreshnessBoardLike(Protocol):
    def evaluate(self, now: UTCDateTime) -> dict[str, Any]: ...
    def keys(self) -> tuple[str, ...]: ...


@dataclass
class LivePipelineCounters:
    upstox_raw_messages: int = 0
    normalized_messages: int = 0
    fresh_messages: int = 0
    scanner_observations: int = 0
    feature_bundles: int = 0
    regime_evaluations: int = 0
    calibration_evaluations: int = 0
    r10_evaluations: int = 0
    r10x_evaluations: int = 0
    live_option_chains: int = 0
    live_option_quotes: int = 0
    option_evidence_failures: int = 0
    scanner_failures: int = 0
    candidates_considered: int = 0
    candidates_rejected: int = 0
    candidates_qualified: int = 0
    portfolio_brain_decisions: int = 0
    a04_decisions: int = 0
    paper_orders: int = 0
    paper_fills: int = 0
    last_updated_at: UTCDateTime | None = None
    nifty_last: str | None = None
    banknifty_last: str | None = None
    nifty_atm: str | None = None
    banknifty_atm: str | None = None
    nifty_regime: str | None = None
    banknifty_regime: str | None = None
    nifty_volatility: str | None = None
    banknifty_volatility: str | None = None
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    rejection_reason_codes: dict[str, int] = field(default_factory=dict)
    predictions: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_predictions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LivePipelineBridge:
    """Feeds truthful universe/freshness into OperatorProvider without faking candidates."""

    board: Any | None = None
    runtime_provider: Any | None = None
    instrument_keys: tuple[str, ...] = ()
    marks: dict[str, Decimal] = field(default_factory=dict)
    counters: LivePipelineCounters = field(default_factory=LivePipelineCounters)
    pipeline_evaluations: int = 0

    def record_tick(
        self, instrument_key: str, price: Decimal, *, received_at: UTCDateTime | None = None
    ) -> None:
        now = received_at or SystemClock().now()
        self.marks[instrument_key] = price
        self.counters.upstox_raw_messages += 1
        self.counters.normalized_messages += 1
        if instrument_key == "NIFTY":
            self.counters.nifty_last = str(price)
        elif instrument_key == "BANKNIFTY":
            self.counters.banknifty_last = str(price)
        self.counters.last_updated_at = now

    def record_freshness(self, *, fresh_count: int) -> None:
        """Record feed freshness without impersonating an autonomous scan."""

        self.counters.fresh_messages += fresh_count
        self.counters.last_updated_at = SystemClock().now()

    def record_market_evidence(
        self,
        underlying: str,
        *,
        atm_strike: str | None = None,
        regime: str | None = None,
        volatility: str | None = None,
    ) -> None:
        if underlying == "NIFTY":
            if atm_strike is not None:
                self.counters.nifty_atm = atm_strike
            if regime is not None:
                self.counters.nifty_regime = regime
            if volatility is not None:
                self.counters.nifty_volatility = volatility
        elif underlying == "BANKNIFTY":
            if atm_strike is not None:
                self.counters.banknifty_atm = atm_strike
            if regime is not None:
                self.counters.banknifty_regime = regime
            if volatility is not None:
                self.counters.banknifty_volatility = volatility

    def record_prediction(self, prediction_dict: dict[str, Any]) -> None:
        und = str(prediction_dict.get("underlying", "UNKNOWN"))
        self.counters.predictions[und] = prediction_dict
        self.counters.recent_predictions.append(dict(prediction_dict))
        if len(self.counters.recent_predictions) > 50:
            self.counters.recent_predictions = self.counters.recent_predictions[-50:]

    def build_projection_input(
        self, *, as_of: UTCDateTime | None = None
    ) -> OperatorProjectionInput:
        now = as_of or SystemClock().now()
        data_cutoff = self.counters.last_updated_at or now
        instruments: list[InstrumentObservation] = []
        freshness_map: dict[str, Any] = {}
        if self.board is not None and hasattr(self.board, "evaluate"):
            try:
                freshness_map = self.board.evaluate(now)
            except Exception:
                freshness_map = {}
        keys = (
            self.instrument_keys
            or tuple(sorted(set(list(freshness_map.keys()) + list(self.marks.keys()))))
            or ("NIFTY", "BANKNIFTY")
        )
        for key in keys:
            freshness = freshness_map.get(key)
            if freshness is not None:
                fname = getattr(freshness, "value", str(freshness))
                if fname == "FRESH":
                    state = SourceState.LIVE
                elif fname in ("STALE", "RESYNC_REQUIRED"):
                    state = SourceState.STALE
                else:
                    state = SourceState.UNKNOWN
            else:
                state = SourceState.LIVE if key in self.marks else SourceState.UNKNOWN
            observed_at = self.counters.last_updated_at or now
            instruments.append(
                InstrumentObservation(
                    instrument_key=key,
                    source_state=state,
                    reference_valid=True,
                    observed_at=observed_at,
                )
            )
        candidates: tuple[CandidateObservation, ...] = ()
        agents: tuple[AgentObservation, ...] = ()
        return OperatorProjectionInput(
            as_of=now,
            data_cutoff=data_cutoff,
            instruments=tuple(instruments),
            candidates=candidates,
            agents=agents,
            provenance=ProvenanceType.LIVE,
            rejection_counts=dict(self.counters.rejection_reasons),
            predictions=dict(self.counters.predictions),
            recent_predictions=list(self.counters.recent_predictions),
        )

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "upstox_raw_messages": self.counters.upstox_raw_messages,
            "normalized_messages": self.counters.normalized_messages,
            "fresh_messages": self.counters.fresh_messages,
            "scanner_observations": self.counters.scanner_observations,
            "feature_bundles": self.counters.feature_bundles,
            "regime_evaluations": self.counters.regime_evaluations,
            "calibration_evaluations": self.counters.calibration_evaluations,
            "r10_evaluations": self.counters.r10_evaluations,
            "r10x_evaluations": self.counters.r10x_evaluations,
            "live_option_chains": self.counters.live_option_chains,
            "live_option_quotes": self.counters.live_option_quotes,
            "option_evidence_failures": self.counters.option_evidence_failures,
            "candidates_considered": self.counters.candidates_considered,
            "candidates_rejected": self.counters.candidates_rejected,
            "candidates_qualified": self.counters.candidates_qualified,
            "portfolio_brain_decisions": self.counters.portfolio_brain_decisions,
            "a04_decisions": self.counters.a04_decisions,
            "paper_orders": self.counters.paper_orders,
            "paper_fills": self.counters.paper_fills,
            "nifty_last": self.counters.nifty_last,
            "banknifty_last": self.counters.banknifty_last,
            "nifty_atm": self.counters.nifty_atm,
            "banknifty_atm": self.counters.banknifty_atm,
            "nifty_regime": self.counters.nifty_regime,
            "banknifty_regime": self.counters.banknifty_regime,
            "nifty_volatility": self.counters.nifty_volatility,
            "banknifty_volatility": self.counters.banknifty_volatility,
            "rejection_reasons": dict(self.counters.rejection_reasons),
            "rejection_reason_codes": dict(self.counters.rejection_reason_codes),
            "predictions": dict(self.counters.predictions),
            "recent_predictions": list(self.counters.recent_predictions),
        }


__all__ = ["LivePipelineBridge", "LivePipelineCounters"]
