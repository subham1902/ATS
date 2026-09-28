"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";

interface StrategyItem {
  id: string;
  name: string;
  archetype: string;
  description: string;
  status: "UNTESTED" | "TESTING" | "PROMOTED" | "ELIMINATED";
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  net_pnl: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  max_drawdown: number;
  assigned_agent: string | null;
  rejection_reason: string | null;
  created_at: string;
  last_tested: string | null;
  store_rank?: number;
  leaderboard_rank?: number;
  leaderboard_score?: number;
  leaderboard_grade?: string;
  leaderboard_badge?: string;
  hypothesis: string;
  parameters: Record<string, any>;
}

interface LedgerEvent {
  timestamp: string;
  event_type:
    | "PROMOTED_TO_STORE"
    | "TRADE_SETTLED"
    | "ELIMINATED_PRUNED"
    | "NEW_CANDIDATE_INTRODUCED"
    | "TESTING_CLAIMED"
    | "RE_INCUBATED";
  strategy_id: string;
  strategy_name: string;
  agent?: string;
  direction?: string;
  entry_price?: number;
  exit_price?: number;
  pnl_change?: number;
  net_pnl?: number;
  currency_symbol?: string;
  win_rate?: number;
  profit_factor?: number;
  details: string;
}

interface LabState {
  summary: {
    total_strategies: number;
    best_in_store: number;
    under_testing: number;
    untested_incubator: number;
    eliminated_archive: number;
  };
  best_store: StrategyItem[];
  under_testing: StrategyItem[];
  untested_incubator: StrategyItem[];
  eliminated_archive: StrategyItem[];
  ledger: LedgerEvent[];
}

interface AgentInfo {
  id: string;
  name: string;
  avatar: string;
  specialization: string;
  max_principal: number;
  available_capital: number;
  pnl: number;
  win_rate: number;
  total_tests: number;
  winning_tests: number;
  active_strategy: string;
  active_strategy_name: string;
  active_strategy_status: string;
  horizon?: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
  target_net_pnl_increment?: number;
  strategy_retests?: number;
  strategy_net_pnl?: number;
  strategy_wins?: number;
  strategy_losses?: number;
  strategy_edge_status?: string;
  condition_status?: {
    matched: boolean;
    regime_type: string;
    condition_name: string;
    condition_label: string;
    strength_score: number;
    recommended_direction?: string | null;
  };
  guidelines?: {
    allowed_lot_size: number;
    max_principal: number;
    target_market: string;
    mode: string;
    direction_bias: string;
    strategy_id: string;
    strategy_name: string;
    horizon?: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
    target_net_pnl_increment?: number;
  };
}

interface TestInLiveMarketModalState {
  open: boolean;
  agentName: string;
  strategyId: string;
  strategyName: string;
  market: string;
  principal: number;
  allowedLotSize: number;
  horizon: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
  directionBias: "BOTH" | "LONG_ONLY" | "SHORT_ONLY";
}

const AGENT_ORDER = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"];

export function StrategyLabView() {
  const [data, setData] = useState<LabState | null>(null);
  const [activeTab, setActiveTab] = useState<"store" | "testing" | "incubator" | "eliminated" | "ledger">("store");
  const [showIntroduceModal, setShowIntroduceModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Live Agent Status & Market Testing Modal State
  const [agentsState, setAgentsState] = useState<Record<string, AgentInfo>>({});
  const [targetMarket, setTargetMarket] = useState<string>("AUTO");
  const [testModal, setTestModal] = useState<TestInLiveMarketModalState | null>(null);
  const [deployingToLive, setDeployingToLive] = useState(false);
  const [deployedSuccess, setDeployedSuccess] = useState<string | null>(null);
  const [agentFilterHorizon, setAgentFilterHorizon] = useState<"ALL" | "LONG_TERM_SWING" | "TACTICAL_INTRADAY">("ALL");

  // New Strategy Form state
  const [newName, setNewName] = useState("");
  const [newArchetype, setNewArchetype] = useState("Breakout");
  const [newDesc, setNewDesc] = useState("");
  const [newHypothesis, setNewHypothesis] = useState("");

  const fetchLabData = async () => {
    try {
      const res = await fetch("/v1/strategies/lab");
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error("Failed to load Strategy Lab data", e);
    }
  };

  const fetchAgentsStatus = async () => {
    try {
      const res = await fetch("/v1/agents/status");
      if (res.ok) {
        const json = await res.json();
        if (json.agents) {
          setAgentsState(json.agents);
        }
        if (json.target_market) {
          setTargetMarket(json.target_market);
        }
      }
    } catch (e) {
      console.error("Failed to load agents status", e);
    }
  };

  useEffect(() => {
    fetchLabData();
    fetchAgentsStatus();
    const interval = setInterval(() => {
      fetchLabData();
      fetchAgentsStatus();
    }, 2000); // 2s live refresh
    return () => clearInterval(interval);
  }, []);

  const bestAgentsList = useMemo(() => {
    const list = AGENT_ORDER.map((name) => agentsState[name]).filter(Boolean);
    if (list.length === 0) return [];
    return [...list].sort((a, b) => {
      if ((b.pnl || 0) !== (a.pnl || 0)) return (b.pnl || 0) - (a.pnl || 0);
      if ((b.win_rate || 0) !== (a.win_rate || 0)) return (b.win_rate || 0) - (a.win_rate || 0);
      return (b.winning_tests || 0) - (a.winning_tests || 0);
    });
  }, [agentsState]);

  const filteredBestAgents = useMemo(() => {
    if (agentFilterHorizon === "ALL") return bestAgentsList;
    return bestAgentsList.filter((ag) => {
      const h = ag.horizon || (ag.name === "Echo" || ag.name === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY");
      return h === agentFilterHorizon;
    });
  }, [bestAgentsList, agentFilterHorizon]);

  const handleOpenTestModal = (params: {
    agentName?: string;
    strategyId?: string;
    strategyName?: string;
    principal?: number;
    market?: string;
    allowedLotSize?: number;
    horizon?: "TACTICAL_INTRADAY" | "LONG_TERM_SWING";
  }) => {
    const chosenAgent = params.agentName || "Delta";
    const ag = agentsState[chosenAgent];
    const g = ag?.guidelines;

    const defaultStratId = params.strategyId || ag?.active_strategy || "S17_OI_VOLUME_MACHINE";
    const defaultStratName = params.strategyName || ag?.active_strategy_name || "Price × OI × Volume State Machine";
    const defaultPrincipal = params.principal ?? g?.max_principal ?? ag?.max_principal ?? 100000;
    const defaultMarket = params.market || g?.target_market || targetMarket || "AUTO";
    const defaultLot = params.allowedLotSize ?? g?.allowed_lot_size ?? (defaultPrincipal >= 200000 ? 2.0 : 1.0);
    const defaultHorizon =
      params.horizon ||
      g?.horizon ||
      ag?.horizon ||
      (chosenAgent === "Echo" || chosenAgent === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY");

    setTestModal({
      open: true,
      agentName: chosenAgent,
      strategyId: defaultStratId,
      strategyName: defaultStratName,
      market: defaultMarket,
      principal: defaultPrincipal,
      allowedLotSize: defaultLot,
      horizon: defaultHorizon,
      directionBias: (g?.direction_bias as any) || "BOTH",
    });
    setDeployedSuccess(null);
  };

  const handleRunInLiveMarket = async () => {
    if (!testModal) return;
    try {
      setDeployingToLive(true);
      const { agentName, strategyId, strategyName, market, principal, allowedLotSize, horizon, directionBias } =
        testModal;

      const payload = {
        mode: "CUSTOM",
        strategy_id: strategyId,
        strategy_name: strategyName,
        max_principal: Number(principal),
        allowed_lot_size: Number(allowedLotSize),
        lots: 0,
        target_market: market,
        direction_bias: directionBias,
        horizon: horizon,
        target_net_pnl_increment: horizon === "LONG_TERM_SWING" ? 50000 : 25000,
        retest_winning_strategies: true,
        condition_gated_entry: true,
        goal: "SUCCESS_MAX_INCREMENT",
      };

      const res = await fetch(`/v1/agents/${agentName}/guidelines`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (market && market !== "AUTO") {
        await fetch("/v1/agents/market", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_market: market }),
        });
      }

      if (res.ok) {
        setDeployedSuccess(
          `🚀 Agent ${agentName} successfully configured & running in Live Market! Market: ${market} · Strategy: ${strategyName} · Principal: ₹${Number(principal).toLocaleString()} · Lot Ceiling: ${allowedLotSize} Lot`,
        );
        fetchAgentsStatus();
        fetchLabData();
      } else {
        const err = await res.json();
        alert(`Deployment failed: ${err.detail || "Error"}`);
      }
    } catch (e) {
      console.error(e);
      alert("Error executing live market deployment");
    } finally {
      setDeployingToLive(false);
    }
  };

  const handleIntroduce = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch("/v1/strategies/lab/introduce", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName,
          archetype: newArchetype,
          description: newDesc || `Candidate strategy ${newName} for gold breakout validation.`,
          hypothesis: newHypothesis || `Testing ${newArchetype} edge on live tick stream.`,
          params: { lookback: 18, z_threshold: 2.1, vol_window: 24, risk_factor: 0.025 },
        }),
      });
      if (res.ok) {
        setActionMsg(
          `✅ Strategy "${newName}" successfully queued into Untested Incubator! Agents will begin live testing.`,
        );
        setNewName("");
        setNewDesc("");
        setNewHypothesis("");
        setShowIntroduceModal(false);
        setActiveTab("incubator");
        fetchLabData();
        setTimeout(() => setActionMsg(null), 6000);
      }
    } catch (err) {
      console.error(err);
      setActionMsg("❌ Failed to introduce strategy.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetest = async (strategyId: string) => {
    try {
      const res = await fetch("/v1/strategies/lab/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_id: strategyId, action: "retest" }),
      });
      if (res.ok) {
        setActionMsg(`🔄 Strategy ${strategyId} re-incubated into Untested queue for fresh agent evaluation.`);
        fetchLabData();
        setTimeout(() => setActionMsg(null), 5000);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const summary = data?.summary;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Banner & Control Deck */}
      <div
        style={{
          background: "linear-gradient(135deg, #f8fafc 0%, #ffffff 50%, #eff6ff 100%)",
          border: "2px solid #bfdbfe",
          borderRadius: 20,
          padding: "24px 28px",
          boxShadow: "0 4px 16px rgba(0, 0, 0, 0.04)",
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
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <h2 style={{ margin: 0, fontSize: 30, fontWeight: 900, color: "#0f172a", letterSpacing: "-0.02em" }}>
                Strategy Lab & Best-in-Store Engine
              </h2>
              <span
                style={{
                  background: "#dcfce7",
                  color: "#15803d",
                  padding: "4px 12px",
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 800,
                  border: "1px solid #86efac",
                }}
              >
                ⚡ AUTONOMOUS AGENT INCUBATOR ACTIVE
              </span>
            </div>
            <p style={{ margin: "6px 0 0", fontSize: 15, color: "#475569", fontWeight: 500 }}>
              Untested strategies are dispatched to autonomous agents trading live market ticks. Positive results
              promote to the Best Store; underperformers are systematically eliminated.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Link
              href="/agents"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "10px 16px",
                background: "#f1f5f9",
                color: "#334155",
                borderRadius: 12,
                fontSize: 13,
                fontWeight: 800,
                textDecoration: "none",
                border: "1px solid #cbd5e1",
              }}
            >
              🤖 View Agents Playground →
            </Link>

            <button
              onClick={() => setShowIntroduceModal((prev) => !prev)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 18px",
                background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                color: "#ffffff",
                borderRadius: 12,
                fontSize: 14,
                fontWeight: 800,
                border: "none",
                cursor: "pointer",
                boxShadow: "0 4px 12px rgba(37, 99, 235, 0.25)",
              }}
            >
              <span>+</span>
              <span>Introduce New Strategy to Lab</span>
            </button>
          </div>
        </div>

        {/* Global Action Message Banner */}
        {actionMsg && (
          <div
            style={{
              marginTop: 16,
              padding: "12px 18px",
              background: "#eff6ff",
              border: "1px solid #93c5fd",
              borderRadius: 12,
              fontSize: 14,
              fontWeight: 700,
              color: "#1e40af",
            }}
          >
            {actionMsg}
          </div>
        )}

        {/* Introduce Strategy Inline Drawer */}
        {showIntroduceModal && (
          <form
            onSubmit={handleIntroduce}
            style={{
              marginTop: 20,
              padding: "20px 24px",
              background: "#ffffff",
              borderRadius: 16,
              border: "2px solid #3b82f6",
              boxShadow: "0 8px 24px rgba(59, 130, 246, 0.12)",
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: 16, fontWeight: 900, color: "#0f172a" }}>
                🧪 Introduce New Quantitative Strategy Candidate
              </div>
              <button
                type="button"
                onClick={() => setShowIntroduceModal(false)}
                style={{ background: "transparent", border: "none", fontSize: 18, cursor: "pointer", color: "#64748b" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 800, color: "#475569", marginBottom: 4 }}>
                  Strategy Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Volatility Spike Mean-Reversion AI"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: "1px solid #cbd5e1",
                    fontSize: 14,
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 800, color: "#475569", marginBottom: 4 }}>
                  Archetype Family
                </label>
                <select
                  value={newArchetype}
                  onChange={(e) => setNewArchetype(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: "1px solid #cbd5e1",
                    fontSize: 14,
                    outline: "none",
                    background: "#ffffff",
                  }}
                >
                  <option value="Breakout">Breakout</option>
                  <option value="Trend Following">Trend Following</option>
                  <option value="Volatility Control">Volatility Control</option>
                  <option value="Mean Reversion">Mean Reversion</option>
                  <option value="Order Flow">Order Flow</option>
                  <option value="Arbitrage">Arbitrage</option>
                  <option value="Microstructure">Microstructure</option>
                  <option value="Global Macro">Global Macro</option>
                  <option value="Liquidity">Liquidity</option>
                  <option value="Options">Options</option>
                  <option value="Meta">Meta</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 800, color: "#475569", marginBottom: 4 }}>
                  Strategy Description
                </label>
                <input
                  type="text"
                  placeholder="e.g. Fast tick compression trigger on live gold feeds"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: "1px solid #cbd5e1",
                    fontSize: 14,
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 800, color: "#475569", marginBottom: 4 }}>
                  Quantitative Test Hypothesis
                </label>
                <input
                  type="text"
                  placeholder="e.g. Exploits rapid post-session volume absorption targeting 1:2 risk/reward"
                  value={newHypothesis}
                  onChange={(e) => setNewHypothesis(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 8,
                    border: "1px solid #cbd5e1",
                    fontSize: 14,
                    outline: "none",
                  }}
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 4 }}>
              <button
                type="button"
                onClick={() => setShowIntroduceModal(false)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 8,
                  border: "1px solid #cbd5e1",
                  background: "#f8fafc",
                  color: "#475569",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                style={{
                  padding: "8px 20px",
                  borderRadius: 8,
                  border: "none",
                  background: "#16a34a",
                  color: "#ffffff",
                  fontWeight: 800,
                  cursor: "pointer",
                  boxShadow: "0 2px 8px rgba(22, 163, 74, 0.25)",
                }}
              >
                {submitting ? "Deploying..." : "🚀 Submit & Deploy to Agent Testing Queue"}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* 4 Interactive Lifecycle KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        {/* Best in Store */}
        <div
          onClick={() => setActiveTab("store")}
          style={{
            background: activeTab === "store" ? "#f0fdf4" : "#ffffff",
            border: `2px solid ${activeTab === "store" ? "#16a34a" : "#e2e8f0"}`,
            borderRadius: 16,
            padding: "16px 20px",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#16a34a", fontWeight: 800, textTransform: "uppercase" }}>
              🏆 Best In Store
            </span>
            <span style={{ fontSize: 18 }}>⭐</span>
          </div>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#15803d", marginTop: 4 }}>
            {summary?.best_in_store ?? 0}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
            Validated survivors with positive net PnL & edge
          </div>
        </div>

        {/* Under Testing */}
        <div
          onClick={() => setActiveTab("testing")}
          style={{
            background: activeTab === "testing" ? "#eff6ff" : "#ffffff",
            border: `2px solid ${activeTab === "testing" ? "#2563eb" : "#e2e8f0"}`,
            borderRadius: 16,
            padding: "16px 20px",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#2563eb", fontWeight: 800, textTransform: "uppercase" }}>
              ⚡ Under Testing
            </span>
            <span style={{ fontSize: 18 }}>🤖</span>
          </div>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#1d4ed8", marginTop: 4 }}>
            {summary?.under_testing ?? 0}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
            Actively traded by autonomous agents on live ticks
          </div>
        </div>

        {/* Untested Incubator */}
        <div
          onClick={() => setActiveTab("incubator")}
          style={{
            background: activeTab === "incubator" ? "#faf5ff" : "#ffffff",
            border: `2px solid ${activeTab === "incubator" ? "#9333ea" : "#e2e8f0"}`,
            borderRadius: 16,
            padding: "16px 20px",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#9333ea", fontWeight: 800, textTransform: "uppercase" }}>
              🆕 Untested Incubator
            </span>
            <span style={{ fontSize: 18 }}>🌱</span>
          </div>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#7e22ce", marginTop: 4 }}>
            {summary?.untested_incubator ?? 0}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>Awaiting agent pickup & live market trial</div>
        </div>

        {/* Eliminated Archive */}
        <div
          onClick={() => setActiveTab("eliminated")}
          style={{
            background: activeTab === "eliminated" ? "#fef2f2" : "#ffffff",
            border: `2px solid ${activeTab === "eliminated" ? "#dc2626" : "#e2e8f0"}`,
            borderRadius: 16,
            padding: "16px 20px",
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#dc2626", fontWeight: 800, textTransform: "uppercase" }}>
              ❌ Eliminated / Pruned
            </span>
            <span style={{ fontSize: 18 }}>🛡️</span>
          </div>
          <div style={{ fontSize: 32, fontWeight: 900, color: "#b91c1c", marginTop: 4 }}>
            {summary?.eliminated_archive ?? 0}
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>Pruned from store on negative expectancy</div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TOP PERFORMING AUTONOMOUS AGENTS SHOWCASE                                 */}
      {/* ========================================================================= */}
      <div
        style={{
          background: "linear-gradient(135deg, #090e1a 0%, #0f172a 40%, #1e1b4b 100%)",
          borderRadius: 20,
          padding: "22px 26px",
          color: "#ffffff",
          boxShadow: "0 10px 30px rgba(15, 23, 42, 0.4)",
          border: "2px solid #3b82f6",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                fontSize: 26,
                background: "rgba(59, 130, 246, 0.2)",
                padding: "8px 12px",
                borderRadius: 14,
                border: "1px solid #3b82f6",
              }}
            >
              🤖
            </span>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0, fontSize: 19, fontWeight: 900, color: "#ffffff", letterSpacing: "-0.01em" }}>
                  Top Performing Autonomous Agents (Live Edge Ranking)
                </h3>
                <span
                  style={{
                    background: "#059669",
                    color: "#ecfdf5",
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontSize: 10,
                    fontWeight: 900,
                  }}
                >
                  {bestAgentsList.length} AGENTS ACTIVE
                </span>
              </div>
              <p style={{ margin: "3px 0 0 0", color: "#94a3b8", fontSize: 12 }}>
                Autonomous agents actively proving strategies against real-time live market ticks. Click{" "}
                <b>"Test in Live Market"</b> on any agent to customize markets & principal.
              </p>
            </div>
          </div>

          {/* Horizon Filter Tabs for Agents */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[
              { id: "ALL", label: "All Agents" },
              { id: "LONG_TERM_SWING", label: "⏳ Long-Term (Echo & Juliet)" },
              { id: "TACTICAL_INTRADAY", label: "⚡ Tactical Intraday (8)" },
            ].map((tab) => {
              const isActive = agentFilterHorizon === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setAgentFilterHorizon(tab.id as any)}
                  style={{
                    background: isActive ? "#2563eb" : "rgba(30, 41, 59, 0.7)",
                    color: isActive ? "#ffffff" : "#94a3b8",
                    border: isActive ? "1px solid #60a5fa" : "1px solid #334155",
                    padding: "5px 12px",
                    borderRadius: 8,
                    fontSize: 11,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Agent Cards Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
          {filteredBestAgents.map((ag) => {
            const _isTwoLac = (ag.max_principal || 100000) >= 200000;
            const isSwing = ag.horizon === "LONG_TERM_SWING";
            const isMatched = ag.condition_status?.matched ?? false;

            return (
              <div
                key={ag.name}
                style={{
                  background: "rgba(15, 23, 42, 0.75)",
                  border: isMatched ? "1px solid #22c55e" : "1px solid #334155",
                  borderRadius: 14,
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                  boxShadow: isMatched ? "0 4px 14px rgba(34, 197, 94, 0.15)" : "none",
                }}
              >
                {/* Card Top */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 24,
                        background: "#1e293b",
                        padding: "6px",
                        borderRadius: 10,
                        border: "1px solid #475569",
                      }}
                    >
                      {ag.avatar || "🤖"}
                    </span>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 15, fontWeight: 900, color: "#ffffff" }}>Agent {ag.name}</span>
                        {ag.name === "Delta" && <span title="#1 Ranked Strategy Specialist">👑</span>}
                        <span
                          style={{
                            fontSize: 9,
                            fontWeight: 900,
                            padding: "1px 6px",
                            borderRadius: 4,
                            background: isSwing ? "#4c1d95" : "#0c4a6e",
                            color: isSwing ? "#e9d5ff" : "#bae6fd",
                            border: `1px solid ${isSwing ? "#a855f7" : "#0284c7"}`,
                          }}
                        >
                          {isSwing ? "⏳ SWING" : "⚡ INTRADAY"}
                        </span>
                        <span style={{ fontSize: 10, color: "#38bdf8", fontWeight: 800 }}>
                          ₹{((ag.max_principal || 100000) / 100000).toFixed(1)}L
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{ag.specialization}</div>
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 700 }}>NET P&L</div>
                    <div
                      style={{
                        fontSize: 15,
                        fontWeight: 900,
                        fontFamily: "monospace",
                        color: (ag.pnl || 0) >= 0 ? "#4ade80" : "#f87171",
                      }}
                    >
                      {(ag.pnl || 0) >= 0 ? "+" : ""}₹
                      {(ag.pnl || 0).toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                    </div>
                  </div>
                </div>

                {/* Active Strategy & Condition Match */}
                <div
                  style={{
                    background: "rgba(30, 41, 59, 0.6)",
                    padding: "8px 10px",
                    borderRadius: 8,
                    border: "1px solid #334155",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}
                >
                  <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 800, textTransform: "uppercase" }}>
                    TESTING STRATEGY
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: "#38bdf8",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {ag.active_strategy}: {ag.active_strategy_name}
                  </div>

                  {ag.condition_status && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginTop: 2,
                        fontSize: 10,
                      }}
                    >
                      <span
                        style={{
                          color: isMatched ? "#4ade80" : "#fbbf24",
                          fontWeight: 800,
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <span>{isMatched ? "🟢" : "🟡"}</span>
                        <span>{isMatched ? "Condition Matched" : "Observing"}</span>
                      </span>
                      <span style={{ color: "#94a3b8" }}>{ag.condition_status.condition_label}</span>
                    </div>
                  )}
                </div>

                {/* Mini Stats Bar */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: 6,
                    textAlign: "center",
                    fontSize: 11,
                  }}
                >
                  <div style={{ background: "#1e293b", padding: "6px", borderRadius: 6 }}>
                    <div style={{ fontSize: 9, color: "#94a3b8" }}>WIN RATE</div>
                    <div style={{ fontWeight: 900, color: (ag.win_rate || 0) >= 50 ? "#4ade80" : "#f87171" }}>
                      {ag.win_rate || 0}%
                    </div>
                  </div>
                  <div style={{ background: "#1e293b", padding: "6px", borderRadius: 6 }}>
                    <div style={{ fontSize: 9, color: "#94a3b8" }}>TESTS</div>
                    <div style={{ fontWeight: 900, color: "#e2e8f0" }}>{ag.total_tests || 0}</div>
                  </div>
                  <div style={{ background: "#1e293b", padding: "6px", borderRadius: 6 }}>
                    <div style={{ fontSize: 9, color: "#94a3b8" }}>EDGE</div>
                    <div style={{ fontWeight: 800, fontSize: 9, color: "#a5b4fc" }}>
                      {ag.strategy_edge_status || "ACTIVE"}
                    </div>
                  </div>
                </div>

                {/* ACTION BUTTON: TEST IN LIVE MARKET */}
                <button
                  type="button"
                  onClick={() =>
                    handleOpenTestModal({
                      agentName: ag.name,
                      strategyId: ag.active_strategy,
                      strategyName: ag.active_strategy_name,
                      principal: ag.max_principal,
                      horizon: ag.horizon,
                    })
                  }
                  style={{
                    padding: "10px",
                    borderRadius: 10,
                    border: "1px solid #34d399",
                    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                    color: "#ffffff",
                    fontSize: 12,
                    fontWeight: 900,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>⚡</span>
                  <span>Test in Live Market</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Navigation Filter Tabs */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "2px solid #e2e8f0",
          paddingBottom: 10,
        }}
      >
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => setActiveTab("store")}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              border: "none",
              background: activeTab === "store" ? "#16a34a" : "#f1f5f9",
              color: activeTab === "store" ? "#ffffff" : "#475569",
            }}
          >
            🏆 Best in Store ({summary?.best_in_store ?? 0})
          </button>

          <button
            onClick={() => setActiveTab("testing")}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              border: "none",
              background: activeTab === "testing" ? "#2563eb" : "#f1f5f9",
              color: activeTab === "testing" ? "#ffffff" : "#475569",
            }}
          >
            ⚡ Under Agent Testing ({summary?.under_testing ?? 0})
          </button>

          <button
            onClick={() => setActiveTab("incubator")}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              border: "none",
              background: activeTab === "incubator" ? "#9333ea" : "#f1f5f9",
              color: activeTab === "incubator" ? "#ffffff" : "#475569",
            }}
          >
            🆕 Untested Incubator ({summary?.untested_incubator ?? 0})
          </button>

          <button
            onClick={() => setActiveTab("eliminated")}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              border: "none",
              background: activeTab === "eliminated" ? "#dc2626" : "#f1f5f9",
              color: activeTab === "eliminated" ? "#ffffff" : "#475569",
            }}
          >
            ❌ Eliminated Archive ({summary?.eliminated_archive ?? 0})
          </button>

          <button
            onClick={() => setActiveTab("ledger")}
            style={{
              padding: "8px 16px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 800,
              cursor: "pointer",
              border: "none",
              background: activeTab === "ledger" ? "#0f172a" : "#f1f5f9",
              color: activeTab === "ledger" ? "#ffffff" : "#475569",
            }}
          >
            📜 Live Strategy Ledger ({data?.ledger.length ?? 0} events)
          </button>
        </div>

        <div style={{ fontSize: 13, color: "#64748b", fontWeight: 600 }}>Auto-updated on every live market tick</div>
      </div>

      {/* TAB 1: BEST IN STORE (SURVIVORS) */}
      {activeTab === "store" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#f0fdf4",
              padding: "12px 18px",
              borderRadius: 12,
              border: "1px solid #bbf7d0",
              fontSize: 13,
              color: "#166534",
              fontWeight: 700,
            }}
          >
            🌟 THE STORE CURATION: Only strategies with verified statistical edge, win rate ≥ 50%, profit factor ≥ 1.05,
            and positive net PnL are admitted into the store.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
            {data?.best_store.map((s) => (
              <div
                key={s.id}
                style={{
                  background: "#ffffff",
                  borderRadius: 16,
                  padding: "20px",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.03)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span
                        style={{
                          background: "#fef3c7",
                          color: "#92400e",
                          fontWeight: 900,
                          fontSize: 12,
                          padding: "2px 8px",
                          borderRadius: 6,
                          border: "1px solid #fde68a",
                        }}
                      >
                        #{s.store_rank} STORE RANK
                      </span>
                      {s.leaderboard_rank && (
                        <span
                          style={{
                            background: "#eff6ff",
                            color: "#1d4ed8",
                            fontWeight: 800,
                            fontSize: 12,
                            padding: "2px 8px",
                            borderRadius: 6,
                            border: "1px solid #bfdbfe",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          🏆 Leaderboard #{s.leaderboard_rank} · Score:{" "}
                          {s.leaderboard_score ? s.leaderboard_score.toFixed(1) : "92.0"} [
                          {s.leaderboard_grade || "S-TIER"}]
                        </span>
                      )}
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{s.id}</span>
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 900, color: "#0f172a", marginTop: 4 }}>{s.name}</div>
                  </div>
                  <span
                    style={{
                      background: "#dcfce7",
                      color: "#15803d",
                      padding: "4px 10px",
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 800,
                    }}
                  >
                    {s.archetype}
                  </span>
                </div>

                <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.4 }}>{s.description}</div>

                {/* Performance Metrics Bar */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(4, 1fr)",
                    gap: 8,
                    background: "#f8fafc",
                    padding: "10px",
                    borderRadius: 10,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>NET P&L</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#16a34a" }}>
                      +₹{s.net_pnl.toLocaleString("en-IN", { maximumFractionDigits: 1 })}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>WIN RATE</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#2563eb" }}>{s.win_rate}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>PROFIT FACTOR</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#0284c7" }}>{s.profit_factor}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>LIVE TRADES</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#0f172a" }}>{s.total_trades}</div>
                  </div>
                </div>

                {/* Tuned Hyperparameters */}
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: "monospace",
                    color: "#64748b",
                    background: "#f1f5f9",
                    padding: "6px 10px",
                    borderRadius: 6,
                  }}
                >
                  Active Parameters:{" "}
                  {Object.entries(s.parameters || {})
                    .map(([k, v]) => `${k}:${v}`)
                    .join(", ")}
                </div>

                {/* Test in Live Market Button */}
                <button
                  type="button"
                  onClick={() =>
                    handleOpenTestModal({
                      strategyId: s.id,
                      strategyName: s.name,
                      agentName: s.assigned_agent?.replace("Agent ", "") || "Delta",
                    })
                  }
                  style={{
                    marginTop: 4,
                    padding: "10px 14px",
                    borderRadius: 10,
                    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                    color: "#ffffff",
                    border: "1px solid #34d399",
                    fontSize: 13,
                    fontWeight: 900,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    boxShadow: "0 4px 12px rgba(16, 185, 129, 0.25)",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>⚡</span>
                  <span>Test in Live Market</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: UNDER AGENT TESTING */}
      {activeTab === "testing" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#eff6ff",
              padding: "12px 18px",
              borderRadius: 12,
              border: "1px solid #bfdbfe",
              fontSize: 13,
              color: "#1e40af",
              fontWeight: 700,
            }}
          >
            ⚡ ACTIVE AGENT VALIDATION: Autonomous agents trade these strategies against genuine live streaming ticks to
            establish empirical statistical significance.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
            {data?.under_testing.map((s) => (
              <div
                key={s.id}
                style={{
                  background: "#ffffff",
                  borderRadius: 16,
                  padding: "20px",
                  border: "2px solid #93c5fd",
                  boxShadow: "0 4px 12px rgba(59, 130, 246, 0.06)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span
                        style={{
                          background: "#dbeafe",
                          color: "#1d4ed8",
                          fontWeight: 900,
                          fontSize: 12,
                          padding: "2px 8px",
                          borderRadius: 6,
                        }}
                      >
                        ⚡ UNDER TEST
                      </span>
                      {s.leaderboard_rank && (
                        <span
                          style={{
                            background: "#eff6ff",
                            color: "#1d4ed8",
                            fontWeight: 800,
                            fontSize: 12,
                            padding: "2px 8px",
                            borderRadius: 6,
                            border: "1px solid #bfdbfe",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          🏆 Leaderboard #{s.leaderboard_rank} · Score:{" "}
                          {s.leaderboard_score ? s.leaderboard_score.toFixed(1) : "88.0"} [
                          {s.leaderboard_grade || "A-TIER"}]
                        </span>
                      )}
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#64748b" }}>{s.id}</span>
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 900, color: "#0f172a", marginTop: 4 }}>{s.name}</div>
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: "#2563eb",
                      background: "#f0fdf4",
                      padding: "4px 10px",
                      borderRadius: 8,
                      border: "1px solid #bbf7d0",
                    }}
                  >
                    {s.assigned_agent || "Assigned to Agent"}
                  </span>
                </div>

                <div style={{ fontSize: 12, color: "#475569" }}>{s.description}</div>

                {/* Hypothesis Box */}
                <div
                  style={{
                    background: "#f8fafc",
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: "1px solid #e2e8f0",
                    fontSize: 12,
                    color: "#0f766e",
                    fontWeight: 600,
                  }}
                >
                  💡 Hypothesis: {s.hypothesis}
                </div>

                {/* Live Stats */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                  <div style={{ background: "#f8fafc", padding: "8px", borderRadius: 8 }}>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>NET P&L</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: s.net_pnl >= 0 ? "#16a34a" : "#dc2626" }}>
                      {s.net_pnl >= 0 ? "+" : ""}₹{s.net_pnl.toFixed(1)}
                    </div>
                  </div>
                  <div style={{ background: "#f8fafc", padding: "8px", borderRadius: 8 }}>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>WIN RATE</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#2563eb" }}>{s.win_rate}%</div>
                  </div>
                  <div style={{ background: "#f8fafc", padding: "8px", borderRadius: 8 }}>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>PROFIT FACTOR</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#0284c7" }}>{s.profit_factor}</div>
                  </div>
                  <div style={{ background: "#f8fafc", padding: "8px", borderRadius: 8 }}>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>TEST TRADES</div>
                    <div style={{ fontSize: 15, fontWeight: 900, color: "#0f172a" }}>{s.total_trades}</div>
                  </div>
                </div>

                {/* Progress to Promotion Gate */}
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "#64748b",
                      marginBottom: 4,
                    }}
                  >
                    <span>Promotion Gate Sample Progress</span>
                    <span>{Math.min(100, Math.round((s.total_trades / 20) * 100))}%</span>
                  </div>
                  <div style={{ height: 6, background: "#e2e8f0", borderRadius: 999, overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${Math.min(100, (s.total_trades / 20) * 100)}%`,
                        height: "100%",
                        background: "#2563eb",
                        transition: "width 0.4s",
                      }}
                    />
                  </div>
                </div>

                {/* Test in Live Market Button */}
                <button
                  type="button"
                  onClick={() =>
                    handleOpenTestModal({
                      strategyId: s.id,
                      strategyName: s.name,
                      agentName: s.assigned_agent?.replace("Agent ", "") || "Alpha",
                    })
                  }
                  style={{
                    marginTop: 4,
                    padding: "10px 14px",
                    borderRadius: 10,
                    background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                    color: "#ffffff",
                    border: "1px solid #60a5fa",
                    fontSize: 13,
                    fontWeight: 900,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    boxShadow: "0 4px 12px rgba(37, 99, 235, 0.25)",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>⚡</span>
                  <span>Test in Live Market</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: UNTESTED INCUBATOR */}
      {activeTab === "incubator" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#faf5ff",
              padding: "12px 18px",
              borderRadius: 12,
              border: "1px solid #e9d5ff",
              fontSize: 13,
              color: "#6b21a8",
              fontWeight: 700,
            }}
          >
            🌱 UNTESTED INCUBATOR: Newly introduced strategies wait here. Available autonomous agents automatically
            prioritize and claim these candidates for live execution testing.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
            {data?.untested_incubator.map((s) => (
              <div
                key={s.id}
                style={{
                  background: "#ffffff",
                  borderRadius: 16,
                  padding: "20px",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 12px rgba(0, 0, 0, 0.03)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: "#9333ea",
                        background: "#f3e8ff",
                        padding: "2px 8px",
                        borderRadius: 6,
                      }}
                    >
                      🆕 QUEUED IN INCUBATOR
                    </span>
                    <div style={{ fontSize: 18, fontWeight: 900, color: "#0f172a", marginTop: 6 }}>{s.name}</div>
                  </div>
                  <span
                    style={{
                      background: "#f1f5f9",
                      color: "#475569",
                      padding: "4px 8px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {s.archetype}
                  </span>
                </div>

                <div style={{ fontSize: 12, color: "#475569" }}>{s.description}</div>

                <div
                  style={{
                    background: "#fdf4ff",
                    padding: "10px",
                    borderRadius: 8,
                    border: "1px solid #f5d0fe",
                    fontSize: 12,
                    color: "#86198f",
                  }}
                >
                  🔬 Initial Hypothesis: {s.hypothesis}
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderTop: "1px solid #f1f5f9",
                    paddingTop: 10,
                  }}
                >
                  <span style={{ fontSize: 11, color: "#64748b" }}>Queued for agent claim</span>
                  <button
                    type="button"
                    onClick={() =>
                      handleOpenTestModal({
                        strategyId: s.id,
                        strategyName: s.name,
                      })
                    }
                    style={{
                      padding: "6px 12px",
                      borderRadius: 8,
                      background: "linear-gradient(135deg, #9333ea 0%, #7e22ce 100%)",
                      color: "#ffffff",
                      border: "1px solid #c084fc",
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span>⚡</span>
                    <span>Test in Live Market</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: ELIMINATED ARCHIVE */}
      {activeTab === "eliminated" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#fef2f2",
              padding: "12px 18px",
              borderRadius: 12,
              border: "1px solid #fecaca",
              fontSize: 13,
              color: "#991b1b",
              fontWeight: 700,
            }}
          >
            🛡️ ZERO COMPROMISE RISK ELIMINATION: Strategies that fail live market execution (negative PnL, degrading win
            rate, or slippage stress) are immediately pruned from the store.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
            {data?.eliminated_archive.map((s) => (
              <div
                key={s.id}
                style={{
                  background: "#ffffff",
                  borderRadius: 16,
                  padding: "20px",
                  border: "1px solid #fecaca",
                  boxShadow: "0 4px 12px rgba(220, 38, 38, 0.04)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 800,
                        color: "#dc2626",
                        background: "#fee2e2",
                        padding: "2px 8px",
                        borderRadius: 6,
                      }}
                    >
                      ❌ PRUNED FROM STORE
                    </span>
                    <div style={{ fontSize: 18, fontWeight: 900, color: "#0f172a", marginTop: 6 }}>{s.name}</div>
                  </div>
                  <span
                    style={{
                      background: "#f1f5f9",
                      color: "#64748b",
                      padding: "4px 8px",
                      borderRadius: 6,
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {s.archetype}
                  </span>
                </div>

                {/* Rejection Diagnostics */}
                <div
                  style={{
                    background: "#fef2f2",
                    padding: "10px",
                    borderRadius: 8,
                    border: "1px solid #fca5a5",
                    fontSize: 12,
                    color: "#991b1b",
                    fontWeight: 600,
                  }}
                >
                  ⚠️ {s.rejection_reason || "Eliminated due to negative expectancy under live tick spreads."}
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 8,
                    background: "#f8fafc",
                    padding: "8px",
                    borderRadius: 8,
                  }}
                >
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>NET LOSS</div>
                    <div style={{ fontSize: 14, fontWeight: 900, color: "#dc2626" }}>₹{s.net_pnl.toFixed(1)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>WIN RATE</div>
                    <div style={{ fontSize: 14, fontWeight: 900, color: "#475569" }}>{s.win_rate}%</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>TRADES RUN</div>
                    <div style={{ fontSize: 14, fontWeight: 900, color: "#475569" }}>{s.total_trades}</div>
                  </div>
                </div>

                <button
                  onClick={() => handleRetest(s.id)}
                  style={{
                    width: "100%",
                    padding: "8px 14px",
                    borderRadius: 8,
                    border: "1px solid #cbd5e1",
                    background: "#f8fafc",
                    color: "#334155",
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 6,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#e2e8f0")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "#f8fafc")}
                >
                  <span>🔄</span>
                  <span>Re-test Strategy in Incubator</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: LIVE STRATEGY LEDGER */}
      {activeTab === "ledger" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              background: "#f8fafc",
              padding: "12px 18px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              fontSize: 13,
              color: "#334155",
              fontWeight: 700,
            }}
          >
            📜 REAL-TIME STRATEGY LEDGER: Complete chronological record of every candidate introduced, test trade
            settled, strategy promoted to Best Store, and failure elimination.
          </div>

          <div
            style={{
              maxHeight: 600,
              overflowY: "auto",
              border: "1px solid #e2e8f0",
              borderRadius: 16,
              background: "#ffffff",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
              <thead style={{ position: "sticky", top: 0, background: "#f1f5f9", zIndex: 2 }}>
                <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#475569" }}>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Time</th>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Event</th>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Strategy</th>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Agent</th>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Outcome / PnL</th>
                  <th style={{ padding: "12px 14px", fontWeight: 800 }}>Details & Audit Record</th>
                </tr>
              </thead>
              <tbody>
                {data?.ledger.map((ev, idx) => {
                  const isPromotion = ev.event_type === "PROMOTED_TO_STORE";
                  const isElimination = ev.event_type === "ELIMINATED_PRUNED";
                  const isNew = ev.event_type === "NEW_CANDIDATE_INTRODUCED";
                  const isClaimed = ev.event_type === "TESTING_CLAIMED";

                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: "1px solid #f1f5f9",
                        background: isPromotion ? "#f0fdf4" : isElimination ? "#fef2f2" : "transparent",
                      }}
                    >
                      <td
                        style={{
                          padding: "12px 14px",
                          color: "#64748b",
                          fontFamily: "monospace",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </td>
                      <td style={{ padding: "12px 14px", whiteSpace: "nowrap" }}>
                        <span
                          style={{
                            padding: "4px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 800,
                            background: isPromotion
                              ? "#dcfce7"
                              : isElimination
                                ? "#fee2e2"
                                : isNew
                                  ? "#f3e8ff"
                                  : isClaimed
                                    ? "#dbeafe"
                                    : "#f1f5f9",
                            color: isPromotion
                              ? "#15803d"
                              : isElimination
                                ? "#b91c1c"
                                : isNew
                                  ? "#7e22ce"
                                  : isClaimed
                                    ? "#1d4ed8"
                                    : "#475569",
                          }}
                        >
                          {ev.event_type}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", fontWeight: 700, color: "#0f172a" }}>
                        <div>{ev.strategy_name}</div>
                        <div style={{ fontSize: 10, color: "#64748b", fontFamily: "monospace" }}>{ev.strategy_id}</div>
                      </td>
                      <td style={{ padding: "12px 14px", color: "#334155", fontWeight: 600 }}>
                        {ev.agent || "System"}
                      </td>
                      <td
                        style={{ padding: "12px 14px", fontWeight: 800, fontFamily: "monospace", whiteSpace: "nowrap" }}
                      >
                        {ev.pnl_change !== undefined ? (
                          <span style={{ color: ev.pnl_change >= 0 ? "#16a34a" : "#dc2626" }}>
                            {ev.pnl_change >= 0 ? "+" : ""}
                            {ev.currency_symbol || "₹"}
                            {ev.pnl_change.toFixed(2)}
                          </span>
                        ) : ev.net_pnl !== undefined ? (
                          <span style={{ color: ev.net_pnl >= 0 ? "#16a34a" : "#dc2626" }}>
                            {ev.net_pnl >= 0 ? "+" : ""}₹{ev.net_pnl.toFixed(1)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td style={{ padding: "12px 14px", color: "#475569", fontSize: 12 }}>{ev.details}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {/* ========================================================================= */}
      {/* LIVE MARKET TEST CONFIGURATION MODAL                                      */}
      {/* ========================================================================= */}
      {testModal && testModal.open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.8)",
            backdropFilter: "blur(8px)",
            zIndex: 99999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "linear-gradient(135deg, #090e1a 0%, #0f172a 40%, #1e1b4b 100%)",
              color: "#ffffff",
              borderRadius: 22,
              padding: "26px 30px",
              maxWidth: 720,
              width: "100%",
              border: "2px solid #3b82f6",
              boxShadow: "0 25px 60px -15px rgba(0, 0, 0, 0.7)",
              display: "flex",
              flexDirection: "column",
              gap: 18,
              maxHeight: "92vh",
              overflowY: "auto",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                borderBottom: "1px solid #334155",
                paddingBottom: 14,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span
                  style={{
                    fontSize: 32,
                    background: "#1e293b",
                    padding: "8px",
                    borderRadius: 14,
                    border: "1px solid #3b82f6",
                  }}
                >
                  🚀
                </span>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <h3 style={{ margin: 0, fontSize: 20, fontWeight: 900, color: "#ffffff" }}>
                      Test in Live Market: Agent {testModal.agentName}
                    </h3>
                    <span
                      style={{
                        background: "#2563eb",
                        color: "#dbeafe",
                        padding: "2px 8px",
                        borderRadius: 6,
                        fontSize: 11,
                        fontWeight: 800,
                      }}
                    >
                      {testModal.strategyId}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: "#93c5fd", marginTop: 2 }}>
                    Deploy {testModal.strategyName} with custom markets, principal & lot limits.
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setTestModal(null)}
                style={{
                  background: "#1e293b",
                  border: "1px solid #475569",
                  color: "#cbd5e1",
                  borderRadius: 8,
                  width: 32,
                  height: 32,
                  cursor: "pointer",
                  fontSize: 16,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                ✕
              </button>
            </div>

            {/* Success Notification Banner */}
            {deployedSuccess ? (
              <div
                style={{
                  background: "rgba(16, 185, 129, 0.15)",
                  border: "2px solid #10b981",
                  borderRadius: 14,
                  padding: "20px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 28 }}>🎉</div>
                <div style={{ fontSize: 15, fontWeight: 900, color: "#4ade80" }}>{deployedSuccess}</div>
                <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap", marginTop: 6 }}>
                  <button
                    type="button"
                    onClick={() => setTestModal(null)}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 10,
                      background: "#1e293b",
                      color: "#cbd5e1",
                      border: "1px solid #475569",
                      fontSize: 13,
                      fontWeight: 800,
                      cursor: "pointer",
                    }}
                  >
                    ✓ Stay in Strategy Lab
                  </button>
                  <Link
                    href="/agents"
                    style={{
                      padding: "10px 20px",
                      borderRadius: 10,
                      background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                      color: "#ffffff",
                      border: "1px solid #60a5fa",
                      fontSize: 13,
                      fontWeight: 900,
                      textDecoration: "none",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      boxShadow: "0 4px 14px rgba(37, 99, 235, 0.4)",
                    }}
                  >
                    <span>🤖 Jump to Live Agents Playground →</span>
                  </Link>
                </div>
              </div>
            ) : (
              /* Configuration Form */
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {/* 1. Market Selection */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <label style={{ fontSize: 12, fontWeight: 800, color: "#93c5fd", textTransform: "uppercase" }}>
                    1. Target Market Execution Contract
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 8 }}>
                    {[
                      { id: "AUTO", label: "⚡ AUTO", sub: "Session Detection" },
                      { id: "MCX_GOLDM", label: "🪙 MCX Gold Mini", sub: "100g Multiplier" },
                      { id: "MCX_GOLD", label: "🥇 MCX Gold", sub: "1,000g Standard" },
                      { id: "GLOBAL_XAU", label: "🌍 Global Spot", sub: "24/7 USD Feed" },
                    ].map((mkt) => {
                      const isSel = testModal.market === mkt.id;
                      return (
                        <button
                          key={mkt.id}
                          type="button"
                          onClick={() => setTestModal((prev) => (prev ? { ...prev, market: mkt.id } : null))}
                          style={{
                            background: isSel ? "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)" : "#1e293b",
                            border: isSel ? "2px solid #60a5fa" : "1px solid #334155",
                            borderRadius: 10,
                            padding: "10px",
                            color: "#ffffff",
                            cursor: "pointer",
                            textAlign: "left",
                            boxShadow: isSel ? "0 4px 12px rgba(37, 99, 235, 0.3)" : "none",
                          }}
                        >
                          <div style={{ fontWeight: 900, fontSize: 13 }}>{mkt.label}</div>
                          <div style={{ fontSize: 10, color: isSel ? "#e0f2fe" : "#94a3b8", marginTop: 2 }}>
                            {mkt.sub}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 2. Principal Allocation */}
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label style={{ fontSize: 12, fontWeight: 800, color: "#93c5fd", textTransform: "uppercase" }}>
                      2. Max Principal Allocation (₹ INR)
                    </label>
                    <span style={{ fontSize: 13, fontWeight: 900, fontFamily: "monospace", color: "#4ade80" }}>
                      ₹{Number(testModal.principal).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[50000, 100000, 150000, 200000].map((pVal) => (
                      <button
                        key={pVal}
                        type="button"
                        onClick={() => setTestModal((prev) => (prev ? { ...prev, principal: pVal } : null))}
                        style={{
                          flex: 1,
                          background: testModal.principal === pVal ? "#15803d" : "#1e293b",
                          color: testModal.principal === pVal ? "#ffffff" : "#94a3b8",
                          border: `1px solid ${testModal.principal === pVal ? "#86efac" : "#334155"}`,
                          borderRadius: 8,
                          padding: "6px",
                          fontSize: 12,
                          fontWeight: 800,
                          cursor: "pointer",
                        }}
                      >
                        ₹{pVal >= 100000 ? `${pVal / 100000}L` : `${pVal / 1000}K`}
                      </button>
                    ))}
                  </div>
                  <input
                    type="number"
                    step="5000"
                    min="10000"
                    value={testModal.principal}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value) || 100000;
                      setTestModal((prev) => (prev ? { ...prev, principal: val } : null));
                    }}
                    style={{
                      background: "#0f172a",
                      color: "#4ade80",
                      border: "2px solid #3b82f6",
                      borderRadius: 8,
                      padding: "8px 12px",
                      fontSize: 14,
                      fontWeight: 900,
                      fontFamily: "monospace",
                      outline: "none",
                    }}
                  />
                </div>

                {/* 3. Allowed Lot Size Ceiling & Horizon */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  {/* Allowed Lot Size */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <label style={{ fontSize: 11, fontWeight: 800, color: "#93c5fd", textTransform: "uppercase" }}>
                      3. Allowed Lot Size Ceiling
                    </label>
                    <div style={{ display: "flex", gap: 4 }}>
                      {[0.1, 0.2, 0.5, 1.0, 2.0].map((lVal) => (
                        <button
                          key={lVal}
                          type="button"
                          onClick={() => setTestModal((prev) => (prev ? { ...prev, allowedLotSize: lVal } : null))}
                          style={{
                            flex: 1,
                            background: testModal.allowedLotSize === lVal ? "#0284c7" : "#1e293b",
                            color: testModal.allowedLotSize === lVal ? "#ffffff" : "#94a3b8",
                            border: `1px solid ${testModal.allowedLotSize === lVal ? "#38bdf8" : "#334155"}`,
                            borderRadius: 6,
                            padding: "4px 2px",
                            fontSize: 11,
                            fontWeight: 800,
                            cursor: "pointer",
                          }}
                        >
                          {lVal}L
                        </button>
                      ))}
                    </div>
                    <input
                      type="number"
                      step="0.05"
                      min="0.05"
                      max="10.0"
                      value={testModal.allowedLotSize}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0.1;
                        setTestModal((prev) => (prev ? { ...prev, allowedLotSize: val } : null));
                      }}
                      style={{
                        background: "#0f172a",
                        color: "#38bdf8",
                        border: "2px solid #3b82f6",
                        borderRadius: 8,
                        padding: "8px 10px",
                        fontSize: 13,
                        fontWeight: 900,
                        fontFamily: "monospace",
                        outline: "none",
                      }}
                    />
                  </div>

                  {/* Execution Horizon */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <label style={{ fontSize: 11, fontWeight: 800, color: "#93c5fd", textTransform: "uppercase" }}>
                      4. Execution Horizon
                    </label>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        onClick={() =>
                          setTestModal((prev) => (prev ? { ...prev, horizon: "TACTICAL_INTRADAY" } : null))
                        }
                        style={{
                          flex: 1,
                          padding: "8px",
                          borderRadius: 8,
                          fontSize: 11,
                          fontWeight: 800,
                          cursor: "pointer",
                          background: testModal.horizon === "TACTICAL_INTRADAY" ? "#0284c7" : "#1e293b",
                          color: testModal.horizon === "TACTICAL_INTRADAY" ? "#ffffff" : "#94a3b8",
                          border: testModal.horizon === "TACTICAL_INTRADAY" ? "2px solid #38bdf8" : "1px solid #334155",
                        }}
                      >
                        ⚡ Tactical (15c)
                      </button>
                      <button
                        type="button"
                        onClick={() => setTestModal((prev) => (prev ? { ...prev, horizon: "LONG_TERM_SWING" } : null))}
                        style={{
                          flex: 1,
                          padding: "8px",
                          borderRadius: 8,
                          fontSize: 11,
                          fontWeight: 800,
                          cursor: "pointer",
                          background: testModal.horizon === "LONG_TERM_SWING" ? "#7e22ce" : "#1e293b",
                          color: testModal.horizon === "LONG_TERM_SWING" ? "#ffffff" : "#94a3b8",
                          border: testModal.horizon === "LONG_TERM_SWING" ? "2px solid #d8b4fe" : "1px solid #334155",
                        }}
                      >
                        ⏳ Swing (60c)
                      </button>
                    </div>
                    <div style={{ fontSize: 10, color: "#94a3b8" }}>
                      {testModal.horizon === "LONG_TERM_SWING"
                        ? "60 hold cycles, asymmetric target"
                        : "15 hold cycles, fast velocity"}
                    </div>
                  </div>
                </div>

                {/* 4. Choose Agent */}
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <label style={{ fontSize: 11, fontWeight: 800, color: "#93c5fd", textTransform: "uppercase" }}>
                    5. Deploying Agent
                  </label>
                  <select
                    value={testModal.agentName}
                    onChange={(e) => {
                      const newName = e.target.value;
                      const ag = agentsState[newName];
                      setTestModal((prev) =>
                        prev
                          ? {
                              ...prev,
                              agentName: newName,
                              principal: ag?.max_principal ?? prev.principal,
                              allowedLotSize: ag?.guidelines?.allowed_lot_size ?? prev.allowedLotSize,
                              horizon:
                                newName === "Echo" || newName === "Juliet" ? "LONG_TERM_SWING" : "TACTICAL_INTRADAY",
                            }
                          : null,
                      );
                    }}
                    style={{
                      background: "#0f172a",
                      color: "#ffffff",
                      border: "2px solid #3b82f6",
                      borderRadius: 8,
                      padding: "10px 12px",
                      fontSize: 13,
                      fontWeight: 800,
                      outline: "none",
                    }}
                  >
                    {AGENT_ORDER.map((name) => {
                      const ag = agentsState[name];
                      return (
                        <option key={name} value={name}>
                          {ag
                            ? `${ag.avatar} Agent ${ag.name} · ${ag.specialization} (₹${((ag.max_principal || 100000) / 100000).toFixed(1)}L)`
                            : `Agent ${name}`}
                        </option>
                      );
                    })}
                  </select>
                </div>

                {/* Modal Action Footer */}
                <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
                  <button
                    type="button"
                    onClick={() => setTestModal(null)}
                    disabled={deployingToLive}
                    style={{
                      padding: "10px 18px",
                      borderRadius: 10,
                      background: "#1e293b",
                      color: "#cbd5e1",
                      border: "1px solid #475569",
                      fontSize: 13,
                      fontWeight: 800,
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleRunInLiveMarket}
                    disabled={deployingToLive}
                    style={{
                      padding: "10px 24px",
                      borderRadius: 10,
                      background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                      color: "#ffffff",
                      border: "1px solid #34d399",
                      fontSize: 14,
                      fontWeight: 900,
                      cursor: deployingToLive ? "not-allowed" : "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      boxShadow: "0 4px 16px rgba(16, 185, 129, 0.4)",
                    }}
                  >
                    <span>🚀</span>
                    <span>
                      {deployingToLive
                        ? "Deploying to Live Market..."
                        : `Run in Live Market (Agent ${testModal.agentName})`}
                    </span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
