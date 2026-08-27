/**
 * Operator Intelligence Contracts & Read-Model Types (OI1 - OI8).
 * Pure presentation + read-model contracts — zero financial mutation authority.
 * Invariant: UNKNOWN is never treated as healthy. All unavailable fields default to null/UNKNOWN.
 */

import type { LossState } from "./types";

export type CandidateClass = "STANDARD" | "HIGH_CONVICTION" | "CONVEX" | "RARE_EVENT";

export type ProvenanceType = "LIVE" | "REPLAY" | "FIXTURE";

export type SourceState = "LIVE" | "REPLAY" | "FIXTURE" | "STALE" | "UNKNOWN";

export type PortfolioBrainOutcome = "ALLOW" | "ALLOW_REDUCED" | "DEFER" | "DENY" | "UNKNOWN";

export type A04Outcome = "ALLOW" | "DENY" | "UNKNOWN";

export type DirectionType = "LONG" | "SHORT" | "CALL" | "PUT" | "INCREASE" | "REDUCE";

export type EventualOutcomeType = "WIN" | "LOSS" | "SCRATCH" | "OPEN" | "UNKNOWN";

export type OperatorSurvivalState =
  | "NORMAL"
  | "CAUTION"
  | "SAFE"
  | "COOLDOWN"
  | "EXIT_ONLY"
  | "HALTED"
  | "UNKNOWN";

export type AgentStatus = "ACTIVE" | "IDLE" | "DEGRADED" | "OFFLINE" | "STALE" | "UNKNOWN";

export type GovernorResult =
  | "APPROVED"
  | "REJECTED"
  | "DEFERRED"
  | "NO_CHANGE"
  | "GOVERNOR_BLOCKED"
  | "UNKNOWN";

export type EvidenceNodeType =
  | "MarketSnapshot"
  | "FeatureBundle"
  | "RegimeEvidence"
  | "EnsembleForecast"
  | "CalibratedOutcomeDistribution"
  | "MarketThesis"
  | "OpportunityCandidate"
  | "PortfolioAllocationDecision"
  | "RiskDecision"
  | "A04Decision"
  | "Position"
  | "TradeReview"
  | "HistoricalAnalogueEvidence"
  | "ConvexityEvidence";

export type FixtureScenarioId =
  | "NORMAL_QUIET_MARKET"
  | "HIGH_CONVICTION_CANDIDATE"
  | "HYPOTHETICAL_CONVEX_CANDIDATE"
  | "HYPOTHETICAL_RARE_EVENT_CANDIDATE"
  | "SAFE_DUE_DRAWDOWN"
  | "HALTED"
  | "HARNESS_UNAVAILABLE"
  | "STALE_AGENT_ADVISORY"
  | "CANDIDATE_REJECTED_PORTFOLIO_BRAIN"
  | "CANDIDATE_DENIED_A04";

// ================================================================
// OI1: OPPORTUNITY SCANNER CONTRACTS
// ================================================================

export interface FunnelCounts {
  universe_observed: number;
  fresh: number;
  stale: number;
  invalid_reference: number;
}

export interface RejectionBreakdown {
  liquidity: number;
  spread: number;
  calibration: number;
  negative_ev: number;
  portfolio_capacity: number;
  a04: number;
}

export interface CandidateClassCounts {
  standard: number;
  high_conviction: number;
  convex: number;
  rare_event: number;
}

export interface OpportunityScannerReadModel {
  last_scan_at: string;
  data_cutoff: string;
  source_state: SourceState;
  funnel: FunnelCounts;
  rejections: RejectionBreakdown;
  candidates_by_class: CandidateClassCounts;
  candidate_ids: string[];
}

// ================================================================
// OI2: EDGE LEDGER CONTRACTS
// ================================================================

export interface EdgeLedgerEntry {
  candidate_id: string;
  timestamp: string;
  underlying: string;
  instrument: string;
  direction: DirectionType;
  strategy: string;
  candidate_class: CandidateClass;
  predicted_probability: number | null;
  market_implied_probability: number | null;
  gross_edge: number | null;
  spread_cost: number | null;
  slippage_estimate: number | null;
  fees_estimate: number | null;
  theta_cost: number | null;
  execution_uncertainty: number | null;
  calibration_uncertainty: number | null;
  expected_net_value: number | null;
  portfolio_penalty: number | null;
  approved_capital: string | null;
  approved_quantity: string | null;
  portfolio_brain_outcome: PortfolioBrainOutcome;
  a04_outcome: A04Outcome;
  eventual_outcome: EventualOutcomeType | null;
  realized_pnl: string | null;
}

export interface EdgeLedgerReadModel {
  entries: EdgeLedgerEntry[];
  as_of: string;
  source: ProvenanceType;
}

// ================================================================
// OI3: ATS SURVIVAL / AUTONOMY TELEMETRY CONTRACTS
// ================================================================

export interface SurvivalTelemetryReadModel {
  effective_survival_state: OperatorSurvivalState;
  user_selected_mode: "SAFE" | "NORMAL" | "AGGRESSIVE" | "UNKNOWN";
  effective_mode: "SAFE" | "NORMAL" | "AGGRESSIVE" | "HALTED" | "UNKNOWN";
  reason_codes: string[];
  session_equity: string | null;
  hwm: string | null;
  drawdown_fraction: string | null;
  available_risk: string | null;
  open_positions: number;
  new_entry_permission: boolean;
  reduction_permission: boolean;
  feed_healthy: boolean;
  broker_healthy: boolean;
  reconciliation_active: boolean;
  loss_state: LossState | "UNKNOWN";
  last_state_at: string;
}

// ================================================================
// OI4: AGENT ACCOUNTABILITY CONTRACTS
// ================================================================

export interface AgentAccountabilityEntry {
  agent_id: string;
  role: string;
  status: AgentStatus;
  last_wake: string | null;
  wake_reason: string | null;
  data_cutoff: string | null;
  evidence_refs: string[];
  recommendation: string | null;
  proposal_id: string | null;
  authority: "ADVISORY_ONLY";
  latency_ms: number | null;
  provider_model: string | null;
  tool_calls_count: number;
  is_stale: boolean;
}

export interface TimelineEvent {
  event_id: string;
  timestamp: string;
  material_event: string;
  agent_wake: string;
  evidence_queried: string[];
  recommendation: string;
  proposal_id: string | null;
  governor_result: GovernorResult;
  authority_note: "ADVISORY_ONLY — deterministic governor authorized";
}

// ================================================================
// OI5: MARKET OPPORTUNITY MAP CONTRACTS
// ================================================================

export interface OpportunityMapPoint {
  candidate_id: string;
  instrument: string;
  underlying: string;
  candidate_class: CandidateClass;
  calibrated_probability: number | null;
  expected_net_value: number | null;
  asymmetry: number | null;
  liquidity_score: number | null;
  spread_ticks: number | null;
  analogue_support: number | null;
  portfolio_brain_outcome: PortfolioBrainOutcome;
  a04_outcome: A04Outcome;
}

// ================================================================
// OI6: EVIDENCE DRILL-DOWN CONTRACTS
// ================================================================

export interface EvidenceLineageNode {
  node_type: EvidenceNodeType;
  node_id: string;
  timestamp: string;
  status: "VERIFIED" | "PENDING" | "REJECTED" | "BYPASSED" | "UNKNOWN";
  metrics: Record<string, string | number | null>;
  hash: string;
  summary: string;
}

// ================================================================
// OI7: FULL OPERATOR INTELLIGENCE SNAPSHOT CONTRACT
// ================================================================

export interface OperatorIntelligenceSnapshot {
  scanner: OpportunityScannerReadModel;
  edge_ledger: EdgeLedgerReadModel;
  survival: SurvivalTelemetryReadModel;
  agents: AgentAccountabilityEntry[];
  timeline: TimelineEvent[];
  opportunity_map: OpportunityMapPoint[];
  evidence_lineage: Record<string, EvidenceLineageNode[]>;
  provenance: ProvenanceType;
  scenario_id?: FixtureScenarioId;
  scenario_description?: string;
}
