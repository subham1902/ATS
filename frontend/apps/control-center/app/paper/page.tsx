"use client";

import React, { useEffect, useState, useCallback } from "react";

// ---------------------------------------------------------------------------
// Design Tokens & Aesthetic Styling
// ---------------------------------------------------------------------------

const S = {
  container: {
    minHeight: "100vh",
    background: "linear-gradient(180deg, #090d16 0%, #05080f 100%)",
    color: "#f8fafc",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    padding: "24px 28px",
    display: "flex" as const,
    flexDirection: "column" as const,
    gap: 20,
    boxSizing: "border-box" as const,
  },
  card: {
    background: "rgba(15, 23, 42, 0.75)",
    border: "1px solid rgba(51, 65, 85, 0.65)",
    borderRadius: 14,
    padding: "18px 20px",
    boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
    backdropFilter: "blur(12px)",
  },
  header: {
    display: "flex" as const,
    justifyContent: "space-between" as const,
    alignItems: "center" as const,
    flexWrap: "wrap" as const,
    gap: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: 800,
    letterSpacing: "-0.02em",
    color: "#ffffff",
    margin: 0,
    display: "flex" as const,
    alignItems: "center" as const,
    gap: 10,
  },
  subtitle: {
    fontSize: 12,
    color: "#94a3b8",
    margin: "4px 0 0 0",
    fontWeight: 400,
  },
  pill: (bg: string, color: string, border: string) => ({
    background: bg,
    color: color,
    border: `1px solid ${border}`,
    borderRadius: 6,
    padding: "3px 9px",
    fontSize: 11,
    fontWeight: 700,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    display: "inline-flex" as const,
    alignItems: "center" as const,
    gap: 5,
  }),
  tabContainer: {
    display: "flex" as const,
    borderBottom: "1px solid rgba(51, 65, 85, 0.6)",
    gap: 4,
    overflowX: "auto" as const,
  },
  tab: (active: boolean) => ({
    padding: "10px 18px",
    fontSize: 13,
    fontWeight: active ? 700 : 500,
    color: active ? "#ffffff" : "#94a3b8",
    background: active ? "rgba(99, 102, 241, 0.16)" : "transparent",
    border: "none",
    borderBottom: active ? "2px solid #818cf8" : "2px solid transparent",
    cursor: "pointer",
    display: "flex" as const,
    alignItems: "center" as const,
    gap: 8,
    borderRadius: "8px 8px 0 0",
    transition: "all 0.15s ease",
  }),
  grid2: {
    display: "grid" as const,
    gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
    gap: 18,
  },
  grid4: {
    display: "grid" as const,
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 14,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.06em",
    color: "#cbd5e1",
    marginBottom: 12,
    display: "flex" as const,
    alignItems: "center" as const,
    gap: 8,
  },
  input: {
    width: "100%",
    background: "rgba(15, 23, 42, 0.9)",
    border: "1px solid rgba(71, 85, 105, 0.7)",
    borderRadius: 8,
    padding: "9px 12px",
    color: "#ffffff",
    fontSize: 13,
    fontFamily: "inherit",
    boxSizing: "border-box" as const,
  },
  select: {
    width: "100%",
    background: "rgba(15, 23, 42, 0.9)",
    border: "1px solid rgba(71, 85, 105, 0.7)",
    borderRadius: 8,
    padding: "9px 12px",
    color: "#ffffff",
    fontSize: 13,
    fontFamily: "inherit",
    boxSizing: "border-box" as const,
    cursor: "pointer",
  },
  btnPrimary: {
    background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    padding: "10px 20px",
    fontWeight: 700,
    fontSize: 13,
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(79, 70, 229, 0.4)",
    display: "inline-flex" as const,
    alignItems: "center" as const,
    gap: 8,
  },
  btnSecondary: {
    background: "rgba(30, 41, 59, 0.8)",
    color: "#e2e8f0",
    border: "1px solid rgba(71, 85, 105, 0.6)",
    borderRadius: 8,
    padding: "8px 14px",
    fontWeight: 600,
    fontSize: 12,
    cursor: "pointer",
    display: "inline-flex" as const,
    alignItems: "center" as const,
    gap: 6,
  },
  btnPreset: (active: boolean) => ({
    background: active ? "rgba(99, 102, 241, 0.25)" : "rgba(30, 41, 59, 0.6)",
    color: active ? "#ffffff" : "#94a3b8",
    border: active ? "1px solid #818cf8" : "1px solid rgba(71, 85, 105, 0.5)",
    borderRadius: 8,
    padding: "8px 12px",
    fontSize: 12,
    cursor: "pointer",
    textAlign: "left" as const,
  }),
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: 12,
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    color: "#94a3b8",
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
    borderBottom: "1px solid rgba(51, 65, 85, 0.6)",
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid rgba(30, 41, 59, 0.6)",
    color: "#e2e8f0",
  },
};

// ---------------------------------------------------------------------------
// Helpers & Types
// ---------------------------------------------------------------------------

const BE = (path: string) => path;

interface StrategyItem {
  strategy_id: string;
  name: string;
  category: string;
  signals_count: number;
  candidates_count: number;
  a04_approved_count: number;
  capital_denied_count: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  gross_pnl: number;
  friction_costs: number;
  net_pnl: number;
  margin_allocated: number;
  evidence_state: string;
  cost_drag_ratio: number;
  verdict: string;
}

interface TradeItem {
  trade_id: string;
  strategy_id: string;
  symbol: string;
  direction: "LONG" | "SHORT";
  entry_time: string;
  entry_price: number;
  exit_time: string | null;
  exit_price: number | null;
  quantity: number;
  margin_used: number;
  gross_pnl: number;
  friction_costs: number;
  net_pnl: number;
  mfe: number;
  mae: number;
  holding_time_minutes: number;
  exit_reason: string | null;
  status: "OPEN" | "CLOSED";
}

interface CandidateItem {
  candidate_id: string;
  timestamp: string;
  strategy_id: string;
  instrument: string;
  side: "LONG" | "SHORT";
  entry_reference: number;
  stop: number;
  target: number;
  expected_move: number;
  expected_probability: number;
  expected_gross_edge: number;
  estimated_total_friction: number;
  expected_net_edge: number;
  required_break_even_move: number;
  margin_required: number;
  available_capital_before: number;
  candidate_status: string;
  rejection?: { authority: string; reason_code: string; reason_details: string };
}

interface RejectionItem {
  rejection_id: string;
  candidate_id: string;
  decision_time: string;
  authority: string;
  reason_code: string;
  reason_details: string;
  available_capital: number;
  required_margin: number;
  expected_net_edge: number;
}

interface PaperSessionSummary {
  session_id: string;
  campaign_id: string;
  market: string;
  exchange: string;
  instrument: string;
  contract: string;
  mode: string;
  status: string;
  regime: string;
  capital_profile: string;
  stress_mode: string;
  stress_multiplier: number;
  start_time: string;
  end_time: string;
  configuration_hash: string;
  code_hash: string;
  capital: {
    budget_cap: number;
    available_capital: number;
    reserved_capital: number;
    total_equity: number;
    max_drawdown_pct: number;
    utilization_pct: number;
  };
  pnl: { gross_realized: number; friction_costs: number; net_realized: number };
  telemetry: {
    signals_count: number;
    candidates_count: number;
    a04_approved_count: number;
    capital_denied_count: number;
    a04_denied_count?: number;
    economic_denied_count?: number;
    total_trades: number;
    open_positions_count: number;
    zero_broker_orders_verified: boolean;
    live_money_false_verified: boolean;
  };
  strategies: StrategyItem[];
  recent_candidates: CandidateItem[];
  recent_rejections: RejectionItem[];
  recent_trades: TradeItem[];
  open_positions: TradeItem[];
}

interface Preset {
  preset_id: string;
  name: string;
  description: string;
  capital: number;
  duration_minutes: number;
  instrument: string;
  contract: string;
  selected_strategies: string[];
  max_concurrent_positions: number;
  max_trades_limit: number;
  position_policy: string;
  stop_loss_mode: string;
  stop_loss_value: number;
  take_profit_mode: string;
  take_profit_value: number;
  trailing_stop_mode: string;
  cost_model_id: string;
  session_exit_policy: string;
}

interface SessionConfig {
  session_name: string;
  capital: number;
  duration_minutes: number;
  instrument: string;
  contract: string;
  selected_strategies: string[];
  max_concurrent_positions: number;
  max_trades_limit: number;
  position_policy: string;
  lot_size: number;
  risk_per_trade_pct: number;
  max_drawdown_pct: number;
  stop_loss_mode: string;
  stop_loss_value: number;
  take_profit_mode: string;
  take_profit_value: number;
  trailing_stop_mode: string;
  trailing_stop_value: number;
  entry_policy: string;
  session_exit_policy: string;
  cost_model_id: string;
}

const DEFAULT_CONFIG: SessionConfig = {
  session_name: "",
  capital: 30000,
  duration_minutes: 60,
  instrument: "GOLDM",
  contract: "MCX GOLDM 25SEP26",
  selected_strategies: ["A04_PROBABILISTIC", "S01_ORB_NR7", "S02_TSMOM", "S04_VOL_TARGET", "S17_PRICE_OI_VOL"],
  max_concurrent_positions: 2,
  max_trades_limit: 10,
  position_policy: "ONE_POSITION_PER_STRATEGY",
  lot_size: 1,
  risk_per_trade_pct: 2.0,
  max_drawdown_pct: 5.0,
  stop_loss_mode: "ATR",
  stop_loss_value: 1.5,
  take_profit_mode: "R_MULTIPLE",
  take_profit_value: 2.0,
  trailing_stop_mode: "DISABLED",
  trailing_stop_value: 1.0,
  entry_policy: "MARKET",
  session_exit_policy: "SESSION_FLATTEN",
  cost_model_id: "MCX_GOLDM_CANONICAL_V1",
};

const ALL_STRATEGIES = [
  { id: "A04_PROBABILISTIC", name: "A04 Probabilistic Governor", category: "GOVERNOR", margin: "₹18,000" },
  { id: "S01_ORB_NR7", name: "S01 ORB NR7 Breakout", category: "INTRADAY MOMENTUM", margin: "₹15,000" },
  { id: "S02_TSMOM", name: "S02 Time-Series Momentum", category: "TREND FOLLOWING", margin: "₹16,500" },
  { id: "S03_DONCHIAN_ATR", name: "S03 Donchian Channel ATR", category: "VOLATILITY BREAKOUT", margin: "₹14,000" },
  { id: "S04_VOL_TARGET", name: "S04 Volatility Target Scaler", category: "RISK SCALER", margin: "₹12,500" },
  { id: "S17_PRICE_OI_VOL", name: "S17 Price+OI+Vol State Machine", category: "ORDERFLOW", margin: "₹20,000" },
  { id: "S34_REGIME_ROUTER", name: "S34 Multi-Regime Adaptive", category: "META ROUTER", margin: "₹17,000" },
  { id: "B02_NAIVE_BREAKOUT", name: "B02 Naive High/Low Breakout", category: "BASELINE", margin: "₹15,000" },
  { id: "B00_NO_TRADE", name: "B00 Zero Risk Cash Control", category: "BASELINE", margin: "₹0" },
];

function fmtInr(val: number): string {
  const p = val >= 0 ? "+" : "-";
  return `${p}₹${Math.abs(val).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pnlColor(val: number): string {
  if (val > 0) return "#34d399";
  if (val < 0) return "#f87171";
  return "#94a3b8";
}

function VerdictBadge({ verdict }: { verdict: string }) {
  if (verdict === "SURVIVED_PASSED")
    return <span style={S.pill("rgba(5, 150, 105, 0.2)", "#34d399", "#059669")}>✓ SURVIVED</span>;
  if (verdict === "COST_DRAGGED_LOSS")
    return <span style={S.pill("rgba(217, 119, 6, 0.2)", "#fbbf24", "#d97706")}>⚠ COST DRAG</span>;
  if (verdict === "CONTROL_BASELINE")
    return <span style={S.pill("rgba(30, 41, 59, 0.6)", "#94a3b8", "#475569")}>○ BASELINE</span>;
  return <span style={S.pill("rgba(220, 38, 38, 0.2)", "#f87171", "#dc2626")}>✕ LOSS</span>;
}

function SafetyGuarantees() {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {["LIVE_MONEY = False", "Zero Broker Orders", "A2_PAPER Mode", "Evidence Vault Active"].map((label) => (
        <span key={label} style={S.pill("rgba(6, 78, 59, 0.4)", "#6ee7b7", "#047857")}>
          ✓ {label}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NEW SESSION TAB
// ---------------------------------------------------------------------------

function NewPaperSessionTab({ onSessionStarted }: { onSessionStarted: (s: PaperSessionSummary) => void }) {
  const [config, setConfig] = useState<SessionConfig>({ ...DEFAULT_CONFIG });
  const [presets, setPresets] = useState<Preset[]>([]);
  const [validation, setValidation] = useState<null | {
    status: string;
    reason_codes: string[];
    warnings: string[];
    effective_config?: Record<string, number | string>;
  }>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [_result, setResult] = useState<null | { status: string; session?: PaperSessionSummary }>(null);

  useEffect(() => {
    fetch(BE("/v1/runtime/paper_session/presets"))
      .then((r) => r.json())
      .then((d) => setPresets(d.presets || []))
      .catch(() => {});
  }, []);

  const applyPreset = (p: Preset) => {
    setConfig((prev) => ({
      ...prev,
      capital: p.capital,
      duration_minutes: p.duration_minutes,
      selected_strategies: p.selected_strategies || prev.selected_strategies,
      max_concurrent_positions: p.max_concurrent_positions,
      max_trades_limit: p.max_trades_limit,
      position_policy: p.position_policy,
      stop_loss_mode: p.stop_loss_mode,
      take_profit_mode: p.take_profit_mode,
      trailing_stop_mode: p.trailing_stop_mode,
      cost_model_id: p.cost_model_id,
    }));
    setValidation(null);
    setResult(null);
  };

  const doValidate = async () => {
    setIsValidating(true);
    try {
      const res = await fetch(BE("/v1/runtime/paper_session/validate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      setValidation(await res.json());
    } catch {
      setValidation({ status: "ERROR", reason_codes: ["FETCH_FAILED"], warnings: [] });
    } finally {
      setIsValidating(false);
    }
  };

  const doStart = async () => {
    setIsRunning(true);
    try {
      const res = await fetch(BE("/v1/runtime/paper_session/start"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      setResult(data);
      if (data.session) onSessionStarted(data.session);
    } catch {
      setResult({ status: "FAILED" });
    } finally {
      setIsRunning(false);
    }
  };

  const toggleStrategy = (id: string) => {
    setConfig((prev) => ({
      ...prev,
      selected_strategies: prev.selected_strategies.includes(id)
        ? prev.selected_strategies.filter((s) => s !== id)
        : [...prev.selected_strategies, id],
    }));
    setValidation(null);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Quick Presets */}
      <div style={S.card}>
        <div style={S.sectionTitle}>
          <span style={{ color: "#f59e0b" }}>◈</span> Quick Presets
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {presets.map((p) => (
            <button
              key={p.preset_id}
              onClick={() => applyPreset(p)}
              style={S.btnPreset(config.capital === p.capital && config.duration_minutes === p.duration_minutes)}
            >
              <div style={{ fontWeight: 700, color: "#ffffff" }}>{p.name}</div>
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                ₹{(p.capital / 1000).toFixed(0)}K · {p.duration_minutes}m · {p.max_concurrent_positions} pos
              </div>
            </button>
          ))}
          <button
            onClick={() => {
              setConfig({ ...DEFAULT_CONFIG });
              setValidation(null);
              setResult(null);
            }}
            style={S.btnSecondary}
          >
            ↺ Reset
          </button>
        </div>
      </div>

      <div style={S.grid2}>
        {/* Capital & Duration */}
        <div style={S.card}>
          <div style={S.sectionTitle}>
            <span style={{ color: "#34d399" }}>₹</span> Capital & Duration
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 6 }}>Budget (INR)</label>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                {[10000, 30000, 50000, 100000].map((amt) => (
                  <button
                    key={amt}
                    onClick={() => setConfig((prev) => ({ ...prev, capital: amt }))}
                    style={S.btnPreset(config.capital === amt)}
                  >
                    ₹{amt / 1000}K
                  </button>
                ))}
              </div>
              <input
                type="number"
                value={config.capital}
                onChange={(e) => setConfig((prev) => ({ ...prev, capital: Number(e.target.value) }))}
                style={S.input}
              />
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 6 }}>Duration</label>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {[15, 30, 60, 90, 120, 180].map((m) => (
                  <button
                    key={m}
                    onClick={() => setConfig((prev) => ({ ...prev, duration_minutes: m }))}
                    style={S.btnPreset(config.duration_minutes === m)}
                  >
                    {m < 60 ? `${m}m` : `${m / 60}h`}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                Session Name (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Gold Multi-Breakout Stress Test"
                value={config.session_name}
                onChange={(e) => setConfig((prev) => ({ ...prev, session_name: e.target.value }))}
                style={S.input}
              />
            </div>
          </div>
        </div>

        {/* Positions & Risk */}
        <div style={S.card}>
          <div style={S.sectionTitle}>
            <span style={{ color: "#818cf8" }}>⚖</span> Positions & Risk
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                Max Concurrent Positions: {config.max_concurrent_positions}
              </label>
              <div style={{ display: "flex", gap: 6 }}>
                {[1, 2, 3, 5, 10].map((n) => (
                  <button
                    key={n}
                    onClick={() => setConfig((prev) => ({ ...prev, max_concurrent_positions: n }))}
                    style={S.btnPreset(config.max_concurrent_positions === n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 6 }}>
                Max Trades Limit: {config.max_trades_limit}
              </label>
              <input
                type="range"
                min="1"
                max="50"
                value={config.max_trades_limit}
                onChange={(e) => setConfig((prev) => ({ ...prev, max_trades_limit: Number(e.target.value) }))}
                style={{ width: "100%", accentColor: "#6366f1" }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                  Position Policy
                </label>
                <select
                  value={config.position_policy}
                  onChange={(e) => setConfig((prev) => ({ ...prev, position_policy: e.target.value }))}
                  style={S.select}
                >
                  <option value="ONE_POSITION_PER_STRATEGY">1 per Strategy</option>
                  <option value="ALLOW_MULTIPLE">Allow Multiple</option>
                  <option value="ONE_POSITION_PER_INSTRUMENT">1 per Instrument</option>
                  <option value="NET_BY_INSTRUMENT">Net by Instrument</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>Cost Model</label>
                <select
                  value={config.cost_model_id}
                  onChange={(e) => setConfig((prev) => ({ ...prev, cost_model_id: e.target.value }))}
                  style={S.select}
                >
                  <option value="MCX_GOLDM_CANONICAL_V1">Canonical MCX (Standard)</option>
                  <option value="RESEARCH_V2">Research V2</option>
                  <option value="STRESS_1_5X">1.5X Stress Friction</option>
                  <option value="STRESS_2X">2.0X Stress Friction</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                  Stop Loss Mode
                </label>
                <select
                  value={config.stop_loss_mode}
                  onChange={(e) => setConfig((prev) => ({ ...prev, stop_loss_mode: e.target.value }))}
                  style={S.select}
                >
                  <option value="ATR">ATR Multiplier</option>
                  <option value="FIXED">Fixed Points</option>
                  <option value="PERCENT">Percentage</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                  Take Profit Mode
                </label>
                <select
                  value={config.take_profit_mode}
                  onChange={(e) => setConfig((prev) => ({ ...prev, take_profit_mode: e.target.value }))}
                  style={S.select}
                >
                  <option value="R_MULTIPLE">R-Multiple</option>
                  <option value="FIXED">Fixed Points</option>
                  <option value="PERCENT">Percentage</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Strategies Multi-Select */}
      <div style={S.card}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={S.sectionTitle}>
            <span style={{ color: "#eab308" }}>⚡</span> Registered Strategies ({config.selected_strategies.length}{" "}
            active)
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              onClick={() => setConfig((prev) => ({ ...prev, selected_strategies: ALL_STRATEGIES.map((s) => s.id) }))}
              style={S.btnSecondary}
            >
              Select All
            </button>
            <button onClick={() => setConfig((prev) => ({ ...prev, selected_strategies: [] }))} style={S.btnSecondary}>
              Clear
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
          {ALL_STRATEGIES.map((s) => {
            const active = config.selected_strategies.includes(s.id);
            return (
              <div
                key={s.id}
                onClick={() => toggleStrategy(s.id)}
                style={{
                  background: active ? "rgba(79, 70, 229, 0.15)" : "rgba(30, 41, 59, 0.4)",
                  border: active ? "1px solid #6366f1" : "1px solid rgba(51, 65, 85, 0.5)",
                  borderRadius: 10,
                  padding: "10px 14px",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: active ? "#ffffff" : "#cbd5e1" }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                    {s.category} · Margin: {s.margin}
                  </div>
                </div>
                <div
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 4,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: active ? "#4f46e5" : "transparent",
                    border: active ? "none" : "1px solid #475569",
                    color: "#ffffff",
                    fontSize: 11,
                    fontWeight: 800,
                  }}
                >
                  {active ? "✓" : ""}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Validation & Launch Actions */}
      <div
        style={{
          ...S.card,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
        }}
      >
        <div>
          {validation && (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={S.pill(
                  validation.status === "VALID"
                    ? "rgba(5, 150, 105, 0.2)"
                    : validation.status === "WARNING"
                      ? "rgba(217, 119, 6, 0.2)"
                      : "rgba(220, 38, 38, 0.2)",
                  validation.status === "VALID" ? "#34d399" : validation.status === "WARNING" ? "#fbbf24" : "#f87171",
                  validation.status === "VALID" ? "#059669" : validation.status === "WARNING" ? "#d97706" : "#dc2626",
                )}
              >
                {validation.status === "VALID"
                  ? "✓ Configuration Valid"
                  : validation.status === "WARNING"
                    ? "⚠ Configuration Warning"
                    : "✕ Blocked"}
              </span>
              {validation.warnings.length > 0 && (
                <span style={{ fontSize: 12, color: "#fbbf24" }}>{validation.warnings.join("; ")}</span>
              )}
              {validation.reason_codes.length > 0 && (
                <span style={{ fontSize: 12, color: "#f87171" }}>{validation.reason_codes.join(", ")}</span>
              )}
            </div>
          )}
          {!validation && (
            <span style={{ fontSize: 12, color: "#94a3b8" }}>
              Pre-flight validation required before starting execution.
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={doValidate} disabled={isValidating} style={S.btnSecondary}>
            {isValidating ? "Validating..." : "Validate Configuration"}
          </button>
          <button
            onClick={doStart}
            disabled={isRunning || config.selected_strategies.length === 0}
            style={S.btnPrimary}
          >
            {isRunning ? "Starting Session..." : `▶ Launch Paper Session (₹${config.capital.toLocaleString("en-IN")})`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SESSION HISTORY TAB
// ---------------------------------------------------------------------------

function SessionHistoryTab({ onSwitchToNew }: { onSwitchToNew: () => void }) {
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(BE("/v1/runtime/paper_session/history"))
      .then((r) => r.json())
      .then((d) => setHistory(d.sessions || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={S.sectionTitle}>
          <span style={{ color: "#38bdf8" }}>📋</span> Session History ({history.length} archived sessions)
        </div>
        <button onClick={onSwitchToNew} style={S.btnPrimary}>
          + New Paper Session
        </button>
      </div>

      <div style={S.card}>
        {loading ? (
          <div style={{ textAlign: "center", padding: "30px 0", color: "#94a3b8", fontSize: 13 }}>
            Loading archived sessions...
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Session ID</th>
                  <th style={S.th}>Start Time</th>
                  <th style={S.th}>Instrument</th>
                  <th style={S.th}>Capital</th>
                  <th style={S.th}>Duration</th>
                  <th style={S.th}>Trades</th>
                  <th style={S.th}>Net P&L</th>
                  <th style={S.th}>Friction</th>
                  <th style={S.th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((s, i) => (
                  <tr key={String(s.session_id || i)}>
                    <td style={{ ...S.td, fontFamily: "monospace", fontWeight: 700, color: "#818cf8" }}>
                      {String(s.session_id)}
                    </td>
                    <td style={S.td}>
                      {String(s.start_time || "")
                        .substring(0, 19)
                        .replace("T", " ")}
                    </td>
                    <td style={S.td}>
                      <span style={S.pill("rgba(30, 41, 59, 0.6)", "#e2e8f0", "#475569")}>{String(s.instrument)}</span>
                    </td>
                    <td style={S.td}>₹{Number(s.capital || 0).toLocaleString("en-IN")}</td>
                    <td style={S.td}>{String(s.duration_minutes)}m</td>
                    <td style={S.td}>{String(s.trades_count)}</td>
                    <td style={{ ...S.td, fontWeight: 700, color: pnlColor(Number(s.net_pnl || 0)) }}>
                      {fmtInr(Number(s.net_pnl || 0))}
                    </td>
                    <td style={S.td}>₹{Number(s.friction_costs || 0).toFixed(2)}</td>
                    <td style={S.td}>
                      <span style={S.pill("rgba(5, 150, 105, 0.2)", "#34d399", "#059669")}>{String(s.status)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CAMPAIGN VALIDATION TAB
// ---------------------------------------------------------------------------

function CampaignValidationTab() {
  const [campaign, setCampaign] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const fetch_ = useCallback(async () => {
    try {
      const r = await fetch(BE("/v1/runtime/paper_campaign"));
      if (r.ok) setCampaign(await r.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch_();
  }, [fetch_]);

  const runSession = async (regime: string, stress: string) => {
    setRunning(true);
    try {
      await fetch(BE("/v1/runtime/paper_campaign/run_session"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget: 30000, regime, stress_mode: stress, start_price: 75420 }),
      });
      await fetch_();
    } finally {
      setRunning(false);
    }
  };

  if (loading)
    return <div style={{ textAlign: "center", padding: "40px 0", color: "#94a3b8" }}>Loading campaign data...</div>;

  const c = campaign;
  const totals = c?.aggregate_totals as Record<string, number> | undefined;
  const evidence = (c?.strategy_evidence as Record<string, unknown>[]) || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {c && (
        <div style={S.grid4}>
          {[
            { label: "Total Sessions", value: String(c.total_sessions ?? 0), color: "#ffffff" },
            { label: "Valid Sessions", value: String(c.valid_sessions_count ?? 0), color: "#34d399" },
            { label: "Total Trades", value: String(totals?.total_trades ?? 0), color: "#ffffff" },
            { label: "Net P&L", value: fmtInr(totals?.net_pnl ?? 0), color: pnlColor(totals?.net_pnl ?? 0) },
          ].map((k) => (
            <div key={k.label} style={S.card}>
              <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>{k.label}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: k.color, fontFamily: "monospace" }}>{k.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Regimes */}
      <div style={S.card}>
        <div style={S.sectionTitle}>
          <span style={{ color: "#a855f7" }}>◈</span> Empirical Stress Scenarios
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {[
            { regime: "VOLATILE_EXPANSION", label: "Volatile Expansion" },
            { regime: "RANGE_BOUND_CHOP", label: "Range Bound Chop" },
            { regime: "TREND_CONTINUATION", label: "Trend Continuation" },
          ].map((r) => (
            <button
              key={r.regime}
              onClick={() => runSession(r.regime, "BASE")}
              disabled={running}
              style={S.btnSecondary}
            >
              ▶ Run {r.label}
            </button>
          ))}
        </div>

        {/* Strategy Evidence Table */}
        <div style={{ overflowX: "auto" }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Strategy</th>
                <th style={S.th}>Trades</th>
                <th style={S.th}>Win Rate</th>
                <th style={S.th}>Gross P&L</th>
                <th style={S.th}>Friction</th>
                <th style={S.th}>Net P&L</th>
                <th style={S.th}>Cost Drag</th>
                <th style={S.th}>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((s, i) => (
                <tr key={String(s.strategy_id || i)}>
                  <td style={{ ...S.td, fontWeight: 700 }}>{String(s.name || s.strategy_id)}</td>
                  <td style={S.td}>{String(s.total_trades ?? 0)}</td>
                  <td style={S.td}>{Number(s.win_rate ?? 0).toFixed(1)}%</td>
                  <td style={S.td}>₹{Number(s.gross_pnl ?? 0).toFixed(2)}</td>
                  <td style={S.td}>₹{Number(s.friction ?? 0).toFixed(2)}</td>
                  <td style={{ ...S.td, fontWeight: 700, color: pnlColor(Number(s.net_pnl ?? 0)) }}>
                    {fmtInr(Number(s.net_pnl ?? 0))}
                  </td>
                  <td style={S.td}>{(Number(s.cost_drag_ratio ?? 0) * 100).toFixed(1)}%</td>
                  <td style={S.td}>
                    <VerdictBadge verdict={String(s.verdict || "PENDING")} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// LIVE DASHBOARD TAB
// ---------------------------------------------------------------------------

function LiveDashboardTab({
  sessionData,
  onQuickStart,
}: {
  sessionData: PaperSessionSummary | null;
  onQuickStart: () => void;
}) {
  const s = sessionData;

  if (!s) {
    return (
      <div style={{ ...S.card, textAlign: "center", padding: "60px 20px" }}>
        <div style={{ fontSize: 44, marginBottom: 12 }}>⚡</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "#ffffff", marginBottom: 6 }}>No Active Paper Session</div>
        <div style={{ fontSize: 13, color: "#94a3b8", maxWidth: 440, margin: "0 auto 20px auto" }}>
          Launch a quick ₹30,000 session or use the New Session tab to configure an arbitrary trading tournament.
        </div>
        <button onClick={onQuickStart} style={S.btnPrimary}>
          ▶ Quick Session (₹30K)
        </button>
      </div>
    );
  }

  const pnl = s.pnl || { gross_realized: 0, friction_costs: 0, net_realized: 0 };
  const cap = s.capital || {
    budget_cap: 30000,
    available_capital: 30000,
    reserved_capital: 0,
    max_drawdown_pct: 0,
    utilization_pct: 0,
  };
  const openPos = s.open_positions || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Top Metric Cards */}
      <div style={S.grid4}>
        <div style={S.card}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Net Realized P&L</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: pnlColor(pnl.net_realized), fontFamily: "monospace" }}>
            {fmtInr(pnl.net_realized)}
          </div>
        </div>
        <div style={S.card}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Gross Realized P&L</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#ffffff", fontFamily: "monospace" }}>
            ₹{pnl.gross_realized.toFixed(2)}
          </div>
        </div>
        <div style={S.card}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Total Statutory Friction</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#f87171", fontFamily: "monospace" }}>
            ₹{pnl.friction_costs.toFixed(2)}
          </div>
        </div>
        <div style={S.card}>
          <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>Max Drawdown</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#fbbf24", fontFamily: "monospace" }}>
            {cap.max_drawdown_pct.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Capital Allocation & Active Positions */}
      <div style={S.grid2}>
        <div style={S.card}>
          <div style={S.sectionTitle}>
            <span style={{ color: "#34d399" }}>◈</span> Capital Utilization & Margins
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: "#94a3b8" }}>Available: ₹{cap.available_capital.toLocaleString("en-IN")}</span>
              <span style={{ color: "#fbbf24" }}>Reserved: ₹{cap.reserved_capital.toLocaleString("en-IN")}</span>
              <span style={{ color: "#ffffff", fontWeight: 700 }}>
                Total: ₹{cap.budget_cap.toLocaleString("en-IN")}
              </span>
            </div>
            {/* Progress Bar */}
            <div
              style={{
                width: "100%",
                height: 10,
                borderRadius: 5,
                background: "rgba(30, 41, 59, 0.8)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (cap.reserved_capital / cap.budget_cap) * 100)}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #6366f1 0%, #a855f7 100%)",
                }}
              />
            </div>
            <div style={{ fontSize: 11, color: "#64748b" }}>
              Active positions: {openPos.length} | Closed trades: {s.telemetry.total_trades} | Regime: {s.regime}
            </div>
          </div>
        </div>

        <div style={S.card}>
          <div style={S.sectionTitle}>
            <span style={{ color: "#818cf8" }}>⚡</span> Open Positions ({openPos.length})
          </div>
          {openPos.length === 0 ? (
            <div style={{ fontSize: 12, color: "#64748b", padding: "16px 0", textAlign: "center" }}>
              No active positions open. Capital is fully liquid.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {openPos.map((pos) => (
                <div
                  key={pos.trade_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: "rgba(30, 41, 59, 0.5)",
                    borderRadius: 8,
                    padding: "8px 12px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontWeight: 700, color: "#ffffff" }}>{pos.strategy_id}</span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>
                      {pos.direction} @ ₹{pos.entry_price}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        background: "rgba(56, 189, 248, 0.15)",
                        color: "#38bdf8",
                        padding: "1px 6px",
                        borderRadius: 4,
                        fontFamily: "monospace",
                        border: "1px solid rgba(56, 189, 248, 0.3)",
                      }}
                    >
                      {pos.quantity || 1} {pos.quantity === 1 ? "Lot" : "Lots"} (100g/lot)
                    </span>
                  </div>
                  <span
                    style={S.pill(
                      pos.net_pnl >= 0 ? "rgba(5, 150, 105, 0.2)" : "rgba(220, 38, 38, 0.2)",
                      pos.net_pnl >= 0 ? "#34d399" : "#f87171",
                      pos.net_pnl >= 0 ? "#059669" : "#dc2626",
                    )}
                  >
                    {fmtInr(pos.net_pnl)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Paper Closed Trade History with Lot Size Information */}
      <div style={S.card}>
        <div style={S.sectionTitle}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              width: "100%",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <span>
              <span style={{ color: "#34d399" }}>📋</span> Trade History & Lot Execution Details (
              {s.recent_trades?.length ?? 0})
            </span>
            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 500 }}>Contract: MCX GOLDM · 100g / Lot</span>
          </div>
        </div>
        {!s.recent_trades || s.recent_trades.length === 0 ? (
          <div style={{ fontSize: 12, color: "#64748b", padding: "20px 0", textAlign: "center" }}>
            No trades completed in this session yet. Orders execute automatically as signals trigger.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Time</th>
                  <th style={S.th}>Strategy</th>
                  <th style={S.th}>Side</th>
                  <th style={S.th}>Lots</th>
                  <th style={S.th}>Lot Size</th>
                  <th style={S.th}>Total Qty</th>
                  <th style={S.th}>Entry → Exit</th>
                  <th style={S.th}>Friction</th>
                  <th style={S.th}>Net P&L</th>
                </tr>
              </thead>
              <tbody>
                {s.recent_trades.slice(0, 10).map((t, idx) => (
                  <tr key={t.trade_id || idx}>
                    <td style={{ ...S.td, fontFamily: "monospace", color: "#94a3b8" }}>
                      {t.entry_time?.substring(11, 19) || "—"}
                    </td>
                    <td style={{ ...S.td, fontWeight: 700, color: "#ffffff" }}>{t.strategy_id}</td>
                    <td style={S.td}>
                      <span
                        style={{
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 800,
                          background: t.direction === "LONG" ? "#065f46" : "#7f1d1d",
                          color: "#ffffff",
                        }}
                      >
                        {t.direction}
                      </span>
                    </td>
                    <td style={{ ...S.td, fontFamily: "monospace", fontWeight: 800, color: "#38bdf8" }}>
                      {t.quantity || 1} {t.quantity === 1 ? "Lot" : "Lots"}
                    </td>
                    <td style={{ ...S.td, fontFamily: "monospace", color: "#34d399" }}>100g / lot</td>
                    <td style={{ ...S.td, fontFamily: "monospace", fontWeight: 700, color: "#e2e8f0" }}>
                      {(t.quantity || 1) * 100}g
                    </td>
                    <td style={{ ...S.td, fontFamily: "monospace" }}>
                      ₹{t.entry_price} → ₹{t.exit_price ?? t.entry_price}
                    </td>
                    <td style={{ ...S.td, color: "#f59e0b" }}>₹{(t.friction_costs || 0).toFixed(2)}</td>
                    <td style={{ ...S.td, fontWeight: 800, color: pnlColor(t.net_pnl || 0) }}>
                      {fmtInr(t.net_pnl || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Strategies Performance Table */}
      <div style={S.card}>
        <div style={S.sectionTitle}>
          <span style={{ color: "#38bdf8" }}>🏆</span> Strategy Performance Matrix
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Strategy</th>
                <th style={S.th}>Trades</th>
                <th style={S.th}>Win Rate</th>
                <th style={S.th}>Gross P&L</th>
                <th style={S.th}>Friction</th>
                <th style={S.th}>Net P&L</th>
                <th style={S.th}>Cost Drag</th>
                <th style={S.th}>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {s.strategies.map((strat) => (
                <tr key={strat.strategy_id}>
                  <td style={{ ...S.td, fontWeight: 700 }}>{strat.name}</td>
                  <td style={S.td}>{strat.total_trades}</td>
                  <td style={S.td}>{strat.win_rate.toFixed(1)}%</td>
                  <td style={S.td}>₹{strat.gross_pnl.toFixed(2)}</td>
                  <td style={S.td}>₹{strat.friction_costs.toFixed(2)}</td>
                  <td style={{ ...S.td, fontWeight: 700, color: pnlColor(strat.net_pnl) }}>{fmtInr(strat.net_pnl)}</td>
                  <td style={S.td}>{(strat.cost_drag_ratio * 100).toFixed(1)}%</td>
                  <td style={S.td}>
                    <VerdictBadge verdict={strat.verdict} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MAIN PAGE
// ---------------------------------------------------------------------------

export default function PaperPage() {
  const [tab, setTab] = useState<"dashboard" | "new" | "history" | "campaign">("dashboard");
  const [session, setSession] = useState<PaperSessionSummary | null>(null);

  const fetchSession = useCallback(async () => {
    try {
      const res = await fetch(BE("/v1/runtime/paper_session"));
      if (res.ok) {
        const data = await res.json();
        if (data.session) setSession(data.session);
      }
    } catch {
      // A failed fetch leaves the session panel showing its previous state.
    }
  }, []);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  const handleQuickStart = async () => {
    try {
      const res = await fetch(BE("/v1/runtime/paper_session/start"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ capital: 30000, duration_minutes: 60 }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.session) setSession(data.session);
      }
    } catch {
      // A failed fetch leaves the session panel showing its previous state.
    }
  };

  return (
    <div style={S.container}>
      {/* Header */}
      <div style={S.header}>
        <div>
          <h1 style={S.title}>
            <span style={{ color: "#a855f7" }}>◈</span> Paper Trading Control Center
          </h1>
          <p style={S.subtitle}>Universal empirical validation workspace · A2_PAPER mode · LIVE_MONEY = False</p>
        </div>
        <span style={S.pill("rgba(30, 41, 59, 0.8)", "#34d399", "#059669")}>● ONLINE</span>
      </div>

      {/* Safety Invariants Banner */}
      <SafetyGuarantees />

      {/* Navigation Tabs */}
      <div style={S.tabContainer}>
        <button onClick={() => setTab("dashboard")} style={S.tab(tab === "dashboard")}>
          <span>📊</span> Live Dashboard {session ? `(${fmtInr(session.pnl.net_realized)})` : ""}
        </button>
        <button onClick={() => setTab("new")} style={S.tab(tab === "new")}>
          <span>⚙</span> + New Session
        </button>
        <button onClick={() => setTab("history")} style={S.tab(tab === "history")}>
          <span>📋</span> Session History
        </button>
        <button onClick={() => setTab("campaign")} style={S.tab(tab === "campaign")}>
          <span>🏆</span> Campaign Validation
        </button>
      </div>

      {/* Active Tab View */}
      {tab === "dashboard" && <LiveDashboardTab sessionData={session} onQuickStart={handleQuickStart} />}
      {tab === "new" && (
        <NewPaperSessionTab
          onSessionStarted={(s) => {
            setSession(s);
            setTab("dashboard");
          }}
        />
      )}
      {tab === "history" && <SessionHistoryTab onSwitchToNew={() => setTab("new")} />}
      {tab === "campaign" && <CampaignValidationTab />}
    </div>
  );
}
