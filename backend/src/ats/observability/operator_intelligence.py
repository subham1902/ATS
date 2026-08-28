"""Operator Intelligence Read Models and Telemetry Builders (OI1 - OI8).

Read-only presentation and observability seam.
INVARIANTS:
1. AI proposes; deterministic ATS authorizes.
2. A04 remains final authority; Portfolio Brain remains allocation layer.
3. Harness agents remain ADVISORY_ONLY.
4. UNKNOWN is never mapped to healthy (NORMAL).
5. Zero financial mutation authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from ats.contracts.common import UTCDateTime


class CandidateClass(StrEnum):
    STANDARD = "STANDARD"
    HIGH_CONVICTION = "HIGH_CONVICTION"
    CONVEX = "CONVEX"
    RARE_EVENT = "RARE_EVENT"


class ProvenanceType(StrEnum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    FIXTURE = "FIXTURE"


class SourceState(StrEnum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    FIXTURE = "FIXTURE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class PortfolioBrainOutcome(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_REDUCED = "ALLOW_REDUCED"
    DEFER = "DEFER"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class A04Outcome(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class OperatorSurvivalState(StrEnum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    SAFE = "SAFE"
    COOLDOWN = "COOLDOWN"
    EXIT_ONLY = "EXIT_ONLY"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"


class AgentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class GovernorResult(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    NO_CHANGE = "NO_CHANGE"
    GOVERNOR_BLOCKED = "GOVERNOR_BLOCKED"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# OI1: OPPORTUNITY SCANNER MODELS
# ============================================================================


class FunnelCounts(BaseModel):
    universe_observed: int = 0
    fresh: int = 0
    stale: int = 0
    invalid_reference: int = 0


class RejectionBreakdown(BaseModel):
    liquidity: int = 0
    spread: int = 0
    calibration: int = 0
    negative_ev: int = 0
    portfolio_capacity: int = 0
    a04: int = 0
    neutral_thesis: int = 0


class CandidateClassCounts(BaseModel):
    standard: int = 0
    high_conviction: int = 0
    convex: int = 0
    rare_event: int = 0


class OpportunityScannerReadModel(BaseModel):
    last_scan_at: UTCDateTime
    data_cutoff: UTCDateTime
    source_state: SourceState = SourceState.UNKNOWN
    funnel: FunnelCounts = Field(default_factory=FunnelCounts)
    rejections: RejectionBreakdown = Field(default_factory=RejectionBreakdown)
    candidates_by_class: CandidateClassCounts = Field(default_factory=CandidateClassCounts)
    candidate_ids: tuple[str, ...] = ()
    predictions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    recent_predictions: list[dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# OI2: EDGE LEDGER MODELS
# ============================================================================


class EdgeLedgerEntry(BaseModel):
    candidate_id: str
    timestamp: UTCDateTime
    underlying: str
    instrument: str
    direction: str
    strategy: str
    candidate_class: CandidateClass = CandidateClass.STANDARD
    predicted_probability: float | None = None
    market_implied_probability: float | None = None
    gross_edge: float | None = None
    spread_cost: float | None = None
    slippage_estimate: float | None = None
    fees_estimate: float | None = None
    theta_cost: float | None = None
    execution_uncertainty: float | None = None
    calibration_uncertainty: float | None = None
    calibration_health: str = "UNKNOWN"
    expected_net_value: float | None = None
    portfolio_penalty: float | None = None
    approved_capital: str | None = None
    approved_quantity: str | None = None
    portfolio_brain_outcome: PortfolioBrainOutcome = PortfolioBrainOutcome.UNKNOWN
    a04_outcome: A04Outcome = A04Outcome.UNKNOWN
    eventual_outcome: str | None = None
    realized_pnl: str | None = None


class EdgeLedgerReadModel(BaseModel):
    entries: tuple[EdgeLedgerEntry, ...] = ()
    as_of: UTCDateTime
    source: ProvenanceType = ProvenanceType.LIVE


# ============================================================================
# OI3: SURVIVAL TELEMETRY MODELS
# ============================================================================


class SurvivalTelemetryReadModel(BaseModel):
    effective_survival_state: OperatorSurvivalState = OperatorSurvivalState.UNKNOWN
    user_selected_mode: str = "UNKNOWN"
    effective_mode: str = "UNKNOWN"
    reason_codes: tuple[str, ...] = ()
    session_equity: str | None = None
    hwm: str | None = None
    drawdown_fraction: str | None = None
    available_risk: str | None = None
    open_positions: int = 0
    new_entry_permission: bool = False
    reduction_permission: bool = False
    feed_healthy: bool = False
    broker_healthy: bool = False
    reconciliation_active: bool = False
    loss_state: str = "UNKNOWN"
    last_state_at: UTCDateTime


# ============================================================================
# OI4: AGENT ACCOUNTABILITY MODELS
# ============================================================================


class AgentAccountabilityEntry(BaseModel):
    agent_id: str
    role: str
    status: AgentStatus = AgentStatus.UNKNOWN
    last_wake: UTCDateTime | None = None
    wake_reason: str | None = None
    data_cutoff: UTCDateTime | None = None
    evidence_refs: tuple[str, ...] = ()
    recommendation: str | None = None
    proposal_id: str | None = None
    authority: str = "ADVISORY_ONLY"
    latency_ms: int | None = None
    provider_model: str | None = None
    tool_calls_count: int = 0
    is_stale: bool = False


class TimelineEvent(BaseModel):
    event_id: str
    timestamp: UTCDateTime
    material_event: str
    agent_wake: str
    evidence_queried: tuple[str, ...] = ()
    recommendation: str
    proposal_id: str | None = None
    governor_result: GovernorResult = GovernorResult.UNKNOWN
    authority_note: str = "ADVISORY_ONLY — deterministic governor authorized"


class OpportunityMapPoint(BaseModel):
    candidate_id: str
    instrument: str
    underlying: str
    candidate_class: CandidateClass = CandidateClass.STANDARD
    calibrated_probability: float | None = None
    expected_net_value: float | None = None
    asymmetry: float | None = None
    liquidity_score: float | None = None
    spread_ticks: float | None = None
    analogue_support: int | None = None
    portfolio_brain_outcome: PortfolioBrainOutcome = PortfolioBrainOutcome.UNKNOWN
    a04_outcome: A04Outcome = A04Outcome.UNKNOWN


class EvidenceLineageNode(BaseModel):
    node_type: str
    node_id: str
    timestamp: UTCDateTime
    status: str = "UNKNOWN"
    metrics: dict[str, str | int | float | None] = Field(default_factory=dict)
    hash: str
    summary: str


class OperatorIntelligenceSnapshot(BaseModel):
    scanner: OpportunityScannerReadModel
    edge_ledger: EdgeLedgerReadModel
    survival: SurvivalTelemetryReadModel
    agents: tuple[AgentAccountabilityEntry, ...] = ()
    timeline: tuple[TimelineEvent, ...] = ()
    opportunity_map: tuple[OpportunityMapPoint, ...] = ()
    evidence_lineage: dict[str, tuple[EvidenceLineageNode, ...]] = Field(default_factory=dict)
    provenance: ProvenanceType = ProvenanceType.LIVE


# ============================================================================
# DETERMINISTIC SURVIVAL RESOLUTION HELPER
# ============================================================================


def resolve_operator_survival_state(
    *,
    is_halted: bool = False,
    must_flatten: bool = False,
    loss_state: str = "UNKNOWN",
    effective_mode: str = "UNKNOWN",
    can_enter: bool = False,
    can_reduce: bool = False,
    paused_new_entries: bool = False,
    feed_healthy: bool | None = None,
    broker_healthy: bool | None = None,
    system_state: str = "UNKNOWN",
    reconciliation_active: bool = False,
) -> tuple[OperatorSurvivalState, tuple[str, ...]]:
    """Deterministically map runtime metrics to OperatorSurvivalState with zero risk invention."""
    reasons: list[str] = []

    # If completely uninitialized / unverified
    if (
        effective_mode == "UNKNOWN"
        and system_state == "UNKNOWN"
        and loss_state == "UNKNOWN"
        and feed_healthy is None
        and broker_healthy is None
        and not is_halted
        and not must_flatten
        and not paused_new_entries
        and not can_reduce
    ):
        reasons.append("STATE_UNVERIFIED")
        return OperatorSurvivalState.UNKNOWN, tuple(reasons)

    if is_halted or must_flatten or loss_state == "HALTED" or effective_mode == "HALTED":
        reasons.append("SAFETY_HALTED")
        return OperatorSurvivalState.HALTED, tuple(reasons)

    if loss_state == "COOLDOWN" or paused_new_entries:
        reasons.append("COOLDOWN_ACTIVE" if loss_state == "COOLDOWN" else "NEW_ENTRIES_PAUSED")
        return OperatorSurvivalState.COOLDOWN, tuple(reasons)

    if can_reduce and not can_enter and not paused_new_entries:
        reasons.append("EXIT_ONLY_ENFORCED")
        return OperatorSurvivalState.EXIT_ONLY, tuple(reasons)

    if (
        effective_mode == "SAFE"
        or feed_healthy is False
        or broker_healthy is False
        or system_state == "DEGRADED"
        or reconciliation_active
    ):
        if feed_healthy is False:
            reasons.append("FEED_DEGRADED")
        if broker_healthy is False:
            reasons.append("BROKER_DEGRADED")
        if effective_mode == "SAFE":
            reasons.append("SAFE_ENVELOPE")
        if reconciliation_active:
            reasons.append("RECONCILING")
        return OperatorSurvivalState.SAFE, tuple(reasons)

    if loss_state == "CAUTION":
        return OperatorSurvivalState.CAUTION, ("LOSS_CAUTION",)

    if (
        effective_mode in ("NORMAL", "AGGRESSIVE")
        and feed_healthy is True
        and broker_healthy is True
        and system_state == "READY"
        and not is_halted
    ):
        return OperatorSurvivalState.NORMAL, ()

    reasons.append("STATE_UNVERIFIED")
    return OperatorSurvivalState.UNKNOWN, tuple(reasons)


__all__ = [
    "A04Outcome",
    "AgentAccountabilityEntry",
    "AgentStatus",
    "CandidateClass",
    "CandidateClassCounts",
    "EdgeLedgerEntry",
    "EdgeLedgerReadModel",
    "EvidenceLineageNode",
    "FunnelCounts",
    "GovernorResult",
    "OperatorIntelligenceSnapshot",
    "OperatorSurvivalState",
    "OpportunityMapPoint",
    "OpportunityScannerReadModel",
    "PortfolioBrainOutcome",
    "ProvenanceType",
    "RejectionBreakdown",
    "SourceState",
    "SurvivalTelemetryReadModel",
    "TimelineEvent",
    "resolve_operator_survival_state",
]
