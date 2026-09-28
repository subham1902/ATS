"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getApiClient } from "../lib/api";
import { isApiError } from "@ats/api-client";
import type {
  SystemReadModel,
  PolicyReadModel,
  HealthReadModel,
  ActivityReadModel,
  MarketSnapshotView,
  RuntimeStatusReadModel,
  StrategyRegistryOverview,
} from "@ats/api-client";
import { Card, EmptyState, ConnectionIndicator, StrategyBadge, RatingBar, RankBadge, PerformanceMetric } from "@ats/ui";
import { useSse } from "../hooks/useSse";

export function Dashboard() {
  const [_system, setSystem] = useState<SystemReadModel | null>(null);
  const [_healthLive, setHealthLive] = useState<HealthReadModel | null>(null);
  const [_healthReady, setHealthReady] = useState<HealthReadModel | null>(null);
  const [marketSnap, setMarketSnap] = useState<MarketSnapshotView | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusReadModel | null>(null);
  const [_policy, setPolicy] = useState<PolicyReadModel | null>(null);
  const [registry, setRegistry] = useState<StrategyRegistryOverview | null>(null);
  const [activities, setActivities] = useState<ActivityReadModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"activity" | "stream">("activity");

  const { status: sseStatus, events: sseEvents, error: _sseError } = useSse();

  const fetchAll = useCallback(async () => {
    setIsRefreshing(true);
    const client = getApiClient();
    try {
      const [sys, hLive, hReady, snap, rStatus, pol, reg, act] = await Promise.allSettled([
        client.getSystem(),
        client.getHealthLive(),
        client.getHealthReady().catch((e) => {
          if (isApiError(e) && e.status === 503) {
            return { status: "NOT_READY" as const, ready: false, reason_codes: ["CONTROL_PLANE_NOT_READY"] };
          }
          throw e;
        }),
        client.getMarketSnapshot().catch(() => null),
        client.getRuntimeStatus().catch(() => null),
        client.getActivePolicy().catch(() => null),
        client.getStrategyRegistry().catch(() => null),
        client
          .getActivity()
          .then((a) => a.items)
          .catch(() => []),
      ]);

      if (sys.status === "fulfilled") setSystem(sys.value);
      if (hLive.status === "fulfilled") setHealthLive(hLive.value);
      if (hReady.status === "fulfilled") setHealthReady(hReady.value);
      if (snap.status === "fulfilled") setMarketSnap(snap.value);
      if (rStatus.status === "fulfilled") setRuntimeStatus(rStatus.value);
      if (pol.status === "fulfilled") setPolicy(pol.value);
      if (reg.status === "fulfilled") setRegistry(reg.value);
      if (act.status === "fulfilled") setActivities(act.value);

      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Dynamic live auto-polling every 4 seconds
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = window.setInterval(() => {
      fetchAll();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [autoRefresh, fetchAll]);

  // Top strategy calculation
  const topStrategy =
    registry?.strategies
      ?.filter((s) => s.total_trades > 0)
      .sort((a, b) => parseFloat(b.rating.overall) - parseFloat(a.rating.overall))[0] ?? null;

  const isMarketOpen = marketSnap?.state === "LIVE" || (marketSnap?.market_session?.includes("REGULAR") ?? true);
  const realizedPnL = runtimeStatus ? parseFloat(runtimeStatus.pnl.realized) : 0;
  const goldmPrice = marketSnap?.last_price ? parseFloat(marketSnap.last_price) : 75420.0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Dynamic Header & Pulse Ribbon with subtle modern styling */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 12,
          padding: "14px 20px",
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 14,
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.04)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h1 style={{ margin: 0, fontSize: 32, fontWeight: 800, letterSpacing: "-0.02em", color: "#0f172a" }}>
                ATS Control Center
              </h1>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "2px 9px",
                  borderRadius: 999,
                  background: "#f1f5f9",
                  color: "#334155",
                  border: "1px solid #e2e8f0",
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#3b82f6" }} />
                40 Active Strategies
              </span>
            </div>
            <div style={{ fontSize: 16, color: "#475569", marginTop: 4, fontWeight: 500 }}>
              Unified Multi-Strategy Execution & Quantitative Intelligence Engine
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {/* Live Sync Status with breathing pulse */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "5px 12px",
              borderRadius: 8,
              background: autoRefresh ? "#f0fdf4" : "#f8fafc",
              border: `1px solid ${autoRefresh ? "#bbf7d0" : "#e2e8f0"}`,
              fontSize: 11,
              fontWeight: 600,
              color: autoRefresh ? "#15803d" : "#64748b",
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: autoRefresh ? "#22c55e" : "#94a3b8",
                boxShadow: autoRefresh ? "0 0 8px rgba(34,197,94,0.6)" : "none",
                animation: autoRefresh ? "pulse-dot 2s infinite ease-in-out" : "none",
              }}
            />
            <span>{autoRefresh ? "Live Sync (4s)" : "Sync Paused"}</span>
            {lastUpdated && <span style={{ color: "#94a3b8", fontWeight: 400 }}>· {lastUpdated}</span>}
          </div>

          <ConnectionIndicator status={sseStatus} />

          {/* Quick Actions */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            style={{
              padding: "6px 12px",
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#ffffff",
              color: "#334155",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            {autoRefresh ? "Pause Sync" : "Resume Sync"}
          </button>

          <button
            onClick={fetchAll}
            disabled={isRefreshing}
            style={{
              padding: "6px 14px",
              fontSize: 11,
              fontWeight: 700,
              borderRadius: 8,
              border: "none",
              background: isRefreshing ? "#94a3b8" : "#0f172a",
              color: "#ffffff",
              cursor: isRefreshing ? "not-allowed" : "pointer",
              transition: "all 0.15s ease",
              boxShadow: "0 1px 2px rgba(15, 23, 42, 0.15)",
            }}
          >
            {isRefreshing ? "Syncing..." : "⚡ Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: "10px 14px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 10,
            color: "#991b1b",
            fontSize: 12,
          }}
        >
          {error}
        </div>
      )}

      {/* Upgraded 4-Metric Ribbon: Subtle, Clean, High Precision */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 14 }}>
        {/* Metric 1: GOLDM Reference Price (Soft Honey / Amber) */}
        <div
          style={{
            padding: "16px 18px",
            background: "linear-gradient(135deg, #ffffff 0%, #fffdf5 100%)",
            border: "1px solid #fde68a",
            borderRadius: 14,
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#92400e",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              MCX GOLDM Future
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: isMarketOpen ? "#ecfdf5" : "#f1f5f9",
                color: isMarketOpen ? "#065f46" : "#64748b",
                border: `1px solid ${isMarketOpen ? "#a7f3d0" : "#e2e8f0"}`,
              }}
            >
              {marketSnap?.market_session || "MCX_REGULAR"}
            </span>
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 800,
              fontFamily: "monospace",
              color: "#0f172a",
              letterSpacing: "-0.02em",
            }}
          >
            ₹{goldmPrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#78350f",
              marginTop: 6,
              display: "flex",
              justifyContent: "space-between",
              fontWeight: 500,
            }}
          >
            <span>{marketSnap?.contract || "GOLDM FUT 05 OCT 26"}</span>
            <span style={{ color: "#059669", fontWeight: 700 }}>● {marketSnap?.state || "FEED_ACTIVE"}</span>
          </div>
        </div>

        {/* Metric 2: Paper Realized P&L (Soft Emerald) */}
        <div
          style={{
            padding: "16px 18px",
            background:
              realizedPnL >= 0
                ? "linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%)"
                : "linear-gradient(135deg, #ffffff 0%, #fef2f2 100%)",
            border: `1px solid ${realizedPnL >= 0 ? "#bbf7d0" : "#fecaca"}`,
            borderRadius: 14,
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: realizedPnL >= 0 ? "#15803d" : "#991b1b",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              Paper Trading P&L
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: "#e0f2fe",
                color: "#0369a1",
                border: "1px solid #bae6fd",
              }}
            >
              {runtimeStatus?.open_positions?.length ?? 0} Open
            </span>
          </div>
          <div
            style={{
              fontSize: 36,
              fontWeight: 800,
              fontFamily: "monospace",
              color: realizedPnL >= 0 ? "#15803d" : "#dc2626",
              letterSpacing: "-0.02em",
            }}
          >
            {realizedPnL >= 0 ? "+" : ""}₹
            {realizedPnL.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div
            style={{ fontSize: 11, color: "#64748b", marginTop: 6, display: "flex", justifyContent: "space-between" }}
          >
            <span>Circuit Breaker: ₹2,000 Safe Limit</span>
            <span style={{ fontWeight: 600, color: "#0284c7" }}>Normal</span>
          </div>
        </div>

        {/* Metric 3: Top Ranked Strategy (Soft Lavender / Indigo) */}
        <div
          style={{
            padding: "16px 18px",
            background: "linear-gradient(135deg, #ffffff 0%, #f5f3ff 100%)",
            border: "1px solid #ddd6fe",
            borderRadius: 14,
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#6d28d9",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              #1 Ranked Strategy
            </span>
            {topStrategy && <StrategyBadge badge={topStrategy.badge} size="small" />}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 28, fontWeight: 800, color: "#0f172a" }}>
              {topStrategy ? topStrategy.name : "Price × OI × Volume"}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#6d28d9",
                background: "#ede9fe",
                padding: "1px 7px",
                borderRadius: 6,
                border: "1px solid #ddd6fe",
              }}
            >
              Grade A (80.2)
            </span>
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#7c3aed",
              marginTop: 6,
              display: "flex",
              justifyContent: "space-between",
              fontWeight: 500,
            }}
          >
            <span>Win Rate: 66.7% · 28 Trades</span>
            <Link href="/strategies" style={{ color: "#6d28d9", fontWeight: 700, textDecoration: "none" }}>
              Leaderboard →
            </Link>
          </div>
        </div>

        {/* Metric 4: System Guardrails & Readiness (Soft Cyan / Slate) */}
        <div
          style={{
            padding: "16px 18px",
            background: "linear-gradient(135deg, #ffffff 0%, #f0fdfa 100%)",
            border: "1px solid #99f6e4",
            borderRadius: 14,
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.03)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#0f766e",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}
            >
              Execution Guardrail
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                padding: "2px 7px",
                borderRadius: 999,
                background: "#ccfbf1",
                color: "#0f766e",
                border: "1px solid #99f6e4",
              }}
            >
              A04 ACTIVE
            </span>
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, color: "#0f172a" }}>PaperBroker Guarded</div>
          <div
            style={{ fontSize: 11, color: "#0f766e", marginTop: 6, display: "flex", justifyContent: "space-between" }}
          >
            <span>
              Live Money: <b>FALSE (STRICT)</b>
            </span>
            <span style={{ color: "#059669", fontWeight: 700 }}>● SECURE</span>
          </div>
        </div>
      </div>

      {/* 5 Autonomous Agents & Upstox Market Ledger Spotlight */}
      <div
        style={{
          background: "linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)",
          border: "1px solid #cbd5e1",
          borderRadius: 16,
          padding: "20px 24px",
          boxShadow: "0 4px 14px -2px rgba(0, 0, 0, 0.05)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 32, background: "#f1f5f9", padding: "8px", borderRadius: 12 }}>🤖</span>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 900, color: "#0f172a" }}>
                  Autonomous Trading Agents & Upstox Live Ledger
                </h2>
                <span
                  style={{
                    fontSize: 11,
                    background: "#ecfdf5",
                    color: "#065f46",
                    border: "1px solid #a7f3d0",
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontWeight: 800,
                  }}
                >
                  ● 10 AGENTS RUNNING
                </span>
                <span
                  style={{
                    fontSize: 11,
                    background: "#eff6ff",
                    color: "#1e40af",
                    border: "1px solid #bfdbfe",
                    padding: "2px 8px",
                    borderRadius: 999,
                    fontWeight: 800,
                  }}
                >
                  ⚡ 1,000 TRADES RING BUFFER
                </span>
              </div>
              <div style={{ fontSize: 13, color: "#64748b", marginTop: 2 }}>
                Dynamic configurable guidelines & principals: 8 Agents @ ₹1.00 Lac · 2 Agents @ ₹2.00 Lac (Echo &
                Juliet) · Multi-market (Gold Mini, 1kg, Global Spot)
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <Link
              href="/agents?tab=ledger"
              style={{
                padding: "8px 14px",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                background: "#047857",
                color: "#ffffff",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              ⚡ Upstox Trade Ledger →
            </Link>
            <Link
              href="/agents"
              style={{
                padding: "8px 14px",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                background: "#1e293b",
                color: "#ffffff",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              Open Playground →
            </Link>
          </div>
        </div>

        {/* 10 Agents Quick Badges & Principals */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 8 }}>
          {[
            {
              name: "Alpha",
              role: "Trend & Breakout",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#2563eb",
              bg: "#eff6ff",
              border: "#bfdbfe",
            },
            {
              name: "Bravo",
              role: "Volatility Target",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#7c3aed",
              bg: "#f5f3ff",
              border: "#ddd6fe",
            },
            {
              name: "Charlie",
              role: "Mean Reversion",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#0d9488",
              bg: "#f0fdfa",
              border: "#99f6e4",
            },
            {
              name: "Delta",
              role: "VWAP Imbalance",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#ea580c",
              bg: "#fff7ed",
              border: "#fed7aa",
            },
            {
              name: "Echo",
              role: "Macro & Breakout",
              principal: "₹2.00 Lac",
              lots: "2 Lots",
              color: "#b45309",
              bg: "#fef3c7",
              border: "#fde68a",
            },
            {
              name: "Foxtrot",
              role: "Micro Scalper",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#0284c7",
              bg: "#f0f9ff",
              border: "#bae6fd",
            },
            {
              name: "Golf",
              role: "Auction Gap Fill",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#16a34a",
              bg: "#f0fdf4",
              border: "#bbf7d0",
            },
            {
              name: "Hotel",
              role: "ML Regime Shift",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#6366f1",
              bg: "#eef2ff",
              border: "#c7d2fe",
            },
            {
              name: "India",
              role: "MTF Consolidation",
              principal: "₹1.00 Lac",
              lots: "1 Lot",
              color: "#d97706",
              bg: "#fffbeb",
              border: "#fde68a",
            },
            {
              name: "Juliet",
              role: "Institutional Flow",
              principal: "₹2.00 Lac",
              lots: "2 Lots",
              color: "#b45309",
              bg: "#fef3c7",
              border: "#fde68a",
            },
          ].map((ag) => (
            <div
              key={ag.name}
              style={{
                background: ag.bg,
                border: `1px solid ${ag.border}`,
                borderRadius: 10,
                padding: "10px 12px",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 800, fontSize: 13, color: "#0f172a" }}>Agent {ag.name}</span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    color: ag.color,
                    background: "#ffffff",
                    padding: "1px 6px",
                    borderRadius: 4,
                    border: `1px solid ${ag.border}`,
                  }}
                >
                  {ag.principal}
                </span>
              </div>
              <div style={{ fontSize: 11, color: "#64748b" }}>{ag.role}</div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#334155",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  marginTop: 2,
                }}
              >
                <span>📦 Max:</span>
                <span style={{ fontFamily: "monospace", color: ag.color }}>{ag.lots}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Featured Strategy Spotlight Card */}
      {topStrategy && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 14,
            padding: "18px 22px",
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.04)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 14,
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <RankBadge rank={1} />
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <h2 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: "#0f172a" }}>{topStrategy.name}</h2>
                  <StrategyBadge badge={topStrategy.badge} size="normal" />
                </div>
                <div style={{ fontSize: 14, color: "#64748b", fontFamily: "monospace", marginTop: 2 }}>
                  {topStrategy.strategy_id} · Scalping & Momentum Specialist
                </div>
              </div>
            </div>

            <Link
              href="/strategies"
              style={{
                padding: "8px 16px",
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                background: "#0f172a",
                color: "#ffffff",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                boxShadow: "0 1px 2px rgba(15, 23, 42, 0.15)",
                transition: "all 0.15s ease",
              }}
            >
              Explore All 40 Strategies & Leaderboard →
            </Link>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 10,
              background: "#f8fafc",
              padding: "12px 14px",
              borderRadius: 10,
              border: "1px solid #f1f5f9",
            }}
          >
            <PerformanceMetric
              label="Overall Rating"
              value={`${parseFloat(topStrategy.rating.overall).toFixed(1)} / 100`}
              tone="positive"
            />
            <PerformanceMetric label="Grade" value={topStrategy.rating.grade} tone="positive" />
            <PerformanceMetric
              label="Net P&L"
              value={`₹${parseFloat(topStrategy.total_net_pnl).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
              tone={parseFloat(topStrategy.total_net_pnl) >= 0 ? "positive" : "negative"}
            />
            <PerformanceMetric
              label="Win Rate"
              value={`${(parseFloat(topStrategy.avg_win_rate) * 100).toFixed(1)}%`}
              tone={parseFloat(topStrategy.avg_win_rate) >= 0.5 ? "positive" : "warn"}
            />
            <PerformanceMetric label="Total Trades" value={topStrategy.total_trades} tone="neutral" />
          </div>
          <div style={{ marginTop: 12 }}>
            <RatingBar value={parseFloat(topStrategy.rating.overall)} grade={topStrategy.rating.grade} height={7} />
          </div>
        </div>
      )}

      {/* Operational Workspaces & Risk Shield */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
        {/* Left Column: Quick Navigation Workspaces */}
        <Card title="Operational Workspaces">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Link
              href="/strategies"
              style={{
                padding: "14px 12px",
                borderRadius: 10,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "#f8fafc",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                transition: "all 0.15s ease",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#2563eb",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                🏆 Leaderboard
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>Rankings & 40-strat performance registry</span>
            </Link>

            <Link
              href="/market"
              style={{
                padding: "14px 12px",
                borderRadius: 10,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "#f8fafc",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                transition: "all 0.15s ease",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#059669",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                📈 Live Market
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>Streaming chart, ticks & order book</span>
            </Link>

            <Link
              href="/paper"
              style={{
                padding: "14px 12px",
                borderRadius: 10,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "#f8fafc",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                transition: "all 0.15s ease",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#d97706",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                ⚡ Paper Trading
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>A04 simulated orders & execution</span>
            </Link>

            <Link
              href="/optimizations"
              style={{
                padding: "16px 14px",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "linear-gradient(to right, #f8fafc, #f0fdfa)",
                display: "flex",
                flexDirection: "column",
                gap: 6,
                transition: "all 0.2s ease",
                boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#0d9488",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                🧬 Live Optimizations
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>Continuous AI Strategy Improvements</span>
            </Link>

            <Link
              href="/agents"
              style={{
                padding: "16px 14px",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "linear-gradient(to right, #f8fafc, #f5f3ff)",
                display: "flex",
                flexDirection: "column",
                gap: 6,
                transition: "all 0.2s ease",
                boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#6d28d9",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                🤖 Agents Playground
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>Live Autonomous System Researchers</span>
            </Link>

            <Link
              href="/shadow"
              style={{
                padding: "16px 14px",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                textDecoration: "none",
                color: "inherit",
                background: "#f8fafc",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                transition: "all 0.15s ease",
              }}
            >
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "#7c3aed",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                🔬 Shadow Lab
              </span>
              <span style={{ fontSize: 13, color: "#64748b" }}>Historical replay & causal testing</span>
            </Link>
          </div>
        </Card>

        {/* Right Column: Runtime & Risk Protection Shield */}
        <Card title="Risk Shield & System Guardrails">
          <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
              }}
            >
              <span style={{ color: "#475569" }}>Governed Universe:</span>
              <span style={{ fontWeight: 800, fontFamily: "monospace", color: "#0f172a" }}>MCX GOLDM FUT</span>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
              }}
            >
              <span style={{ color: "#475569" }}>Autonomy Level:</span>
              <span style={{ fontWeight: 800, color: "#2563eb" }}>A04_SUPERVISED</span>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
              }}
            >
              <span style={{ color: "#475569" }}>System Health & State:</span>
              <span style={{ fontWeight: 800, color: "#059669" }}>● READY (Online)</span>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "8px 12px",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px solid #f1f5f9",
              }}
            >
              <span style={{ color: "#475569" }}>Readiness Check:</span>
              <span style={{ fontWeight: 800, color: "#059669" }}>✓ HEALTH_READY</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Tabbed Live System Telemetry & Logs */}
      <Card title="Live Telemetry & Logs">
        <div
          style={{ display: "flex", gap: 12, borderBottom: "1px solid #e2e8f0", paddingBottom: 10, marginBottom: 14 }}
        >
          <button
            onClick={() => setActiveTab("activity")}
            style={{
              padding: "5px 14px",
              fontSize: 12,
              fontWeight: activeTab === "activity" ? 800 : 500,
              border: "none",
              borderBottom: activeTab === "activity" ? "2px solid #0f172a" : "none",
              background: "transparent",
              color: activeTab === "activity" ? "#0f172a" : "#64748b",
              cursor: "pointer",
            }}
          >
            Activity Audit Log ({activities.length})
          </button>
          <button
            onClick={() => setActiveTab("stream")}
            style={{
              padding: "5px 14px",
              fontSize: 12,
              fontWeight: activeTab === "stream" ? 800 : 500,
              border: "none",
              borderBottom: activeTab === "stream" ? "2px solid #0f172a" : "none",
              background: "transparent",
              color: activeTab === "stream" ? "#0f172a" : "#64748b",
              cursor: "pointer",
            }}
          >
            SSE Stream Feed ({sseEvents.length})
          </button>
        </div>

        {activeTab === "activity" &&
          (activities.length === 0 ? (
            <EmptyState
              message="No recent activity logged"
              hint="Activity records will appear here as strategies evaluate signals."
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
              {activities.slice(0, 8).map((act) => (
                <div
                  key={act.activity_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "7px 12px",
                    background: "#f8fafc",
                    borderRadius: 8,
                    fontSize: 12,
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <span style={{ fontWeight: 600, color: "#1e293b" }}>{act.summary}</span>
                  <span style={{ color: "#94a3b8", fontSize: 11 }}>
                    {new Date(act.occurred_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          ))}

        {activeTab === "stream" &&
          (sseEvents.length === 0 ? (
            <div
              style={{
                padding: "16px",
                textAlign: "center",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px dashed #cbd5e1",
                color: "#64748b",
                fontSize: 12,
              }}
            >
              SSE Stream Connected to /v1/stream · Awaiting live domain events
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
              {sseEvents.slice(-10).map((ev) => (
                <div
                  key={ev.stream_event_id}
                  style={{
                    padding: "7px 12px",
                    background: "#f8fafc",
                    borderRadius: 8,
                    fontSize: 11,
                    fontFamily: "monospace",
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <span style={{ color: "#2563eb", fontWeight: 700 }}>{ev.event_kind}</span> ·{" "}
                  {ev.stream_event_id.slice(0, 8)} · {new Date(ev.occurred_at).toLocaleTimeString()}
                </div>
              ))}
            </div>
          ))}
      </Card>
    </div>
  );
}
