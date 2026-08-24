/**
 * Mechanically synchronized types from A05 OpenAPI / ats.api.models.
 * Do not rename backend routes; do not invent shapes.
 * Source: backend/src/ats/api/models.py + domain/governance contracts.
 */

export type SystemState = "READY" | "DEGRADED" | "RECONCILING" | "HALTED" | "UNKNOWN";
export type ReadinessState = "READY" | "DEGRADED" | "NOT_READY" | "UNKNOWN";
export type HealthState = "LIVE" | "READY" | "DEGRADED" | "NOT_READY";
export type TokenViewState = "ISSUED" | "CONSUMED" | "EXPIRED" | "REVOKED" | "INVALID" | "UNKNOWN";
export type LossState = "NORMAL" | "CAUTION" | "COOLDOWN" | "HALTED";
export type AutonomyLevel = "A0" | "A1" | "A2";
export type PolicyStatus = "VALIDATED" | "ACTIVE" | "RETIRED";
export type CampaignStatus =
  | "DRAFT"
  | "VALIDATED"
  | "ACTIVE"
  | "PAUSED"
  | "COMPLETED"
  | "HALTED"
  | "EXPIRED"
  | "REJECTED";
export type CandidateStatus =
  | "CREATED"
  | "ELIGIBLE"
  | "RISK_EVALUATED"
  | "ADVISED"
  | "AUTHORIZED"
  | "REJECTED"
  | "EXPIRED"
  | "CONSUMED";
export type StrategyExecutionMode = "CHAMPION_ONLY" | "ISOLATED_CHALLENGER_PAPER";
export type RiskDirection = "INCREASE" | "REDUCE" | "NEUTRAL";
export type RiskOutcome = "ALLOW" | "DENY" | "UNKNOWN";
export type AdvisoryOutcome = "APPROVE" | "REJECT" | "UNKNOWN";
export type KernelOutcome = "ALLOW" | "DENY" | "UNKNOWN";

export interface ErrorDetail {
  field: string | null;
  issue: string;
}

export interface ErrorEnvelope {
  code: string;
  message: string;
  correlation_id: string;
  details: ErrorDetail[];
}

export interface HealthReadModel {
  status: HealthState;
  ready: boolean;
  reason_codes: string[];
}

export interface SystemReadModel {
  system_state: SystemState;
  system_state_version: number;
  readiness: ReadinessState;
  degradation_indicators: string[];
  loss_state: LossState;
  active_policy_id: string | null;
  active_policy_version: number | null;
  active_campaign_id: string | null;
  active_campaign_version: number | null;
  authority_mode: "A2_PAPER";
  reconciliation_active: boolean;
  halted: boolean;
  last_state_at: string;
  last_event_at: string | null;
}

export interface PolicyReadModel {
  policy_id: string;
  policy_version: number;
  owner_subject: string;
  lifecycle_status: PolicyStatus;
  autonomy_level: AutonomyLevel;
  universe: string[];
  timeframe: "5m";
  event_definition_id: string;
  forecast_horizon_bars: number;
  confidence_threshold: string;
  minimum_calibration_support: number;
  minimum_reward_risk: string;
  valid_from: string;
  valid_until: string;
  activated_at: string | null;
}

export interface PolicyValidationRequest {
  policy: Record<string, unknown>;
  evaluation_time: string;
  timeframe: string;
  event_definition_id: string;
  model_version: string;
  calibrator_version: string;
}

export interface PolicyValidationReadModel {
  outcome: KernelOutcome;
  reason_codes: string[];
}

export interface CampaignReadModel {
  campaign_id: string;
  campaign_version: number;
  name: string;
  scope: "A2_PAPER";
  policy_id: string;
  policy_version: number;
  status: CampaignStatus;
  strategy_execution_mode: StrategyExecutionMode;
  instrument_universe: string[];
  allowed_timeframes: string[];
  max_trades: number;
  max_concurrent_positions: number;
  capital_budget: string;
  start_at: string;
  expires_at: string;
  activated_at: string | null;
}

export interface CandidateReadModel {
  candidate_id: string;
  candidate_version: number;
  instrument_id: string;
  market_context_id: string;
  thesis_id: string;
  thesis_version: number;
  distribution_id: string;
  campaign_id: string;
  campaign_version: number;
  strategy_definition_id: string;
  strategy_definition_version: number;
  calibrated_probability: string;
  expected_net_edge_r: number;
  expected_reward_risk: string;
  status: CandidateStatus;
  risk_decision_id: string | null;
  advisory_id: string | null;
  autonomy_token_id: string | null;
  created_at: string;
  expires_at: string;
}

export interface GovernanceContextReadModel {
  governance_context_id: string;
  action_subject_id: string;
  action_kind: string;
  risk_direction: RiskDirection;
  candidate_id: string | null;
  candidate_version: number | null;
  system_state: SystemState;
  system_state_version: number;
  policy_id: string;
  policy_version: number;
  campaign_id: string | null;
  campaign_version: number | null;
  strategy_definition_id: string;
  strategy_definition_version: number;
  portfolio_version: number;
  market_context_id: string;
  risk_facts_id: string;
  data_quality_state: string;
  data_freshness_ms: number;
  authority_scope: "A2_PAPER";
  source_refs: string[];
  created_at: string;
}

export interface RiskDecisionReadModel {
  risk_decision_id: string;
  decision: RiskOutcome;
  policy_id: string;
  policy_version: number;
  snapshot_sequence: number;
  risk_facts_id: string;
  applicable_rule_ids: string[];
  measured_values: Record<string, string>;
  limits: Record<string, string>;
  loss_state: LossState;
  reason_codes: string[];
  decided_at: string;
}

export interface AdvisoryReadModel {
  advisory_id: string;
  packet_id: string;
  recommendation: AdvisoryOutcome;
  evidence_refs: string[];
  reason_codes: string[];
  uncertainty_flags: string[];
  model_id: string;
  model_version: string;
  latency_ms: number;
  created_at: string;
}

export interface AutonomyTokenReadModel {
  token_id: string;
  scope: "A2_PAPER";
  candidate_id: string;
  policy_id: string;
  policy_version: number;
  risk_decision_id: string;
  advisory_id: string;
  system_state_version: number;
  issued_at: string;
  expires_at: string;
  consumed_at: string | null;
  state: TokenViewState;
}

export interface ActivityReadModel {
  activity_id: string;
  event_kind: string;
  occurred_at: string;
  correlation_id: string;
  trace_id: string | null;
  aggregate_id: string | null;
  aggregate_version: number | null;
  summary: string;
}

export interface ActivityPage {
  items: ActivityReadModel[];
  replay_supported: false;
}

export interface StreamEvent {
  stream_event_id: string;
  event_kind: string;
  occurred_at: string;
  correlation_id: string;
  payload: Record<string, unknown>;
}

export const ROUTES = {
  healthLive: "/health/live",
  healthReady: "/health/ready",
  system: "/v1/system",
  policiesActive: "/v1/policies/active",
  policyById: (id: string) => `/v1/policies/${id}`,
  policyValidate: "/v1/policies/validate",
  campaignById: (id: string) => `/v1/campaigns/${id}`,
  candidateById: (id: string) => `/v1/candidates/${id}`,
  governanceById: (id: string) => `/v1/governance-contexts/${id}`,
  riskDecisionById: (id: string) => `/v1/risk-decisions/${id}`,
  advisoryById: (id: string) => `/v1/advisories/${id}`,
  autonomyTokenById: (id: string) => `/v1/autonomy-tokens/${id}`,
  activity: "/v1/activity",
  stream: "/v1/stream",
} as const;
