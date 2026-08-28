"""Read-only projections from canonical ATS contracts into operator telemetry.

This module performs no scoring, sizing, authorization, or financial mutation.
Missing source facts remain UNKNOWN/null; it never reconstructs R10/R10-X output.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.models import Position, RiskDecision, SupervisorAdvisory
from ats.contracts.governance.models import OpportunityCandidate
from ats.intelligence.calibration.validation import CalibrationValidationReport
from ats.intelligence.rare_opportunity.models import (
    OptionConvexityInput,
    RareOpportunityAssessment,
)
from ats.portfolio.brain.models import PortfolioAllocationDecision
from ats.trading_runtime.runtime_provider import RuntimeProviderState

from .operator_intelligence import (
    A04Outcome,
    AgentAccountabilityEntry,
    AgentStatus,
    CandidateClass,
    CandidateClassCounts,
    EdgeLedgerEntry,
    EdgeLedgerReadModel,
    EvidenceLineageNode,
    FunnelCounts,
    GovernorResult,
    OperatorIntelligenceSnapshot,
    OpportunityMapPoint,
    OpportunityScannerReadModel,
    PortfolioBrainOutcome,
    ProvenanceType,
    RejectionBreakdown,
    SourceState,
    SurvivalTelemetryReadModel,
    TimelineEvent,
    resolve_operator_survival_state,
)


class RuntimeStateReader(Protocol):
    def get_state(self) -> RuntimeProviderState: ...


class InstrumentObservation(BaseModel):
    """Reference/feed truth already established by D10 and InstrumentSpec authority."""

    instrument_key: str
    source_state: SourceState
    reference_valid: bool
    observed_at: UTCDateTime


class CandidateObservation(BaseModel):
    """Joins canonical decisions without recomputing any of them."""

    candidate: OpportunityCandidate
    underlying: str | None = None
    strategy: str | None = None
    rare_assessment: RareOpportunityAssessment | None = None
    convexity_input: OptionConvexityInput | None = None
    portfolio_decision: PortfolioAllocationDecision | None = None
    risk_decision: RiskDecision | None = None
    calibration: CalibrationValidationReport | None = None
    market_implied_probability: float | None = None
    realized_position: Position | None = None


class AgentObservation(BaseModel):
    agent_id: str
    role: str
    advisory: SupervisorAdvisory | None = None
    wake_reason: str | None = None
    data_cutoff: UTCDateTime | None = None
    proposal_id: str | None = None
    tool_calls_count: int = 0
    status: AgentStatus = AgentStatus.UNKNOWN
    is_stale: bool = False


class OperatorProjectionInput(BaseModel):
    as_of: UTCDateTime
    data_cutoff: UTCDateTime
    instruments: tuple[InstrumentObservation, ...] = ()
    candidates: tuple[CandidateObservation, ...] = ()
    agents: tuple[AgentObservation, ...] = ()
    provenance: ProvenanceType = ProvenanceType.LIVE
    rejection_counts: dict[str, int] = Field(default_factory=dict)


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)


def _candidate_class(item: CandidateObservation) -> CandidateClass:
    if item.rare_assessment is None:
        return CandidateClass.STANDARD
    return CandidateClass(_value(item.rare_assessment.opportunity_class))


def _portfolio_outcome(item: CandidateObservation) -> PortfolioBrainOutcome:
    if item.portfolio_decision is None:
        return PortfolioBrainOutcome.UNKNOWN
    return PortfolioBrainOutcome(_value(item.portfolio_decision.outcome))


def _a04_outcome(item: CandidateObservation) -> A04Outcome:
    if item.risk_decision is None:
        return A04Outcome.UNKNOWN
    decision = _value(item.risk_decision.decision)
    return A04Outcome(decision) if decision in {"ALLOW", "DENY"} else A04Outcome.UNKNOWN


def _reason_codes(item: CandidateObservation) -> tuple[str, ...]:
    values: list[str] = []
    for source in (item.rare_assessment, item.portfolio_decision, item.risk_decision):
        if source is not None:
            values.extend(str(value) for value in source.reason_codes)
    if item.calibration is not None:
        values.extend(str(value) for value in item.calibration.reason_codes)
    return tuple(values)


def _has_reason(item: CandidateObservation, fragment: str) -> bool:
    return any(fragment in reason.upper() for reason in _reason_codes(item))


def _survival(
    runtime: RuntimeProviderState | None,
    *,
    as_of: UTCDateTime,
) -> SurvivalTelemetryReadModel:
    if runtime is None:
        state, reasons = resolve_operator_survival_state()
        return SurvivalTelemetryReadModel(
            effective_survival_state=state,
            reason_codes=reasons,
            last_state_at=as_of,
        )
    effective = _value(runtime.effective_mode)
    loss = _value(runtime.loss_state)
    state, reasons = resolve_operator_survival_state(
        is_halted=runtime.is_halted,
        must_flatten=runtime.must_flatten,
        loss_state=loss,
        effective_mode=effective,
        can_enter=runtime.can_enter,
        can_reduce=runtime.can_reduce,
        paused_new_entries=runtime.paused,
        feed_healthy=runtime.feed_healthy,
        broker_healthy=runtime.broker_healthy,
        system_state="READY" if runtime.updated_at is not None else "UNKNOWN",
    )
    return SurvivalTelemetryReadModel(
        effective_survival_state=state,
        user_selected_mode=_value(runtime.user_mode),
        effective_mode=effective,
        reason_codes=reasons,
        session_equity=str(runtime.total + runtime.realized + runtime.unrealized),
        hwm=str(runtime.peak_equity),
        drawdown_fraction=str(runtime.drawdown_fraction),
        available_risk=str(runtime.available),
        open_positions=len(runtime.open_positions),
        new_entry_permission=runtime.can_enter and not runtime.paused and not runtime.is_halted,
        reduction_permission=runtime.can_reduce,
        feed_healthy=runtime.feed_healthy,
        broker_healthy=runtime.broker_healthy,
        reconciliation_active=False,
        loss_state=loss,
        last_state_at=runtime.updated_at or as_of,
    )


def _edge_entry(item: CandidateObservation) -> EdgeLedgerEntry:
    candidate = item.candidate
    rare = item.rare_assessment
    convexity = item.convexity_input
    portfolio = item.portfolio_decision
    calibration = item.calibration
    position = item.realized_position
    penalty = None
    if portfolio is not None:
        penalty = float(
            portfolio.correlation_penalty
            + portfolio.concentration_penalty
            + portfolio.drawdown_penalty
            + portfolio.execution_penalty
            + portfolio.liquidity_penalty
        )
    return EdgeLedgerEntry(
        candidate_id=str(candidate.candidate_id),
        timestamp=candidate.created_at,
        underlying=item.underlying or "UNKNOWN",
        instrument=str(candidate.instrument_id),
        direction=_value(candidate.side),
        strategy=item.strategy or str(candidate.strategy_definition_id),
        candidate_class=_candidate_class(item),
        predicted_probability=float(candidate.calibrated_probability),
        market_implied_probability=item.market_implied_probability,
        gross_edge=float(candidate.expected_net_edge_r),
        spread_cost=_float(convexity.spread_cost) if convexity else None,
        slippage_estimate=_float(convexity.slippage_cost) if convexity else None,
        fees_estimate=_float(convexity.fee_cost) if convexity else None,
        theta_cost=float(convexity.theta_per_day) if convexity else None,
        execution_uncertainty=_float(convexity.execution_uncertainty) if convexity else None,
        calibration_uncertainty=_float(convexity.calibration_uncertainty) if convexity else None,
        calibration_health=_value(calibration.health) if calibration else "UNKNOWN",
        expected_net_value=(
            _float(portfolio.expected_net_value)
            if portfolio
            else _float(rare.expected_net_value) if rare else None
        ),
        portfolio_penalty=penalty,
        approved_capital=str(portfolio.approved_capital) if portfolio else None,
        approved_quantity=str(portfolio.approved_quantity) if portfolio else None,
        portfolio_brain_outcome=_portfolio_outcome(item),
        a04_outcome=_a04_outcome(item),
        eventual_outcome=None,
        realized_pnl=str(position.realized_pnl) if position else None,
    )


def _map_point(item: CandidateObservation) -> OpportunityMapPoint:
    rare = item.rare_assessment
    convexity = item.convexity_input
    return OpportunityMapPoint(
        candidate_id=str(item.candidate.candidate_id),
        instrument=str(item.candidate.instrument_id),
        underlying=item.underlying or "UNKNOWN",
        candidate_class=_candidate_class(item),
        calibrated_probability=float(item.candidate.calibrated_probability),
        expected_net_value=_float(rare.expected_net_value) if rare else None,
        asymmetry=_float(rare.payoff_asymmetry_ratio) if rare else None,
        liquidity_score=float(convexity.liquidity_score) if convexity else None,
        spread_ticks=None,
        analogue_support=rare.analogue_count if rare else None,
        portfolio_brain_outcome=_portfolio_outcome(item),
        a04_outcome=_a04_outcome(item),
    )


def _lineage(item: CandidateObservation) -> tuple[EvidenceLineageNode, ...]:
    candidate = item.candidate
    nodes = [
        EvidenceLineageNode(
            node_type="OpportunityCandidate",
            node_id=str(candidate.candidate_id),
            timestamp=candidate.created_at,
            status="VERIFIED",
            metrics={"probability": float(candidate.calibrated_probability)},
            hash=str(candidate.payload_hash),
            summary="Canonical R10 opportunity candidate.",
        )
    ]
    if item.rare_assessment is not None:
        rare = item.rare_assessment
        nodes.append(
            EvidenceLineageNode(
                node_type="ConvexityEvidence",
                node_id=str(rare.assessment_id),
                timestamp=candidate.created_at,
                status="VERIFIED" if rare.eligible else "REJECTED",
                metrics={
                    "class": _value(rare.opportunity_class),
                    "analogue_support": rare.analogue_count,
                    "expected_net_value": float(rare.expected_net_value),
                },
                hash=str(rare.payload_hash),
                summary="Canonical R10-X rare-opportunity assessment.",
            )
        )
    if item.portfolio_decision is not None:
        portfolio_decision = item.portfolio_decision
        nodes.append(
            EvidenceLineageNode(
                node_type="PortfolioAllocationDecision",
                node_id=str(portfolio_decision.decision_id),
                timestamp=candidate.created_at,
                status=(
                    "VERIFIED"
                    if _value(portfolio_decision.outcome).startswith("ALLOW")
                    else "REJECTED"
                ),
                metrics={"outcome": _value(portfolio_decision.outcome)},
                hash=str(portfolio_decision.payload_hash),
                summary="Canonical Portfolio Brain allocation decision.",
            )
        )
    if item.risk_decision is not None:
        risk_decision = item.risk_decision
        nodes.append(
            EvidenceLineageNode(
                node_type="A04Decision",
                node_id=str(risk_decision.risk_decision_id),
                timestamp=risk_decision.decided_at,
                status=(
                    "VERIFIED" if _value(risk_decision.decision) == "ALLOW" else "REJECTED"
                ),
                metrics={"outcome": _value(risk_decision.decision)},
                hash=str(risk_decision.payload_hash),
                summary="Canonical deterministic A04 risk decision.",
            )
        )
    return tuple(nodes)


def build_operator_snapshot(
    source: OperatorProjectionInput,
    *,
    runtime: RuntimeProviderState | None = None,
) -> OperatorIntelligenceSnapshot:
    """Build a presentation snapshot exclusively from caller-supplied canonical facts."""
    fresh = sum(item.source_state is SourceState.LIVE for item in source.instruments)
    stale = sum(item.source_state is SourceState.STALE for item in source.instruments)
    invalid = sum(not item.reference_valid for item in source.instruments)
    classes = [_candidate_class(item) for item in source.candidates]
    portfolio_rejected = sum(
        _portfolio_outcome(item) in {PortfolioBrainOutcome.DEFER, PortfolioBrainOutcome.DENY}
        for item in source.candidates
    )
    a04_rejected = sum(_a04_outcome(item) is A04Outcome.DENY for item in source.candidates)
    source_state = SourceState.UNKNOWN
    if source.provenance is ProvenanceType.REPLAY:
        source_state = SourceState.REPLAY
    elif source.provenance is ProvenanceType.FIXTURE:
        source_state = SourceState.FIXTURE
    elif not source.instruments:
        source_state = SourceState.UNKNOWN
    elif fresh == 0:
        source_state = SourceState.STALE
    else:
        source_state = SourceState.LIVE
    entries = tuple(_edge_entry(item) for item in source.candidates)
    agents: list[AgentAccountabilityEntry] = []
    timeline: list[TimelineEvent] = []
    for item in source.agents:
        advisory = item.advisory
        agents.append(
            AgentAccountabilityEntry(
                agent_id=item.agent_id,
                role=item.role,
                status=item.status,
                last_wake=advisory.created_at if advisory else None,
                wake_reason=item.wake_reason,
                data_cutoff=item.data_cutoff,
                evidence_refs=tuple(str(ref) for ref in advisory.evidence_refs) if advisory else (),
                recommendation=_value(advisory.recommendation) if advisory else None,
                proposal_id=item.proposal_id,
                authority="ADVISORY_ONLY",
                latency_ms=advisory.latency_ms if advisory else None,
                provider_model=(
                    f"{advisory.model_id}/{advisory.model_version}" if advisory else None
                ),
                tool_calls_count=item.tool_calls_count,
                is_stale=item.is_stale,
            )
        )
        if advisory is not None:
            timeline.append(
                TimelineEvent(
                    event_id=str(advisory.advisory_id),
                    timestamp=advisory.created_at,
                    material_event=item.wake_reason or "AGENT_ADVISORY",
                    agent_wake=item.role,
                    evidence_queried=tuple(str(ref) for ref in advisory.evidence_refs),
                    recommendation=_value(advisory.recommendation),
                    proposal_id=item.proposal_id,
                    governor_result=GovernorResult.UNKNOWN,
                )
            )
    return OperatorIntelligenceSnapshot(
        scanner=OpportunityScannerReadModel(
            last_scan_at=source.as_of,
            data_cutoff=source.data_cutoff,
            source_state=source_state,
            funnel=FunnelCounts(
                universe_observed=len(source.instruments),
                fresh=fresh,
                stale=stale,
                invalid_reference=invalid,
            ),
            rejections=RejectionBreakdown(
                liquidity=sum(_has_reason(item, "LIQUIDITY") for item in source.candidates)
                + source.rejection_counts.get("liquidity", 0),
                spread=sum(_has_reason(item, "SPREAD") for item in source.candidates)
                + source.rejection_counts.get("spread", 0),
                calibration=sum(
                    item.calibration is not None and _value(item.calibration.health) != "HEALTHY"
                    for item in source.candidates
                )
                + source.rejection_counts.get("insufficient_calibration_support", 0),
                negative_ev=sum(
                    _has_reason(item, "NEGATIVE_NET")
                    or (
                        item.rare_assessment is not None
                        and item.rare_assessment.expected_net_value <= 0
                    )
                    for item in source.candidates
                )
                + source.rejection_counts.get("negative_net_ev", 0),
                portfolio_capacity=portfolio_rejected
                + source.rejection_counts.get("portfolio_concentration", 0),
                a04=a04_rejected + source.rejection_counts.get("a04", 0),
                neutral_thesis=(
                    source.rejection_counts.get("neutral_thesis", 0)
                    if source.rejection_counts
                    else sum(_has_reason(item, "NEUTRAL") for item in source.candidates)
                ),
            ),
            candidates_by_class=CandidateClassCounts(
                standard=classes.count(CandidateClass.STANDARD),
                high_conviction=classes.count(CandidateClass.HIGH_CONVICTION),
                convex=classes.count(CandidateClass.CONVEX),
                rare_event=classes.count(CandidateClass.RARE_EVENT),
            ),
            candidate_ids=tuple(str(item.candidate.candidate_id) for item in source.candidates),
        ),
        edge_ledger=EdgeLedgerReadModel(
            entries=entries,
            as_of=source.as_of,
            source=source.provenance,
        ),
        survival=_survival(runtime, as_of=source.as_of),
        agents=tuple(agents),
        timeline=tuple(timeline),
        opportunity_map=tuple(_map_point(item) for item in source.candidates),
        evidence_lineage={
            str(item.candidate.candidate_id): _lineage(item) for item in source.candidates
        },
        provenance=source.provenance,
    )


__all__ = [
    "AgentObservation",
    "CandidateObservation",
    "InstrumentObservation",
    "OperatorProjectionInput",
    "RuntimeStateReader",
    "build_operator_snapshot",
]
