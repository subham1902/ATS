export type TruthState = "READY" | "DEGRADED" | "OFFLINE" | "UNKNOWN";

export interface ControlPlaneOverview {
  system: TruthState;
  session: string;
  feed: TruthState;
  broker: TruthState;
  user_mode: "SAFE" | "NORMAL" | "AGGRESSIVE";
  effective_mode: "SAFE" | "NORMAL" | "AGGRESSIVE" | "HALTED";
  mode_reason: string | null;
  underlyings: Array<{ symbol: "NIFTY" | "BANKNIFTY"; price: string | null; freshness: TruthState }>;
  capital: { total: string | null; deployable: string | null; available: string | null; reserved: string | null; inflight: string | null; committed: string | null };
  pnl: { realized: string | null; unrealized: string | null; hwm: string | null; drawdown: string | null };
  positions: number;
  opportunities: number;
  a04_decisions: number;
  portfolio_decisions: number;
  harness: TruthState;
  openrouter: TruthState;
  active_agents: string[];
  champion: string | null;
  challengers: string[];
  experiments: string[];
  activity: string[];
}

export interface EvidenceBackedChatAnswer {
  answer: string;
  authority: "ADVISORY_ONLY";
  evidence_refs: string[];
  proposal_id: string | null;
}
