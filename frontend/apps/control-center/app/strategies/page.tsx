"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Card, Badge, StrategyBadge, RatingBar, RankBadge, PerformanceMetric } from "@ats/ui";
import { getApiClient } from "../../lib/api";
import { StrategyLabView } from "./StrategyLabView";
import type {
  StrategyRegistryOverview,
  LeaderboardResponse,
  LeaderboardEntry,
  StrategyRegistryEntry,
} from "@ats/api-client";

// ---------------------------------------------------------------------------
// Context label helpers
// ---------------------------------------------------------------------------

const CONTEXT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  BACKTEST: { label: "Backtest", icon: "🔬", color: "#6366f1" },
  PAPER_TRADE: { label: "Paper Trade", icon: "📝", color: "#0891b2" },
  SHADOW: { label: "Shadow", icon: "👁️", color: "#7c3aed" },
  LIVE_FORWARD: { label: "Live Forward", icon: "🔴", color: "#dc2626" },
  REAL_ACCOUNT: { label: "Real Account", icon: "💰", color: "#059669" },
};

const TIMEFRAMES = ["ALL", "5m", "15m", "1h", "4h", "daily"] as const;
const CONTEXTS = ["ALL", "BACKTEST", "PAPER_TRADE", "SHADOW", "LIVE_FORWARD", "REAL_ACCOUNT"] as const;
const BADGES = ["ALL", "SCALPING", "INTRADAY", "SWING", "POSITIONAL", "META_ROUTER", "BASELINE"] as const;

function formatPnl(val: string | number): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "—";
  const prefix = n >= 0 ? "+" : "";
  return `${prefix}₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPercent(val: string | number): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n) || n === 0) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function formatDecimal(val: string | number, digits = 2): string {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "—";
  return n.toFixed(digits);
}

function pnlTone(val: string | number): "positive" | "negative" | "neutral" {
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (n > 0) return "positive";
  if (n < 0) return "negative";
  return "neutral";
}

// ---------------------------------------------------------------------------
// Expanded strategy detail row
// ---------------------------------------------------------------------------

function StrategyDetail({ entry }: { entry: StrategyRegistryEntry }) {
  const best = entry.best_performance;
  return (
    <tr>
      <td colSpan={10} style={{ padding: 0, background: "#fafbfc" }}>
        <div style={{ padding: "16px 20px", borderTop: "2px solid #e0e7ff", borderBottom: "2px solid #e0e7ff" }}>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 18, fontWeight: 800 }}>{entry.name}</span>
            <StrategyBadge badge={entry.badge} size="large" />
            <Badge tone={entry.data_blocked ? "warn" : entry.classification === "REJECTED" ? "danger" : entry.classification === "VALIDATED" ? "success" : "neutral"}>
              {entry.classification}
            </Badge>
            <Badge tone="neutral">{entry.evidence_tier}</Badge>
          </div>

          {/* Metrics grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8, marginBottom: 12 }}>
            <PerformanceMetric label="Total Trades" value={entry.total_trades} tone="neutral" />
            <PerformanceMetric label="Total Net P&L" value={formatPnl(entry.total_net_pnl)} tone={pnlTone(entry.total_net_pnl)} />
            <PerformanceMetric label="Avg Win Rate" value={formatPercent(entry.avg_win_rate)} tone={parseFloat(entry.avg_win_rate) > 0.5 ? "positive" : "warn"} />
            <PerformanceMetric label="Rating" value={parseFloat(entry.rating.overall).toFixed(1)} tone={parseFloat(entry.rating.overall) >= 50 ? "positive" : "negative"} />
            <PerformanceMetric label="Grade" value={entry.rating.grade} tone={["S", "A"].includes(entry.rating.grade) ? "positive" : ["B", "C"].includes(entry.rating.grade) ? "warn" : "negative"} />
            <PerformanceMetric label="Family" value={entry.family || "—"} tone="neutral" />
          </div>

          {/* Rating breakdown */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#6b7280", marginBottom: 6, textTransform: "uppercase" }}>Rating Breakdown</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
              {Object.entries(entry.rating.breakdown).map(([key, val]) => (
                <div key={key}>
                  <div style={{ fontSize: 10, color: "#6b7280", marginBottom: 2 }}>{key.replace(/_/g, " ")}</div>
                  <RatingBar value={parseFloat(val)} showLabel grade={undefined} height={6} />
                </div>
              ))}
            </div>
          </div>

          {/* Best performance */}
          {best && (
            <div style={{ padding: 10, background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#15803d", marginBottom: 6 }}>🏆 Best Performance</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", gap: 8 }}>
                <PerformanceMetric label="Timeframe" value={best.timeframe} tone="neutral" />
                <PerformanceMetric label="Context" value={CONTEXT_LABELS[best.execution_context]?.label ?? best.execution_context} tone="neutral" />
                <PerformanceMetric label="Net P&L" value={formatPnl(best.net_pnl)} tone={pnlTone(best.net_pnl)} />
                <PerformanceMetric label="Win Rate" value={formatPercent(best.win_rate)} tone={parseFloat(best.win_rate) > 0.5 ? "positive" : "warn"} />
                <PerformanceMetric label="Profit Factor" value={formatDecimal(best.profit_factor)} tone={parseFloat(best.profit_factor) >= 1 ? "positive" : "negative"} />
                <PerformanceMetric label="Max DD" value={formatPnl(best.max_drawdown)} tone="negative" />
                <PerformanceMetric label="Trades" value={best.trades_count} tone="neutral" />
                <PerformanceMetric label="Budget" value={formatPnl(best.capital_budget)} tone="neutral" />
              </div>
            </div>
          )}

          {/* Performance records */}
          {entry.performance_records.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#6b7280", marginBottom: 6, textTransform: "uppercase" }}>
                Performance History ({entry.performance_records.length} records)
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e5e7eb", color: "#6b7280" }}>
                      <th style={{ padding: "4px 6px", textAlign: "left" }}>Context</th>
                      <th style={{ padding: "4px 6px", textAlign: "left" }}>TF</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>Trades</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>WR</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>Net P&L</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>PF</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>Max DD</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>1.5x Cost</th>
                      <th style={{ padding: "4px 6px", textAlign: "right" }}>2x Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entry.performance_records.map((r) => (
                      <tr key={r.run_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "4px 6px" }}>
                          <span style={{ fontSize: 10 }}>
                            {CONTEXT_LABELS[r.execution_context]?.icon ?? "📋"}{" "}
                            {CONTEXT_LABELS[r.execution_context]?.label ?? r.execution_context}
                          </span>
                        </td>
                        <td style={{ padding: "4px 6px", fontFamily: "monospace" }}>{r.timeframe}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace" }}>{r.trades_count}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace" }}>{formatPercent(r.win_rate)}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace", color: parseFloat(r.net_pnl) >= 0 ? "#16a34a" : "#dc2626" }}>{formatPnl(r.net_pnl)}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace" }}>{formatDecimal(r.profit_factor)}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace", color: "#dc2626" }}>{formatPnl(r.max_drawdown)}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace", color: r.cost_1_5x_net && parseFloat(r.cost_1_5x_net) > 0 ? "#16a34a" : "#dc2626" }}>
                          {r.cost_1_5x_net ? formatPnl(r.cost_1_5x_net) : "—"}
                        </td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontFamily: "monospace", color: r.cost_2_0x_net && parseFloat(r.cost_2_0x_net) > 0 ? "#16a34a" : "#dc2626" }}>
                          {r.cost_2_0x_net ? formatPnl(r.cost_2_0x_net) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Blocker info */}
          {entry.blocker_reason && (
            <div style={{ marginTop: 10, padding: 8, background: "#fef3c7", borderRadius: 6, fontSize: 11, color: "#92400e", border: "1px solid #fcd34d" }}>
              ⚠️ <strong>Blocker:</strong> {entry.blocker_reason}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function StrategiesPage() {
  const [registry, setRegistry] = useState<StrategyRegistryOverview | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [timeframe, setTimeframe] = useState<string>("ALL");
  const [context, setContext] = useState<string>("ALL");
  const [badgeFilter, setBadgeFilter] = useState<string>("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [view, setView] = useState<"lab" | "leaderboard" | "registry">("lab");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const api = getApiClient();
    Promise.all([
      api.getStrategyRegistry().catch(() => null),
      api.getStrategyLeaderboard(
        timeframe === "ALL" ? undefined : timeframe,
        context === "ALL" ? undefined : context,
        badgeFilter === "ALL" ? undefined : badgeFilter,
      ).catch(() => null),
    ]).then(([reg, lb]) => {
      if (cancelled) return;
      if (reg) setRegistry(reg);
      if (lb) setLeaderboard(lb);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [timeframe, context, badgeFilter]);

  // Build lookup for registry entries
  const registryLookup = useMemo(() => {
    const map = new Map<string, StrategyRegistryEntry>();
    if (registry) {
      for (const s of registry.strategies) map.set(s.strategy_id, s);
    }
    return map;
  }, [registry]);

  const entries = leaderboard?.entries ?? [];

  // Stats
  const topPerformer = entries.length > 0 ? entries[0] : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Navigation View Toggle */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: 16 }}>
        <div style={{ display: "flex", gap: 6, background: "#f1f5f9", borderRadius: 12, padding: 4, border: "1px solid #cbd5e1" }}>
          {(["lab", "leaderboard", "registry"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              style={{
                padding: "8px 18px",
                borderRadius: 9,
                fontSize: 14,
                fontWeight: view === v ? 800 : 600,
                background: view === v ? "#0f172a" : "transparent",
                color: view === v ? "#ffffff" : "#475569",
                border: "none",
                cursor: "pointer",
                boxShadow: view === v ? "0 2px 8px rgba(15, 23, 42, 0.15)" : "none",
                transition: "all 0.15s ease",
              }}
            >
              {v === "lab" ? "🧪 Strategy Lab & Best Store" : v === "leaderboard" ? "🏆 Leaderboard" : "📋 Registry"}
            </button>
          ))}
        </div>
      </div>

      {view === "lab" && <StrategyLabView />}

      {view !== "lab" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Page header */}
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 900, background: "linear-gradient(90deg, #111827, #4f46e5)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Strategy Performance Registry & Leaderboard
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
              {registry ? `${registry.total_strategies} registered strategies · ${registry.rated_count} rated · Avg rating: ${parseFloat(registry.avg_rating).toFixed(1)}` : "Loading..."}
            </p>
          </div>

          {/* Stats overview */}
          {registry && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
              <PerformanceMetric label="Total Strategies" value={registry.total_strategies} tone="neutral" />
              <PerformanceMetric label="Rated" value={registry.rated_count} tone="positive" />
              <PerformanceMetric label="Data Blocked" value={registry.data_blocked_count} tone="warn" />
              <PerformanceMetric label="Rejected" value={registry.rejected_count} tone="negative" />
              <PerformanceMetric label="Validated" value={registry.validated_count} tone="positive" />
              <PerformanceMetric label="Avg Rating" value={parseFloat(registry.avg_rating).toFixed(1)} tone={parseFloat(registry.avg_rating) >= 40 ? "positive" : "warn"} />
              {topPerformer && (
                <div style={{ padding: "8px 10px", borderRadius: 8, background: "linear-gradient(135deg, #fef3c7, #fde68a)", border: "1px solid #f59e0b", minWidth: 80 }}>
                  <div style={{ fontSize: 10, color: "#92400e", fontWeight: 600, textTransform: "uppercase" }}>🏆 Top Strategy</div>
                  <div style={{ fontSize: 14, fontWeight: 900, color: "#78350f" }}>{topPerformer.name}</div>
                  <div style={{ fontSize: 10, color: "#92400e" }}>Rating: {parseFloat(topPerformer.rating.overall).toFixed(1)} ({topPerformer.rating.grade})</div>
                </div>
              )}
            </div>
          )}

          {/* Badge distribution */}
          {registry && Object.keys(registry.top_badge_distribution).length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 600 }}>Strategy Types:</span>
              {Object.entries(registry.top_badge_distribution).map(([badge, count]) => (
                <div key={badge} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <StrategyBadge badge={badge} size="small" />
                  <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 700 }}>×{count}</span>
                </div>
              ))}
            </div>
          )}

          {/* Filters */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            {/* Timeframe tabs */}
            <div style={{ display: "flex", gap: 2, background: "#f3f4f6", borderRadius: 8, padding: 2 }}>
              {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => setTimeframe(tf)}
              style={{
                padding: "5px 10px",
                borderRadius: 5,
                fontSize: 11,
                fontWeight: timeframe === tf ? 700 : 500,
                background: timeframe === tf ? "#111827" : "transparent",
                color: timeframe === tf ? "white" : "#6b7280",
                border: "none",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              {tf}
            </button>
          ))}
        </div>

        {/* Context filter */}
        <select
          value={context}
          onChange={(e) => setContext(e.target.value)}
          style={{
            padding: "5px 8px",
            borderRadius: 6,
            fontSize: 11,
            border: "1px solid #d1d5db",
            background: "white",
            color: "#374151",
            cursor: "pointer",
          }}
        >
          {CONTEXTS.map((c) => (
            <option key={c} value={c}>
              {c === "ALL" ? "All Contexts" : CONTEXT_LABELS[c]?.label ?? c}
            </option>
          ))}
        </select>

        {/* Badge filter */}
        <select
          value={badgeFilter}
          onChange={(e) => setBadgeFilter(e.target.value)}
          style={{
            padding: "5px 8px",
            borderRadius: 6,
            fontSize: 11,
            border: "1px solid #d1d5db",
            background: "white",
            color: "#374151",
            cursor: "pointer",
          }}
        >
          {BADGES.map((b) => (
            <option key={b} value={b}>
              {b === "ALL" ? "All Badges" : b}
            </option>
          ))}
        </select>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
          Loading strategy registry...
        </div>
      )}
      {error && (
        <div style={{ padding: 12, background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, color: "#991b1b", fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Leaderboard view */}
      {!loading && view === "leaderboard" && (
        <Card title={`Strategy Leaderboard (${entries.length} ranked${timeframe !== "ALL" ? ` · ${timeframe}` : ""})`}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb", color: "#6b7280" }}>
                  <th style={{ padding: "8px 6px", width: 40 }}>Rank</th>
                  <th style={{ padding: "8px 6px" }}>Strategy</th>
                  <th style={{ padding: "8px 6px", width: 90 }}>Badge</th>
                  <th style={{ padding: "8px 6px", width: 160 }}>Rating</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Net P&L</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Win Rate</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>PF</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Max DD</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Trades</th>
                  <th style={{ padding: "8px 6px" }}>Context</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => {
                  const fullEntry = registryLookup.get(e.strategy_id);
                  const isExpanded = expandedId === e.strategy_id;
                  return (
                    <React.Fragment key={e.strategy_id}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : e.strategy_id)}
                        style={{
                          borderBottom: "1px solid #f3f4f6",
                          cursor: "pointer",
                          background: isExpanded ? "#f0f4ff" : e.rank <= 3 ? "#fffbeb08" : "transparent",
                          transition: "background 0.15s ease",
                        }}
                        onMouseOver={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = isExpanded ? "#e8edff" : "#f9fafb"; }}
                        onMouseOut={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = isExpanded ? "#f0f4ff" : "transparent"; }}
                      >
                        <td style={{ padding: "8px 6px" }}>
                          <RankBadge rank={e.rank} />
                        </td>
                        <td style={{ padding: "8px 6px" }}>
                          <div style={{ fontWeight: 700, fontSize: 13 }}>{e.name}</div>
                          <div style={{ fontSize: 10, color: "#6b7280", fontFamily: "monospace" }}>{e.strategy_id}</div>
                        </td>
                        <td style={{ padding: "8px 6px" }}>
                          <StrategyBadge badge={e.badge} size="small" />
                        </td>
                        <td style={{ padding: "8px 6px" }}>
                          <RatingBar value={parseFloat(e.rating.overall)} grade={e.rating.grade} height={6} />
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace", fontWeight: 700, color: parseFloat(e.net_pnl) >= 0 ? "#16a34a" : "#dc2626" }}>
                          {formatPnl(e.net_pnl)}
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace" }}>
                          {formatPercent(e.win_rate)}
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace", color: parseFloat(e.profit_factor) >= 1 ? "#16a34a" : "#dc2626" }}>
                          {formatDecimal(e.profit_factor)}
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace", color: "#dc2626" }}>
                          {formatPnl(e.max_drawdown)}
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace" }}>
                          {e.trades_count || "—"}
                        </td>
                        <td style={{ padding: "8px 6px" }}>
                          {e.execution_context && CONTEXT_LABELS[e.execution_context] ? (
                            <span style={{ fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
                              {CONTEXT_LABELS[e.execution_context].icon}
                              <span style={{ color: CONTEXT_LABELS[e.execution_context].color, fontWeight: 600 }}>
                                {CONTEXT_LABELS[e.execution_context].label}
                              </span>
                            </span>
                          ) : "—"}
                        </td>
                      </tr>
                      {isExpanded && fullEntry && <StrategyDetail entry={fullEntry} />}
                    </React.Fragment>
                  );
                })}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={10} style={{ textAlign: "center", padding: 24, color: "#6b7280" }}>
                      No strategies match the current filters
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Registry view */}
      {!loading && view === "registry" && registry && (
        <Card title={`Full Strategy Registry (${registry.total_strategies})`}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e5e7eb", color: "#6b7280" }}>
                  <th style={{ padding: "8px 6px" }}>ID</th>
                  <th style={{ padding: "8px 6px" }}>Name</th>
                  <th style={{ padding: "8px 6px" }}>Badge</th>
                  <th style={{ padding: "8px 6px" }}>Classification</th>
                  <th style={{ padding: "8px 6px" }}>Evidence</th>
                  <th style={{ padding: "8px 6px", width: 140 }}>Rating</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Trades</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Net P&L</th>
                  <th style={{ padding: "8px 6px" }}>Paper Ready</th>
                  <th style={{ padding: "8px 6px" }}>Blocker</th>
                </tr>
              </thead>
              <tbody>
                {registry.strategies.map((s) => {
                  const isExpanded = expandedId === s.strategy_id;
                  return (
                    <React.Fragment key={s.strategy_id}>
                      <tr
                        onClick={() => setExpandedId(isExpanded ? null : s.strategy_id)}
                        style={{
                          borderBottom: "1px solid #f3f4f6",
                          cursor: "pointer",
                          background: isExpanded ? "#f0f4ff" : "transparent",
                          transition: "background 0.15s ease",
                        }}
                        onMouseOver={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = isExpanded ? "#e8edff" : "#f9fafb"; }}
                        onMouseOut={(ev) => { (ev.currentTarget as HTMLTableRowElement).style.background = isExpanded ? "#f0f4ff" : "transparent"; }}
                      >
                        <td style={{ padding: "8px 6px", fontFamily: "monospace", fontWeight: 700 }}>{s.strategy_id}</td>
                        <td style={{ padding: "8px 6px", fontWeight: 600 }}>{s.name}</td>
                        <td style={{ padding: "8px 6px" }}><StrategyBadge badge={s.badge} size="small" /></td>
                        <td style={{ padding: "8px 6px" }}>
                          <Badge tone={s.classification === "REJECTED" ? "danger" : s.data_blocked ? "warn" : s.classification === "VALIDATED" ? "success" : "neutral"}>
                            {s.classification}
                          </Badge>
                        </td>
                        <td style={{ padding: "8px 6px", fontSize: 10 }}>{s.evidence_tier}</td>
                        <td style={{ padding: "8px 6px" }}>
                          <RatingBar value={parseFloat(s.rating.overall)} grade={s.rating.grade} height={5} />
                        </td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace" }}>{s.total_trades || "—"}</td>
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace", color: parseFloat(s.total_net_pnl) >= 0 ? "#16a34a" : "#dc2626" }}>
                          {s.total_trades > 0 ? formatPnl(s.total_net_pnl) : "—"}
                        </td>
                        <td style={{ padding: "8px 6px" }}>
                          <Badge tone={s.paper_readiness === "PAPER_CANDIDATE" ? "success" : "unknown"}>
                            {s.paper_readiness}
                          </Badge>
                        </td>
                        <td style={{ padding: "8px 6px", color: "#6b7280", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {s.blocker_reason || "—"}
                        </td>
                      </tr>
                      {isExpanded && <StrategyDetail entry={s} />}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
        </div>
      )}
    </div>
  );
}

