"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

interface WorkflowStage {
  stage_id: string;
  stage_number: number;
  name: string;
  category: string;
  description: string;
  authoritative_engine: string;
  status: string;
  invariants: string[];
}

interface GovernanceWorkflowData {
  name: string;
  authority_mode: string;
  live_money: boolean;
  description: string;
  stages: WorkflowStage[];
  system_metrics: Record<string, any>;
  last_updated: string;
}

interface AutonomyTier {
  level: string;
  name: string;
  description: string;
  is_active: boolean;
  live_trading_allowed: boolean;
  human_in_the_loop: string;
}

interface AutonomyData {
  current_level: string;
  description: string;
  live_money_invariant: boolean;
  broker_target: string;
  kill_switch_active: boolean;
  emergency_override: boolean;
  tiers: AutonomyTier[];
  active_tokens: any[];
  security_guarantees: string[];
}

interface GovernedPolicy {
  policy_id: string;
  name: string;
  version: number;
  lifecycle_status: string;
  autonomy_level: string;
  universe: string[];
  timeframe: string;
  min_confidence: number;
  max_leverage: string;
  max_slippage_ticks: number;
  max_drawdown_percent: number;
  trading_hours: string;
  is_active: boolean;
}

interface GovernedCandidate {
  candidate_id: string;
  strategy_id: string;
  instrument: string;
  direction: string;
  entry_price: number;
  expected_edge_r: number;
  calibrated_prob: number;
  status: string;
  rejection_stage: string | null;
  rejection_reason: string | null;
  created_at: string;
}

interface SupervisorAdvisory {
  advisory_id: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  category: string;
  title: string;
  message: string;
  recommendation: string;
  evidence_refs: string[];
  uncertainty_flags: string[];
  acknowledged: boolean;
  created_at: string;
}

const DEFAULT_WORKFLOW_STAGES: WorkflowStage[] = [
  {
    stage_id: "STAGE_1_MARKET_INGESTION",
    stage_number: 1,
    name: "Market Ingestion & Microstructure",
    category: "FEED",
    description:
      "Consumes high-frequency tick streams via Upstox v3 WebSocket and aggregates non-repainting candles with volume deduplication.",
    authoritative_engine: "IncrementalCandleEngine & StreamHub",
    status: "ACTIVE",
    invariants: ["Zero external write capabilities", "Non-blocking tick queue"],
  },
  {
    stage_id: "STAGE_2_ALPHA_GENERATION",
    stage_number: 2,
    name: "Multi-Agent Alpha Generation",
    category: "MODEL",
    description:
      "Autonomous strategy agents (S17 Breakout, S02 VWAP, S04 JEV Shadow) analyze normalized price structures to synthesize opportunity candidates.",
    authoritative_engine: "Strategy Registry & Isolated Adapters",
    status: "ACTIVE",
    invariants: ["Exception isolation per agent", "Zero broker direct access"],
  },
  {
    stage_id: "STAGE_3_PROBABILISTIC_FILTER",
    stage_number: 3,
    name: "Gate 1: A04 Probabilistic Filter",
    category: "GOVERNANCE",
    description:
      "Evaluates Bayesian calibrated probability P(win) and expected economic edge R. Drops candidates that do not exceed statistical edge thresholds.",
    authoritative_engine: "A04 Probabilistic Gate",
    status: "ENFORCED",
    invariants: ["Calibrated P(win) >= 0.52", "Net Edge R >= 1.0x Total Friction"],
  },
  {
    stage_id: "STAGE_4_CAPITAL_GOVERNOR",
    stage_number: 4,
    name: "Gate 2: Capital Governor",
    category: "GOVERNANCE",
    description:
      "Verifies capital sufficiency and margin reserves before granting trade approval. Enforces maximum portfolio allocation caps per trade.",
    authoritative_engine: "Capital Governor & Margin Manager",
    status: "ENFORCED",
    invariants: ["Required Margin <= Available Capital", "Dynamic margin release on exit"],
  },
  {
    stage_id: "STAGE_5_RISK_GOVERNOR",
    stage_number: 5,
    name: "Gate 3: Risk Governor & Circuit Breakers",
    category: "GOVERNANCE",
    description:
      "Enforces portfolio VaR, session drawdown limits, correlation matrix constraints, and concurrent position caps (up to 10 positions).",
    authoritative_engine: "Risk Governor Engine",
    status: "ENFORCED",
    invariants: ["Session Drawdown <= Max Loss Budget", "Active Positions < Max Concurrency Cap"],
  },
  {
    stage_id: "STAGE_6_AUTONOMY_AUTHORITY",
    stage_number: 6,
    name: "Gate 4: Autonomy Token Authority",
    category: "AUTHORITY",
    description:
      "Verifies operational tier (A2_PAPER). Generates a cryptographic, single-use Autonomy Token binding candidate, policy, and risk decision.",
    authoritative_engine: "Autonomy Token Issuer (Safe View)",
    status: "ARMED",
    invariants: ["LIVE_MONEY = False Permanent Invariant", "Single-use token with 60s TTL"],
  },
  {
    stage_id: "STAGE_7_EXECUTION_PAPER_BROKER",
    stage_number: 7,
    name: "Simulated Execution (PaperBroker)",
    category: "EXECUTION",
    description:
      "Routes approved and tokenized candidate to canonical PaperBroker singleton. Deducts margin, creates open position, and logs audit trail.",
    authoritative_engine: "PaperBroker (Singleton)",
    status: "ACTIVE",
    invariants: ["Sole execution target", "Zero external broker orders"],
  },
];

function GovernanceContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") as any;

  const [activeTab, setActiveTab] = useState<"workflow" | "autonomy" | "policies" | "candidates" | "advisories">(
    initialTab && ["workflow", "autonomy", "policies", "candidates", "advisories"].includes(initialTab)
      ? initialTab
      : "workflow",
  );

  const [workflow, setWorkflow] = useState<GovernanceWorkflowData | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomyData | null>(null);
  const [policies, setPolicies] = useState<GovernedPolicy[]>([]);
  const [candidates, setCandidates] = useState<GovernedCandidate[]>([]);
  const [advisories, setAdvisories] = useState<SupervisorAdvisory[]>([]);
  const [_loading, setLoading] = useState(true);

  // Simulator state
  const [simStrategy, setSimStrategy] = useState("ATS-S17");
  const [simDirection, setSimDirection] = useState<"BUY" | "SELL">("BUY");
  const [simPrice, setSimPrice] = useState(74250.0);
  const [simProb, setSimProb] = useState(0.64);
  const [simEdgeR, setSimEdgeR] = useState(1.85);
  const [simMargin, setSimMargin] = useState(25000.0);
  const [simAvailable, setSimAvailable] = useState(100000.0);
  const [simDrawdown, setSimDrawdown] = useState(850.0);
  const [simMaxLoss, setSimMaxLoss] = useState(5000.0);
  const [simPositions, setSimPositions] = useState(1);
  const [simMaxPositions, setSimMaxPositions] = useState(4);
  const [simResult, setSimResult] = useState<any | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      const [wfRes, autoRes, polRes, candRes, advRes] = await Promise.allSettled([
        fetch("/v1/governance/workflow").then((r) => (r.ok ? r.json() : null)),
        fetch("/v1/governance/autonomy").then((r) => (r.ok ? r.json() : null)),
        fetch("/v1/governance/policies").then((r) => (r.ok ? r.json() : [])),
        fetch("/v1/governance/candidates").then((r) => (r.ok ? r.json() : [])),
        fetch("/v1/governance/advisories").then((r) => (r.ok ? r.json() : [])),
      ]);

      if (wfRes.status === "fulfilled" && wfRes.value) setWorkflow(wfRes.value);
      if (autoRes.status === "fulfilled" && autoRes.value) setAutonomy(autoRes.value);
      if (polRes.status === "fulfilled" && polRes.value) setPolicies(polRes.value);
      if (candRes.status === "fulfilled" && candRes.value) setCandidates(candRes.value);
      if (advRes.status === "fulfilled" && advRes.value) setAdvisories(advRes.value);
    } catch (e) {
      console.error("Failed to load governance data", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Run simulation
  const handleRunSimulation = async (customPayload?: any) => {
    setSimulating(true);
    try {
      const payload = customPayload || {
        strategy_id: simStrategy,
        instrument: "MCX:GOLDM26OCTFUT",
        direction: simDirection,
        entry_price: simPrice,
        target_price: simPrice + (simDirection === "BUY" ? 400 : -400),
        stop_loss: simPrice - (simDirection === "BUY" ? 200 : -200),
        expected_edge_r: simEdgeR,
        calibrated_prob: simProb,
        margin_required: simMargin,
        available_capital: simAvailable,
        max_loss_limit: simMaxLoss,
        current_drawdown: simDrawdown,
        current_concurrent_positions: simPositions,
        max_concurrent_positions: simMaxPositions,
        autonomy_level: "A2_PAPER",
      };

      const res = await fetch("/v1/governance/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
      }
    } catch (e) {
      console.error("Simulation error", e);
    } finally {
      setSimulating(false);
    }
  };

  // Preset loaders for simulator
  const loadPreset = (preset: "PASS_ALL" | "FAIL_PROB" | "FAIL_CAPITAL" | "FAIL_RISK") => {
    if (preset === "PASS_ALL") {
      setSimStrategy("ATS-S17");
      setSimDirection("BUY");
      setSimPrice(74250.0);
      setSimProb(0.65);
      setSimEdgeR(1.95);
      setSimMargin(25000.0);
      setSimAvailable(100000.0);
      setSimDrawdown(500.0);
      setSimMaxLoss(5000.0);
      setSimPositions(1);
      setSimMaxPositions(4);
    } else if (preset === "FAIL_PROB") {
      setSimStrategy("ATS-S02");
      setSimDirection("SELL");
      setSimPrice(74320.0);
      setSimProb(0.44); // Below 0.52 hurdle
      setSimEdgeR(0.75);
      setSimMargin(25000.0);
      setSimAvailable(100000.0);
      setSimDrawdown(500.0);
      setSimMaxLoss(5000.0);
      setSimPositions(0);
      setSimMaxPositions(4);
    } else if (preset === "FAIL_CAPITAL") {
      setSimStrategy("ATS-S17");
      setSimDirection("BUY");
      setSimPrice(74250.0);
      setSimProb(0.68);
      setSimEdgeR(2.1);
      setSimMargin(140000.0); // Exceeds 100k
      setSimAvailable(100000.0);
      setSimDrawdown(500.0);
      setSimMaxLoss(5000.0);
      setSimPositions(0);
      setSimMaxPositions(4);
    } else if (preset === "FAIL_RISK") {
      setSimStrategy("ATS-S04");
      setSimDirection("BUY");
      setSimPrice(74280.0);
      setSimProb(0.61);
      setSimEdgeR(1.7);
      setSimMargin(25000.0);
      setSimAvailable(100000.0);
      setSimDrawdown(5400.0); // Breached 5000 max loss
      setSimMaxLoss(5000.0);
      setSimPositions(1);
      setSimMaxPositions(4);
    }
  };

  // Acknowledge advisory
  const handleAcknowledge = async (id: string) => {
    try {
      const res = await fetch(`/v1/governance/advisories/${id}/acknowledge`, { method: "POST" });
      if (res.ok) {
        setAdvisories((prev) => prev.map((a) => (a.advisory_id === id ? { ...a, acknowledged: true } : a)));
      }
    } catch (e) {
      console.error("Failed to acknowledge advisory", e);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #090d16 0%, #05080f 100%)",
        color: "#f8fafc",
        padding: "24px 32px",
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 24,
          paddingBottom: 20,
          borderBottom: "1px solid rgba(51, 65, 85, 0.4)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 24 }}>🏛️</span>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
              Governance & Agent Execution Center
            </h1>
            <span
              style={{
                fontSize: 11,
                padding: "3px 10px",
                borderRadius: 20,
                fontWeight: 700,
                background: "rgba(16, 185, 129, 0.15)",
                color: "#34d399",
                border: "1px solid rgba(16, 185, 129, 0.3)",
              }}
            >
              A2_PAPER AUTONOMOUS
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#94a3b8" }}>
            Deterministic 7-stage multi-agent governance pipeline from live tick ingestion to simulated PaperBroker
            execution.
          </p>
        </div>

        {/* Global Security Badges */}
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div
            style={{
              padding: "6px 14px",
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              color: "#38bdf8",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#38bdf8" }} />
            LIVE_MONEY = False (Permanent Invariant)
          </div>

          <div
            style={{
              padding: "6px 14px",
              background: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(139, 92, 246, 0.3)",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 600,
              color: "#a78bfa",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span>🏦</span>
            Target: PaperBroker Only
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 24,
          borderBottom: "1px solid rgba(51, 65, 85, 0.4)",
          paddingBottom: 8,
          overflowX: "auto",
        }}
      >
        {[
          { id: "workflow", label: "🧭 Agent Workflow to Execution", badge: "7 Stages" },
          { id: "autonomy", label: "🔑 Autonomy & Tokens", badge: "A2 Active" },
          { id: "policies", label: "📋 Active Policies", badge: String(policies.length) },
          { id: "candidates", label: "🎯 Opportunity Candidates", badge: String(candidates.length) },
          { id: "advisories", label: "💡 Supervisor Advisories", badge: String(advisories.length) },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              padding: "8px 18px",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              transition: "all 0.15s ease",
              background:
                activeTab === tab.id ? "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)" : "rgba(15, 23, 42, 0.6)",
              color: activeTab === tab.id ? "#ffffff" : "#94a3b8",
              boxShadow: activeTab === tab.id ? "0 4px 12px rgba(99, 102, 241, 0.3)" : "none",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>{tab.label}</span>
            <span
              style={{
                fontSize: 10,
                padding: "1px 6px",
                borderRadius: 10,
                background: activeTab === tab.id ? "rgba(255, 255, 255, 0.25)" : "rgba(51, 65, 85, 0.6)",
                color: activeTab === tab.id ? "#ffffff" : "#94a3b8",
              }}
            >
              {tab.badge}
            </span>
          </button>
        ))}
      </div>

      {/* TAB 1: WORKFLOW & SIMULATOR */}
      {activeTab === "workflow" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Top Stage Pipeline Bar */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: "20px 24px",
              boxShadow: "0 8px 32px rgba(0, 0, 0, 0.37)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                Sequential Agent Decision Pipeline till Trade Execution
              </h2>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>
                Deterministic gating: Every trade candidate must pass 4 consecutive safety gates
              </span>
            </div>

            {/* Stages Row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                gap: 12,
              }}
            >
              {(workflow?.stages || DEFAULT_WORKFLOW_STAGES).map((s: WorkflowStage) => (
                <div
                  key={s.stage_id}
                  style={{
                    background: "rgba(30, 41, 59, 0.6)",
                    border: "1px solid rgba(71, 85, 105, 0.4)",
                    borderRadius: 10,
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    position: "relative",
                  }}
                >
                  <div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 6,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          color: "#818cf8",
                          letterSpacing: "0.05em",
                        }}
                      >
                        STAGE 0{s.stage_number}
                      </span>
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: s.status === "ACTIVE" ? "rgba(16, 185, 129, 0.2)" : "rgba(99, 102, 241, 0.2)",
                          color: s.status === "ACTIVE" ? "#34d399" : "#a5b4fc",
                        }}
                      >
                        {s.status}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9", marginBottom: 4 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.4 }}>{s.description}</div>
                  </div>

                  <div style={{ marginTop: 12, paddingTop: 8, borderTop: "1px solid rgba(51, 65, 85, 0.4)" }}>
                    <div style={{ fontSize: 10, color: "#64748b" }}>ENGINE:</div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "#cbd5e1" }}>{s.authoritative_engine}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Candidate Simulator Workspace */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(340px, 1fr) minmax(420px, 1.3fr)",
              gap: 20,
            }}
          >
            {/* Input Controls & Presets */}
            <div
              style={{
                background: "rgba(15, 23, 42, 0.75)",
                border: "1px solid rgba(51, 65, 85, 0.5)",
                borderRadius: 14,
                padding: 20,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  🧪 Interactive Candidate Simulator
                </h3>
                <span style={{ fontSize: 11, color: "#818cf8", fontWeight: 600 }}>Test Any Candidate</span>
              </div>
              <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 0, marginBottom: 16 }}>
                Simulate how the 4 sequential governance gates evaluate a strategy signal in real-time.
              </p>

              {/* Quick Presets */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", marginBottom: 6 }}>QUICK PRESETS:</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button
                    onClick={() => loadPreset("PASS_ALL")}
                    style={{
                      padding: "5px 10px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: "rgba(16, 185, 129, 0.15)",
                      color: "#34d399",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      cursor: "pointer",
                    }}
                  >
                    ✓ High-Edge Scalp (Passes)
                  </button>
                  <button
                    onClick={() => loadPreset("FAIL_PROB")}
                    style={{
                      padding: "5px 10px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: "rgba(239, 68, 68, 0.15)",
                      color: "#f87171",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      cursor: "pointer",
                    }}
                  >
                    ✗ Low Probability (Fails Gate 1)
                  </button>
                  <button
                    onClick={() => loadPreset("FAIL_CAPITAL")}
                    style={{
                      padding: "5px 10px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: "rgba(245, 158, 11, 0.15)",
                      color: "#fbbf24",
                      border: "1px solid rgba(245, 158, 11, 0.3)",
                      cursor: "pointer",
                    }}
                  >
                    ✗ Over-Margin (Fails Gate 2)
                  </button>
                  <button
                    onClick={() => loadPreset("FAIL_RISK")}
                    style={{
                      padding: "5px 10px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 600,
                      background: "rgba(239, 68, 68, 0.15)",
                      color: "#f87171",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      cursor: "pointer",
                    }}
                  >
                    ✗ Drawdown Breach (Fails Gate 3)
                  </button>
                </div>
              </div>

              {/* Form Controls */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>Strategy</label>
                  <select
                    value={simStrategy}
                    onChange={(e) => setSimStrategy(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  >
                    <option value="ATS-S17">ATS-S17 (Breakout Momentum)</option>
                    <option value="ATS-S02">ATS-S02 (VWAP Mean Reversion)</option>
                    <option value="ATS-S04">ATS-S04 (JEV Shadow Engine)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>Direction</label>
                  <select
                    value={simDirection}
                    onChange={(e) => setSimDirection(e.target.value as any)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  >
                    <option value="BUY">BUY (Long)</option>
                    <option value="SELL">SELL (Short)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Calibrated P(win) (Gate 1 ≥ 0.52)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={simProb}
                    onChange={(e) => setSimProb(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Expected Edge (Gate 1 ≥ 1.0R)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    value={simEdgeR}
                    onChange={(e) => setSimEdgeR(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Margin Required (₹)
                  </label>
                  <input
                    type="number"
                    step="5000"
                    value={simMargin}
                    onChange={(e) => setSimMargin(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Available Capital (₹)
                  </label>
                  <input
                    type="number"
                    step="5000"
                    value={simAvailable}
                    onChange={(e) => setSimAvailable(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Current Drawdown (₹)
                  </label>
                  <input
                    type="number"
                    step="500"
                    value={simDrawdown}
                    onChange={(e) => setSimDrawdown(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 11, color: "#94a3b8", display: "block", marginBottom: 4 }}>
                    Max Loss Limit (₹)
                  </label>
                  <input
                    type="number"
                    step="500"
                    value={simMaxLoss}
                    onChange={(e) => setSimMaxLoss(parseFloat(e.target.value) || 0)}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      borderRadius: 6,
                      background: "rgba(30, 41, 59, 0.8)",
                      border: "1px solid rgba(71, 85, 105, 0.6)",
                      color: "#f8fafc",
                      fontSize: 12,
                    }}
                  />
                </div>
              </div>

              {/* Run Test Button */}
              <button
                onClick={() => handleRunSimulation()}
                disabled={simulating}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 700,
                  background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                  color: "#ffffff",
                  border: "none",
                  cursor: simulating ? "not-allowed" : "pointer",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.35)",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                {simulating ? "Evaluating Gates..." : "⚡ Run Live Workflow Test"}
              </button>
            </div>

            {/* Simulation Results & Forensics */}
            <div
              style={{
                background: "rgba(15, 23, 42, 0.75)",
                border: "1px solid rgba(51, 65, 85, 0.5)",
                borderRadius: 14,
                padding: 20,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  📊 Gate Traversal Forensics
                </h3>
                {simResult && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "3px 10px",
                      borderRadius: 20,
                      background:
                        simResult.overall_outcome === "APPROVED_AND_EXECUTED"
                          ? "rgba(16, 185, 129, 0.2)"
                          : "rgba(239, 68, 68, 0.2)",
                      color: simResult.overall_outcome === "APPROVED_AND_EXECUTED" ? "#34d399" : "#f87171",
                      border: `1px solid ${
                        simResult.overall_outcome === "APPROVED_AND_EXECUTED"
                          ? "rgba(16, 185, 129, 0.4)"
                          : "rgba(239, 68, 68, 0.4)"
                      }`,
                    }}
                  >
                    {simResult.overall_outcome}
                  </span>
                )}
              </div>

              {!simResult ? (
                <div
                  style={{
                    padding: 32,
                    textAlign: "center",
                    color: "#64748b",
                    fontSize: 13,
                    border: "1px dashed rgba(71, 85, 105, 0.4)",
                    borderRadius: 10,
                  }}
                >
                  <div>
                    Select a preset or adjust candidate inputs, then click <strong>Run Live Workflow Test</strong> to
                    view step-by-step gate evaluation.
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {simResult.stage_results.map((st: any, i: number) => (
                    <div
                      key={i}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: st.passed ? "rgba(16, 185, 129, 0.08)" : "rgba(239, 68, 68, 0.1)",
                        border: `1px solid ${st.passed ? "rgba(16, 185, 129, 0.25)" : "rgba(239, 68, 68, 0.35)"}`,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: st.passed ? "#34d399" : "#f87171" }}>
                          {st.passed ? "✓" : "✗"} {st.gate_name}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: st.passed ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                            color: st.passed ? "#34d399" : "#f87171",
                          }}
                        >
                          {st.status}
                        </span>
                      </div>

                      <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 4 }}>{st.details}</div>

                      <div style={{ display: "flex", gap: 16, fontSize: 10, color: "#94a3b8", marginTop: 6 }}>
                        <span>
                          <strong>Measured:</strong> {st.measured}
                        </span>
                        <span>
                          <strong>Hurdle:</strong> {st.threshold}
                        </span>
                      </div>
                    </div>
                  ))}

                  {/* Issued Token Box if passed */}
                  {simResult.issued_token && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: 12,
                        borderRadius: 8,
                        background: "rgba(99, 102, 241, 0.12)",
                        border: "1px solid rgba(99, 102, 241, 0.3)",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#a5b4fc", marginBottom: 4 }}>
                        🔑 Autonomy Token Granted: {simResult.issued_token.token_id}
                      </div>
                      <div style={{ fontSize: 11, color: "#cbd5e1" }}>
                        Scope: <strong>{simResult.issued_token.scope}</strong> · Fingerprint:{" "}
                        {simResult.issued_token.sha256_fingerprint} · TTL: 60s
                      </div>
                      <div style={{ fontSize: 10, color: "#818cf8", marginTop: 4 }}>
                        Safe View: Cryptographic signature verified; nonces protected. Order authorized for PaperBroker
                        simulated fill.
                      </div>
                    </div>
                  )}

                  {/* Simulated Execution Details */}
                  {simResult.execution_preview && (
                    <div
                      style={{
                        marginTop: 4,
                        padding: 12,
                        borderRadius: 8,
                        background: "rgba(16, 185, 129, 0.1)",
                        border: "1px solid rgba(16, 185, 129, 0.25)",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#34d399", marginBottom: 4 }}>
                        ⚡ Simulated Execution (PaperBroker): Filled at ₹
                        {simResult.execution_preview.fill_price.toLocaleString()}
                      </div>
                      <div style={{ fontSize: 11, color: "#cbd5e1" }}>
                        Margin Reserved: ₹{simResult.execution_preview.margin_reserved.toLocaleString()} · Remaining
                        Available: ₹{simResult.execution_preview.available_capital_after.toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: AUTONOMY & TOKENS */}
      {activeTab === "autonomy" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Autonomy Active Banner */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 24,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                flexWrap: "wrap",
                gap: 16,
              }}
            >
              <div>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#34d399", letterSpacing: "0.05em" }}>
                  OPERATIONAL AUTONOMY TIER
                </span>
                <h2 style={{ fontSize: 20, fontWeight: 800, margin: "4px 0 8px", color: "#f8fafc" }}>
                  A2_PAPER: Autonomous Paper Execution
                </h2>
                <p style={{ margin: 0, fontSize: 13, color: "#94a3b8", maxWidth: 650 }}>
                  {autonomy?.description ||
                    "Full autonomous multi-agent pipeline operating exclusively within the PaperBroker simulation boundary. Automated candidate evaluation, risk gating, and position tracking with zero live capital exposure."}
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
                <span
                  style={{
                    padding: "4px 12px",
                    borderRadius: 20,
                    fontSize: 11,
                    fontWeight: 700,
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "#34d399",
                    border: "1px solid rgba(16, 185, 129, 0.4)",
                  }}
                >
                  ✓ KILL-SWITCH ARMED & NORMAL
                </span>
                <span style={{ fontSize: 11, color: "#64748b" }}>Hardware Lock: LIVE_MONEY = False</span>
              </div>
            </div>

            {/* Guarantees Matrix */}
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid rgba(51, 65, 85, 0.4)" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 10 }}>
                HARD-CODED SECURITY & SAFETY GUARANTEES:
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 10 }}>
                {(autonomy?.security_guarantees || []).map((g, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: 12,
                      color: "#94a3b8",
                      padding: "8px 12px",
                      background: "rgba(30, 41, 59, 0.5)",
                      borderRadius: 6,
                      border: "1px solid rgba(71, 85, 105, 0.3)",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span style={{ color: "#34d399" }}>🛡️</span>
                    <span>{g}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Autonomy Tier Hierarchy Table */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 20,
            }}
          >
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: "0 0 16px", color: "#f8fafc" }}>
              ATS Autonomy Level Hierarchy (A0 to A5)
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {(autonomy?.tiers || []).map((tier) => (
                <div
                  key={tier.level}
                  style={{
                    padding: "14px 18px",
                    borderRadius: 10,
                    background: tier.is_active ? "rgba(16, 185, 129, 0.1)" : "rgba(30, 41, 59, 0.4)",
                    border: `1px solid ${tier.is_active ? "rgba(16, 185, 129, 0.4)" : "rgba(71, 85, 105, 0.3)"}`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 800,
                        padding: "3px 8px",
                        borderRadius: 6,
                        background: tier.is_active ? "#10b981" : "rgba(71, 85, 105, 0.5)",
                        color: "#ffffff",
                      }}
                    >
                      {tier.level}
                    </span>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9" }}>{tier.name}</div>
                      <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>{tier.description}</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <span style={{ fontSize: 11, color: "#cbd5e1" }}>
                      <strong>Human Role:</strong> {tier.human_in_the_loop}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "3px 8px",
                        borderRadius: 4,
                        background: tier.is_active ? "rgba(16, 185, 129, 0.2)" : "rgba(148, 163, 184, 0.1)",
                        color: tier.is_active ? "#34d399" : "#94a3b8",
                      }}
                    >
                      {tier.is_active ? "CURRENT STATE" : "INACTIVE"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: POLICIES */}
      {activeTab === "policies" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 20,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "#f8fafc" }}>Governed Policy Registry</h3>
                <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94a3b8" }}>
                  Formal risk and boundary policies enforcing strategy constraints.
                </p>
              </div>
              <Link
                href="/policies"
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  background: "rgba(99, 102, 241, 0.2)",
                  color: "#a5b4fc",
                  border: "1px solid rgba(99, 102, 241, 0.4)",
                  textDecoration: "none",
                }}
              >
                Open Policies Workspace →
              </Link>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
              {policies.map((p) => (
                <div
                  key={p.policy_id}
                  style={{
                    background: p.is_active ? "rgba(99, 102, 241, 0.08)" : "rgba(30, 41, 59, 0.4)",
                    border: `1px solid ${p.is_active ? "rgba(99, 102, 241, 0.4)" : "rgba(71, 85, 105, 0.3)"}`,
                    borderRadius: 10,
                    padding: 16,
                  }}
                >
                  <div
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}
                  >
                    <span style={{ fontSize: 11, fontWeight: 700, color: "#818cf8" }}>{p.policy_id}</span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: p.is_active ? "rgba(16, 185, 129, 0.2)" : "rgba(148, 163, 184, 0.15)",
                        color: p.is_active ? "#34d399" : "#94a3b8",
                      }}
                    >
                      {p.is_active ? "ACTIVE" : p.lifecycle_status}
                    </span>
                  </div>

                  <div style={{ fontSize: 15, fontWeight: 700, color: "#f1f5f9", marginBottom: 12 }}>{p.name}</div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11 }}>
                    <div style={{ color: "#94a3b8" }}>
                      Timeframe: <strong style={{ color: "#cbd5e1" }}>{p.timeframe}</strong>
                    </div>
                    <div style={{ color: "#94a3b8" }}>
                      Min Confidence: <strong style={{ color: "#cbd5e1" }}>{p.min_confidence}</strong>
                    </div>
                    <div style={{ color: "#94a3b8" }}>
                      Max Leverage: <strong style={{ color: "#cbd5e1" }}>{p.max_leverage}</strong>
                    </div>
                    <div style={{ color: "#94a3b8" }}>
                      Max Drawdown: <strong style={{ color: "#cbd5e1" }}>{p.max_drawdown_percent}%</strong>
                    </div>
                    <div style={{ color: "#94a3b8" }}>
                      Max Slippage: <strong style={{ color: "#cbd5e1" }}>{p.max_slippage_ticks} ticks</strong>
                    </div>
                    <div style={{ color: "#94a3b8" }}>
                      Hours: <strong style={{ color: "#cbd5e1" }}>{p.trading_hours}</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: CANDIDATES */}
      {activeTab === "candidates" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 20,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  Live Opportunity Candidates Funnel
                </h3>
                <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94a3b8" }}>
                  Recent candidate proposals generated by strategy agents and evaluated across all gates.
                </p>
              </div>
              <Link
                href="/candidates"
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  background: "rgba(99, 102, 241, 0.2)",
                  color: "#a5b4fc",
                  border: "1px solid rgba(99, 102, 241, 0.4)",
                  textDecoration: "none",
                }}
              >
                Open Candidates Workspace →
              </Link>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {candidates.map((c) => (
                <div
                  key={c.candidate_id}
                  style={{
                    padding: 14,
                    borderRadius: 8,
                    background:
                      c.status === "EXECUTED" || c.status === "APPROVED"
                        ? "rgba(16, 185, 129, 0.08)"
                        : "rgba(30, 41, 59, 0.5)",
                    border: `1px solid ${
                      c.status === "EXECUTED" || c.status === "APPROVED"
                        ? "rgba(16, 185, 129, 0.25)"
                        : "rgba(71, 85, 105, 0.3)"
                    }`,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 13, fontWeight: 800, color: "#f1f5f9" }}>{c.candidate_id}</span>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 4,
                          background: c.direction === "BUY" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                          color: c.direction === "BUY" ? "#34d399" : "#f87171",
                        }}
                      >
                        {c.direction} {c.instrument}
                      </span>
                      <span style={{ fontSize: 11, color: "#818cf8" }}>{c.strategy_id}</span>
                    </div>

                    <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
                      <span>
                        Price: <strong>₹{c.entry_price.toLocaleString()}</strong>
                      </span>
                      <span>
                        Edge R: <strong>{c.expected_edge_r}R</strong>
                      </span>
                      <span>
                        P(win): <strong>{c.calibrated_prob}</strong>
                      </span>
                    </div>

                    {c.rejection_reason && (
                      <div style={{ fontSize: 11, color: "#f87171", marginTop: 4 }}>
                        ↳ Denied at {c.rejection_stage}: {c.rejection_reason}
                      </div>
                    )}
                  </div>

                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 800,
                      padding: "4px 10px",
                      borderRadius: 6,
                      background:
                        c.status === "EXECUTED"
                          ? "rgba(16, 185, 129, 0.2)"
                          : c.status === "APPROVED"
                            ? "rgba(99, 102, 241, 0.2)"
                            : "rgba(239, 68, 68, 0.2)",
                      color: c.status === "EXECUTED" ? "#34d399" : c.status === "APPROVED" ? "#a5b4fc" : "#f87171",
                    }}
                  >
                    {c.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: ADVISORIES */}
      {activeTab === "advisories" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 20,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  Active Supervisor Advisories & Risk Notices
                </h3>
                <p style={{ margin: "4px 0 0", fontSize: 12, color: "#94a3b8" }}>
                  Real-time market regime, capital allocation, and risk alerts from the supervisor subsystem.
                </p>
              </div>
              <Link
                href="/advisories"
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  background: "rgba(99, 102, 241, 0.2)",
                  color: "#a5b4fc",
                  border: "1px solid rgba(99, 102, 241, 0.4)",
                  textDecoration: "none",
                }}
              >
                Open Advisories Workspace →
              </Link>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {advisories.map((a) => (
                <div
                  key={a.advisory_id}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    background:
                      a.severity === "CRITICAL"
                        ? "rgba(239, 68, 68, 0.12)"
                        : a.severity === "WARNING"
                          ? "rgba(245, 158, 11, 0.1)"
                          : "rgba(56, 189, 248, 0.08)",
                    border: `1px solid ${
                      a.severity === "CRITICAL"
                        ? "rgba(239, 68, 68, 0.3)"
                        : a.severity === "WARNING"
                          ? "rgba(245, 158, 11, 0.3)"
                          : "rgba(56, 189, 248, 0.25)"
                    }`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background:
                              a.severity === "CRITICAL" ? "#ef4444" : a.severity === "WARNING" ? "#f59e0b" : "#0284c7",
                            color: "#ffffff",
                          }}
                        >
                          {a.severity}
                        </span>
                        <span style={{ fontSize: 11, color: "#94a3b8" }}>{a.category}</span>
                        <span style={{ fontSize: 11, color: "#64748b" }}>· {a.advisory_id}</span>
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: "#f8fafc", margin: "6px 0 4px" }}>
                        {a.title}
                      </div>
                      <div style={{ fontSize: 12, color: "#cbd5e1", lineHeight: 1.4 }}>{a.message}</div>
                      <div style={{ fontSize: 12, color: "#38bdf8", marginTop: 6, fontWeight: 600 }}>
                        ↳ Recommendation: {a.recommendation}
                      </div>
                    </div>

                    <button
                      onClick={() => handleAcknowledge(a.advisory_id)}
                      disabled={a.acknowledged}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 6,
                        fontSize: 11,
                        fontWeight: 700,
                        border: "none",
                        cursor: a.acknowledged ? "default" : "pointer",
                        background: a.acknowledged ? "rgba(148, 163, 184, 0.2)" : "rgba(16, 185, 129, 0.2)",
                        color: a.acknowledged ? "#94a3b8" : "#34d399",
                      }}
                    >
                      {a.acknowledged ? "✓ Acknowledged" : "Acknowledge"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function GovernancePage() {
  return (
    <Suspense
      fallback={
        <div style={{ minHeight: "100vh", background: "#090d16", color: "#94a3b8", padding: 32 }}>
          Loading Governance & Agent Execution Center...
        </div>
      }
    >
      <GovernanceContent />
    </Suspense>
  );
}
