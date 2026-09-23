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

export type MarketDataState = "LIVE" | "STALE" | "NO_FEED" | "UNKNOWN";
export type MarketInterval = "1s" | "1m" | "3m" | "5m" | "15m" | "30m" | "1h" | "1d";

export interface CandleView {
  bar_start: string;
  bar_close: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string | null;
  volume: number | null;
  open_interest: number | null;
  tick_count: number;
  is_closed: boolean;
}

export interface CandleSeriesView {
  instrument_key: string;
  contract: string | null;
  interval: MarketInterval;
  state: MarketDataState;
  bar_alignment_offset_minutes: number;
  bar_alignment_note: string;
  source: string | null;
  authority_class: string;
  candles: CandleView[];
  reason_codes: string[];
}

export interface MarketQuoteView {
  instrument_key: string;
  state: MarketDataState;
  contract: string | null;
  last_price: string | null;
  bid_price: string | null;
  ask_price: string | null;
  bid_quantity: number | null;
  ask_quantity: number | null;
  spread: string | null;
  volume: number | null;
  open_interest: number | null;
  open_interest_change: number | null;
  exchange_timestamp: string | null;
  received_at: string | null;
  age_ms: number | null;
  source: string | null;
  authority_class: string;
  reason_codes: string[];
}

export interface FeedHealthView {
  state: MarketDataState;
  attached: boolean;
  source: string | null;
  authority_class: string;
  instruments: string[];
  last_update_at: string | null;
  last_update_age_ms: number | null;
  stale_after_ms: number;
  accepted_updates: number;
  dropped_duplicate: number;
  dropped_out_of_order: number;
  dropped_stale: number;
  subscriber_count: number;
  reason_codes: string[];
  provider_state?: string | null;
  reconnect_count?: number | null;
  events_received?: number | null;
  decode_errors?: number | null;
  quote_age_ms?: number | null;
  trade_age_ms?: number | null;
  depth_age_ms?: number | null;
  oi_age_ms?: number | null;
  stream_clients?: number | null;
}

export interface MarketSnapshotView {
  instrument_key: string;
  state: MarketDataState;
  contract: string | null;
  last_price: string | null;
  bid_price: string | null;
  ask_price: string | null;
  spread: string | null;
  volume: number | null;
  open_interest: number | null;
  open_interest_change: number | null;
  market_session: string | null;
  provider: string | null;
  source: string | null;
  authority_class: string;
  exchange_timestamp: string | null;
  received_at: string | null;
  freshness_ms: number | null;
  sequence: number | null;
  connection_state: MarketDataState;
  reason_codes: string[];
}

export interface StrategyPredictionView {
  strategy_id: string;
  probability_long: number;
  probability_short: number;
  dynamic_sl: string;
  dynamic_tp: string;
  confidence_score: number;
}

export interface MarketStreamFrame {
  frame_kind: "TICK" | "FEED_STATE" | "PREDICTION";
  quote?: MarketQuoteView | null;
  health?: FeedHealthView | null;
  prediction?: StrategyPredictionView | null;
}

export interface RuntimeTradingMode {
  user_selected: string;
  effective: string;
  deescalation_reason: string | null;
}

export interface RuntimeCapitalView {
  available: string;
  reserved: string;
  inflight: string;
  used: string;
  total: string;
}

export interface RuntimePnLView {
  realized: string;
  unrealized: string;
  session_peak: string;
  drawdown_fraction: string;
}

export interface RuntimePositionView {
  position_id: string;
  instrument_id: string;
  quantity: string;
  entry_price: string;
  mark_price: string | null;
  unrealized_pnl: string;
}

export interface RuntimeSessionView {
  phase: string;
  can_enter: boolean;
  can_reduce: boolean;
  must_flatten: boolean;
  is_halted: boolean;
}


export interface RuntimeStatusReadModel {
  session: RuntimeSessionView;
  trading_mode: RuntimeTradingMode;
  capital: RuntimeCapitalView;
  pnl: RuntimePnLView;
  loss_state: LossState;
  open_positions: RuntimePositionView[];
  recent_decisions: Record<string, unknown>[];
  feed_healthy: boolean;
  broker_healthy: boolean;
  halted: boolean;
  paused_new_entries: boolean;
  execution_context: string;
  live_ready: boolean;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Strategy Performance Registry types
// ---------------------------------------------------------------------------

export type StrategyBadge =
  | "SCALPING"
  | "INTRADAY"
  | "SWING"
  | "POSITIONAL"
  | "LONG_TERM"
  | "META_ROUTER"
  | "BASELINE";

export type ExecutionContext =
  | "BACKTEST"
  | "PAPER_TRADE"
  | "SHADOW"
  | "LIVE_FORWARD"
  | "REAL_ACCOUNT";

export type StrategyClassification =
  | "REJECTED"
  | "BLOCKED"
  | "VALIDATED"
  | "DATA_EVALUABLE"
  | "BACKTESTABLE"
  | "RESEARCH_ONLY"
  | "SURVIVOR";

export type EvidenceTier =
  | "ROBUST_FORWARD_CANDIDATE"
  | "PROSPECTIVE_SHADOW"
  | "RESEARCH_ACTIVE"
  | "DATA_BLOCKED"
  | "REJECTED"
  | "BASELINE";

export type StrategyGrade = "S" | "A" | "B" | "C" | "D" | "F";

export interface RatingBreakdown {
  net_expectancy_score: string;
  consistency_score: string;
  cost_resilience_score: string;
  drawdown_score: string;
  sample_quality_score: string;
}

export interface StrategyRating {
  overall: string;
  grade: StrategyGrade;
  breakdown: RatingBreakdown;
}

export interface PerformanceRecord {
  run_id: string;
  strategy_id: string;
  timeframe: string;
  execution_context: ExecutionContext;
  dataset: string;
  capital_budget: string;
  capital_currency: string;
  trades_count: number;
  wins: number;
  losses: number;
  flat: number;
  win_rate: string;
  gross_pnl: string;
  total_costs: string;
  net_pnl: string;
  profit_factor: string;
  max_drawdown: string;
  sharpe_ratio: string | null;
  ev_per_trade: string;
  avg_win: string;
  avg_loss: string;
  payoff_ratio: string;
  cost_1_5x_net: string | null;
  cost_2_0x_net: string | null;
  t_statistic: string | null;
  sample_quality: string;
  measured_at: string;
  span_start: string;
  span_end: string;
}

export interface BestPerformanceSnapshot {
  timeframe: string;
  execution_context: ExecutionContext;
  capital_budget: string;
  net_pnl: string;
  win_rate: string;
  profit_factor: string;
  max_drawdown: string;
  trades_count: number;
  measured_at: string;
}

export interface StrategyRegistryEntry {
  strategy_id: string;
  name: string;
  family: string;
  hypothesis: string;
  badge: StrategyBadge;
  classification: StrategyClassification;
  classification_reason: string;
  evidence_tier: EvidenceTier;
  implementation_status: string;
  rating: StrategyRating;
  best_performance: BestPerformanceSnapshot | null;
  performance_records: PerformanceRecord[];
  data_blocked: boolean;
  blocker_reason: string;
  shadow_status: string;
  paper_readiness: string;
  total_trades: number;
  total_net_pnl: string;
  avg_win_rate: string;
}

export interface LeaderboardEntry {
  rank: number;
  strategy_id: string;
  name: string;
  badge: StrategyBadge;
  rating: StrategyRating;
  best_performance: BestPerformanceSnapshot | null;
  net_pnl: string;
  win_rate: string;
  profit_factor: string;
  max_drawdown: string;
  trades_count: number;
  sharpe_ratio: string | null;
  execution_context: ExecutionContext;
  timeframe: string;
  capital_budget: string;
}

export interface StrategyRegistryOverview {
  total_strategies: number;
  rated_count: number;
  data_blocked_count: number;
  rejected_count: number;
  validated_count: number;
  avg_rating: string;
  top_badge_distribution: Record<string, number>;
  strategies: StrategyRegistryEntry[];
}

export interface LeaderboardResponse {
  timeframe_filter: string | null;
  context_filter: string | null;
  badge_filter: string | null;
  total_ranked: number;
  entries: LeaderboardEntry[];
}

export interface StrategyPerformanceReport {
  strategy: StrategyRegistryEntry;
  performance_by_timeframe: Record<string, PerformanceRecord[]>;
  performance_by_context: Record<string, PerformanceRecord[]>;
  cost_stress_summary: Record<string, string>;
  regime_analysis: Record<string, string>;
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
  marketHealth: "/v1/market/health",
  marketQuote: (instrument?: string) =>
    instrument ? `/v1/market/quote?instrument=${encodeURIComponent(instrument)}` : "/v1/market/quote",
  marketSnapshot: (instrument?: string) =>
    instrument ? `/v1/market/snapshot?instrument=${encodeURIComponent(instrument)}` : "/v1/market/snapshot",
  marketCandles: (interval: string, instrument?: string, limit?: number) => {
    const params = new URLSearchParams({ interval });
    if (instrument) params.set("instrument", instrument);
    if (limit) params.set("limit", String(limit));
    return `/v1/market/candles?${params.toString()}`;
  },
  marketStream: (instrument?: string) =>
    instrument ? `/v1/market/stream?instrument=${encodeURIComponent(instrument)}` : "/v1/market/stream",
  runtimeStatus: "/v1/runtime/status",
  // Strategy Registry & Leaderboard
  strategyRegistry: "/v1/strategies/registry",
  strategyLeaderboard: (timeframe?: string, context?: string, badge?: string) => {
    const params = new URLSearchParams();
    if (timeframe) params.set("timeframe", timeframe);
    if (context) params.set("context", context);
    if (badge) params.set("badge", badge);
    const qs = params.toString();
    return `/v1/strategies/registry/leaderboard${qs ? `?${qs}` : ""}`;
  },
  strategyById: (id: string) => `/v1/strategies/registry/${id}`,
  strategyReport: (id: string) => `/v1/strategies/registry/${id}/report`,
  strategyReload: "/v1/strategies/registry/reload",
} as const;


