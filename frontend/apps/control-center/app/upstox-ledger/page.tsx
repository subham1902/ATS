"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";

interface UpstoxLiveTrade {
  trade_id: string;
  timestamp: string;
  ist_timestamp: string;
  agent_id: string;
  agent_name: string;
  strategy_id: string;
  strategy_name: string;
  exchange: string;
  instrument_key: string;
  symbol: string;
  order_side: string;
  direction: "LONG" | "SHORT";
  lot_size: number;
  lots: number;
  total_quantity: number;
  lot_unit: string;
  entry_price: number;
  exit_price: number;
  turnover: number;
  margin_utilized: number;
  agent_max_principal: number;
  gross_pnl: number;
  brokerage: number;
  stt_ctt: number;
  exchange_charges: number;
  gst: number;
  sebi_charges: number;
  stamp_duty: number;
  total_charges: number;
  net_pnl: number;
  net_roi_pct: number;
  post_trade_balance: number;
  duration_seconds: number;
  exit_reason: string;
  upstox_feed_source: string;
  exchange_timestamp?: string;
  hypothesis?: string;
}

interface LedgerSummary {
  capacity: number;
  total_trades: number;
  total_lots_traded: number;
  total_turnover: number;
  gross_pnl: number;
  total_upstox_charges: number;
  net_pnl: number;
  win_rate: number;
  profit_factor: number;
  winning_trades: number;
  losing_trades: number;
  last_trade_time: string | null;
}

export default function UpstoxLedgerPage() {
  const [trades, setTrades] = useState<UpstoxLiveTrade[]>([]);
  const [summary, setSummary] = useState<LedgerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(2000);
  const [filterAgent, setFilterAgent] = useState("ALL");
  const [filterDirection, setFilterDirection] = useState("ALL");
  const [filterMarket, setFilterMarket] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [limit, setLimit] = useState(200);
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const fetchLedger = async () => {
    try {
      const res = await fetch(`/v1/agents/upstox-trades?limit=${limit}`);
      if (res.ok) {
        const data = await res.json();
        setTrades(data.trades || []);
        setSummary(data.summary || null);
      }
    } catch (e) {
      console.error("Failed to fetch Upstox trade ledger:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
    if (autoRefreshInterval > 0) {
      const timer = setInterval(fetchLedger, autoRefreshInterval);
      return () => clearInterval(timer);
    }
  }, [autoRefreshInterval, limit]);

  const handleClearLedger = async () => {
    if (
      !confirm(
        "Are you sure you want to clear the Upstox live trades ledger? This resets all trades in this 1,000 capacity buffer.",
      )
    ) {
      return;
    }
    try {
      setClearing(true);
      const res = await fetch("/v1/agents/upstox-trades", { method: "DELETE" });
      if (res.ok) {
        showToast("🧹 Upstox Trade Ledger buffer cleared!");
        fetchLedger();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setClearing(false);
    }
  };

  const filteredTrades = useMemo(() => {
    return trades.filter((t) => {
      if (filterAgent !== "ALL" && t.agent_name !== filterAgent) return false;
      if (filterDirection !== "ALL" && t.direction !== filterDirection) return false;
      if (filterMarket !== "ALL") {
        if (filterMarket === "MCX" && !t.exchange.includes("MCX")) return false;
        if (filterMarket === "GLOBAL" && t.exchange.includes("MCX")) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matches =
          t.trade_id.toLowerCase().includes(q) ||
          t.agent_name.toLowerCase().includes(q) ||
          t.strategy_name.toLowerCase().includes(q) ||
          t.strategy_id.toLowerCase().includes(q) ||
          t.symbol.toLowerCase().includes(q) ||
          (t.hypothesis && t.hypothesis.toLowerCase().includes(q));
        if (!matches) return false;
      }
      return true;
    });
  }, [trades, filterAgent, filterDirection, filterMarket, searchQuery]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, minHeight: "100vh" }}>
      {/* Toast Notification */}
      {toastMessage && (
        <div
          style={{
            position: "fixed",
            top: 24,
            right: 24,
            background: "#0f172a",
            color: "#ffffff",
            padding: "14px 22px",
            borderRadius: 12,
            boxShadow: "0 10px 25px rgba(0,0,0,0.3)",
            zIndex: 9999,
            fontWeight: 800,
            fontSize: 14,
            border: "1px solid #38bdf8",
          }}
        >
          {toastMessage}
        </div>
      )}

      {/* Header Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, #022c22 0%, #064e3b 50%, #0f172a 100%)",
          borderRadius: 20,
          padding: "24px 28px",
          color: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          boxShadow: "0 10px 25px -5px rgba(6, 78, 59, 0.4)",
          border: "2px solid #059669",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span
            style={{
              fontSize: 32,
              background: "#065f46",
              padding: "10px",
              borderRadius: 16,
              border: "1px solid #34d399",
            }}
          >
            ⚡
          </span>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h1 style={{ margin: 0, fontSize: 24, fontWeight: 900, letterSpacing: "-0.02em" }}>
                Upstox Live Market Trade Ledger
              </h1>
              <span
                style={{
                  background: "#10b981",
                  color: "#022c22",
                  padding: "3px 10px",
                  borderRadius: 999,
                  fontSize: 11,
                  fontWeight: 900,
                  textTransform: "uppercase",
                }}
              >
                1,000 Capacity Ring Buffer
              </span>
            </div>
            <p style={{ margin: "4px 0 0 0", color: "#a7f3d0", fontSize: 13, fontWeight: 500 }}>
              Authentic exchange executions with exact lot sizes, micro-gram metrics, Upstox brokerage, STT, and tax
              breakdowns.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Link
            href="/agents"
            style={{
              background: "#065f46",
              border: "1px solid #34d399",
              color: "#ffffff",
              padding: "10px 18px",
              borderRadius: 12,
              fontSize: 13,
              fontWeight: 800,
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>🤖 Back to Agents Playground</span>
          </Link>

          <a
            href="/v1/agents/upstox-trades/export"
            download
            style={{
              background: "#2563eb",
              border: "1px solid #60a5fa",
              color: "#ffffff",
              padding: "10px 18px",
              borderRadius: 12,
              fontSize: 13,
              fontWeight: 800,
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span>📥 Export Ledger CSV</span>
          </a>

          <button
            onClick={handleClearLedger}
            disabled={clearing}
            style={{
              background: "rgba(239, 68, 68, 0.2)",
              border: "1px solid rgba(239, 68, 68, 0.5)",
              color: "#fca5a5",
              padding: "10px 16px",
              borderRadius: 12,
              fontSize: 13,
              fontWeight: 800,
              cursor: clearing ? "not-allowed" : "pointer",
            }}
          >
            {clearing ? "Clearing..." : "🧹 Clear Ledger"}
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14 }}>
        {/* Ring Buffer */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: 16,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
            Ring Buffer Capacity
          </div>
          <div style={{ fontSize: 26, fontWeight: 900, color: "#0f172a", marginTop: 4 }}>
            {summary?.total_trades ?? trades.length} / 1,000
          </div>
          <div style={{ fontSize: 11, color: "#059669", fontWeight: 700, marginTop: 2 }}>● Upstox Live Ledger</div>
        </div>

        {/* Net Settled PnL */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: 16,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
            Net Settled P&L
          </div>
          <div
            style={{
              fontSize: 26,
              fontWeight: 900,
              color: (summary?.net_pnl ?? 0) >= 0 ? "#16a34a" : "#dc2626",
              marginTop: 4,
            }}
          >
            {(summary?.net_pnl ?? 0) >= 0 ? "+" : ""}₹
            {(summary?.net_pnl ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            Gross: ₹{(summary?.gross_pnl ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 1 })}
          </div>
        </div>

        {/* Total Lots Traded */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: 16,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
            Total Lots Traded
          </div>
          <div style={{ fontSize: 26, fontWeight: 900, color: "#2563eb", marginTop: 4 }}>
            {summary?.total_lots_traded ?? 0} Lots
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            Turnover: ₹{((summary?.total_turnover ?? 0) / 100000).toFixed(1)} Lac
          </div>
        </div>

        {/* Upstox Charges & Taxes */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: 16,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
            Total Fees & Taxes
          </div>
          <div style={{ fontSize: 26, fontWeight: 900, color: "#d97706", marginTop: 4 }}>
            ₹
            {(summary?.total_upstox_charges ?? 0).toLocaleString("en-IN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Brokerage, STT, GST & SEBI</div>
        </div>

        {/* Win Rate */}
        <div
          style={{
            background: "#ffffff",
            padding: "16px 20px",
            borderRadius: 16,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.03)",
          }}
        >
          <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase" }}>
            Win Rate & Factor
          </div>
          <div
            style={{
              fontSize: 26,
              fontWeight: 900,
              color: (summary?.win_rate ?? 0) >= 50 ? "#16a34a" : "#dc2626",
              marginTop: 4,
            }}
          >
            {summary?.win_rate ?? 0}%
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
            Profit Factor: {summary?.profit_factor ?? "0.00"} ({summary?.winning_trades ?? 0}W /{" "}
            {summary?.losing_trades ?? 0}L)
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          background: "#ffffff",
          padding: "16px 20px",
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
        }}
      >
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", flex: 1 }}>
          {/* Search */}
          <input
            type="text"
            placeholder="Search Trade ID, Agent, Strategy, Symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              padding: "8px 14px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              fontSize: 13,
              fontWeight: 600,
              minWidth: 260,
              outline: "none",
            }}
          />

          {/* Agent Filter */}
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              fontSize: 13,
              fontWeight: 700,
              color: "#1e293b",
              background: "#ffffff",
            }}
          >
            <option value="ALL">All 10 Agents</option>
            {["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet"].map(
              (name) => (
                <option key={name} value={name}>
                  Agent {name}
                </option>
              ),
            )}
          </select>

          {/* Direction Filter */}
          <select
            value={filterDirection}
            onChange={(e) => setFilterDirection(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              fontSize: 13,
              fontWeight: 700,
              color: "#1e293b",
              background: "#ffffff",
            }}
          >
            <option value="ALL">All Directions</option>
            <option value="LONG">LONG Only</option>
            <option value="SHORT">SHORT Only</option>
          </select>

          {/* Market Filter */}
          <select
            value={filterMarket}
            onChange={(e) => setFilterMarket(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              fontSize: 13,
              fontWeight: 700,
              color: "#1e293b",
              background: "#ffffff",
            }}
          >
            <option value="ALL">All Markets</option>
            <option value="MCX">MCX Exchange (INR)</option>
            <option value="GLOBAL">Global Spot (PAXG/USD)</option>
          </select>
        </div>

        {/* Auto Refresh & Limit Controls */}
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#64748b" }}
          >
            <span>Auto Refresh:</span>
            <select
              value={autoRefreshInterval}
              onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                border: "1px solid #cbd5e1",
                fontSize: 12,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              <option value={1000}>1s (Ultra Fast)</option>
              <option value={2000}>2s (Standard)</option>
              <option value={5000}>5s</option>
              <option value={0}>Paused</option>
            </select>
          </div>

          <div
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, color: "#64748b" }}
          >
            <span>Fetch Limit:</span>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                border: "1px solid #cbd5e1",
                fontSize: 12,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
              <option value={1000}>1,000</option>
            </select>
          </div>

          <button
            onClick={fetchLedger}
            style={{
              background: "#f1f5f9",
              border: "1px solid #cbd5e1",
              color: "#334155",
              padding: "7px 12px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Trades High-Density Table */}
      <div
        style={{
          background: "#ffffff",
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          boxShadow: "0 4px 12px rgba(0,0,0,0.03)",
          overflow: "hidden",
        }}
      >
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr
                style={{
                  background: "#f8fafc",
                  color: "#64748b",
                  textAlign: "left",
                  borderBottom: "2px solid #e2e8f0",
                }}
              >
                <th style={{ padding: "12px 14px" }}>Trade ID / IST</th>
                <th style={{ padding: "12px 14px" }}>Agent</th>
                <th style={{ padding: "12px 14px" }}>Strategy</th>
                <th style={{ padding: "12px 14px" }}>Contract</th>
                <th style={{ padding: "12px 14px" }}>Direction</th>
                <th style={{ padding: "12px 14px" }}>Lots & Size</th>
                <th style={{ padding: "12px 14px" }}>Entry / Exit</th>
                <th style={{ padding: "12px 14px" }}>Turnover</th>
                <th style={{ padding: "12px 14px" }}>Charges</th>
                <th style={{ padding: "12px 14px" }}>Net Realized P&L</th>
                <th style={{ padding: "12px 14px" }}>Exit Reason</th>
                <th style={{ padding: "12px 14px" }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {loading && trades.length === 0 ? (
                <tr>
                  <td colSpan={12} style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>
                    Loading live Upstox trade records...
                  </td>
                </tr>
              ) : filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={12} style={{ padding: "40px", textAlign: "center", color: "#94a3b8" }}>
                    No trades match the selected criteria.
                  </td>
                </tr>
              ) : (
                filteredTrades.map((t) => {
                  const isExpanded = expandedTradeId === t.trade_id;
                  const isLong = t.direction === "LONG";
                  return (
                    <>
                      <tr
                        key={t.trade_id}
                        style={{
                          borderBottom: isExpanded ? "none" : "1px solid #f1f5f9",
                          background: isExpanded ? "#f8fafc" : "#ffffff",
                          transition: "background 0.15s ease",
                        }}
                      >
                        <td style={{ padding: "12px 14px", fontFamily: "monospace" }}>
                          <div style={{ fontWeight: 800, color: "#0f172a" }}>#{t.trade_id}</div>
                          <div style={{ fontSize: 10, color: "#64748b" }}>{t.ist_timestamp}</div>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <span
                            style={{
                              fontWeight: 800,
                              color: "#0f172a",
                              background: "#f1f5f9",
                              padding: "3px 8px",
                              borderRadius: 6,
                            }}
                          >
                            Agent {t.agent_name}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <div style={{ fontWeight: 800, color: "#0f172a" }}>{t.strategy_id}</div>
                          <div style={{ fontSize: 11, color: "#64748b" }}>{t.strategy_name}</div>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <span style={{ fontWeight: 800, color: "#1e293b", fontFamily: "monospace" }}>{t.symbol}</span>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <span
                            style={{
                              background: isLong ? "#dcfce7" : "#fee2e2",
                              color: isLong ? "#15803d" : "#b91c1c",
                              padding: "3px 8px",
                              borderRadius: 6,
                              fontWeight: 800,
                              fontSize: 11,
                            }}
                          >
                            {t.direction}
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontFamily: "monospace" }}>
                          <span style={{ fontWeight: 800, color: "#0284c7" }}>{t.lots} Lot</span>
                          <span style={{ fontSize: 11, color: "#64748b" }}>
                            {" "}
                            ({t.total_quantity} {t.lot_unit})
                          </span>
                        </td>
                        <td style={{ padding: "12px 14px", fontFamily: "monospace" }}>
                          <div>₹{t.entry_price.toFixed(1)}</div>
                          <div style={{ color: "#64748b", fontSize: 11 }}>₹{t.exit_price.toFixed(1)}</div>
                        </td>
                        <td style={{ padding: "12px 14px", fontFamily: "monospace" }}>
                          ₹{t.turnover.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                        </td>
                        <td style={{ padding: "12px 14px", fontFamily: "monospace", color: "#d97706" }}>
                          -₹{t.total_charges.toFixed(2)}
                        </td>
                        <td style={{ padding: "12px 14px", fontFamily: "monospace" }}>
                          <div
                            style={{
                              fontWeight: 900,
                              fontSize: 13,
                              color: t.net_pnl >= 0 ? "#16a34a" : "#dc2626",
                            }}
                          >
                            {t.net_pnl >= 0 ? "+" : ""}₹{t.net_pnl.toFixed(2)}
                          </div>
                          <div
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: t.net_pnl >= 0 ? "#15803d" : "#b91c1c",
                            }}
                          >
                            {t.net_roi_pct >= 0 ? "+" : ""}
                            {t.net_roi_pct.toFixed(2)}% ROI
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color:
                                t.exit_reason === "PROFIT_TARGET"
                                  ? "#15803d"
                                  : t.exit_reason === "STOP_LOSS"
                                    ? "#b91c1c"
                                    : "#64748b",
                            }}
                          >
                            {t.exit_reason}
                          </span>
                          <div style={{ fontSize: 10, color: "#94a3b8" }}>{t.duration_seconds}s hold</div>
                        </td>
                        <td style={{ padding: "12px 14px" }}>
                          <button
                            onClick={() => setExpandedTradeId(isExpanded ? null : t.trade_id)}
                            style={{
                              background: isExpanded ? "#0f172a" : "#f1f5f9",
                              color: isExpanded ? "#ffffff" : "#475569",
                              border: "none",
                              padding: "4px 8px",
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            {isExpanded ? "Close" : "Inspect"}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable Breakdown Drawer */}
                      {isExpanded && (
                        <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                          <td colSpan={12} style={{ padding: "16px 20px" }}>
                            <div
                              style={{
                                background: "#ffffff",
                                padding: "16px",
                                borderRadius: 12,
                                border: "1px solid #cbd5e1",
                                display: "grid",
                                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                                gap: 16,
                              }}
                            >
                              {/* Rationale & Source */}
                              <div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    color: "#64748b",
                                    fontWeight: 800,
                                    textTransform: "uppercase",
                                  }}
                                >
                                  Signal Hypothesis & Rationale
                                </div>
                                <div style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", marginTop: 4 }}>
                                  {t.hypothesis ||
                                    "Quantitative algorithmic state machine breakout triggered on live price tick."}
                                </div>
                                <div style={{ fontSize: 11, color: "#059669", marginTop: 6 }}>
                                  Feed: {t.upstox_feed_source}
                                </div>
                              </div>

                              {/* Upstox Transaction Fees Breakdown */}
                              <div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    color: "#64748b",
                                    fontWeight: 800,
                                    textTransform: "uppercase",
                                  }}
                                >
                                  Upstox Statutory Fee Breakdown
                                </div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    marginTop: 4,
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 3,
                                    fontFamily: "monospace",
                                  }}
                                >
                                  <div>Brokerage (Upstox): ₹{t.brokerage.toFixed(2)}</div>
                                  <div>STT / CTT: ₹{t.stt_ctt.toFixed(2)}</div>
                                  <div>Exchange Charges: ₹{t.exchange_charges.toFixed(2)}</div>
                                  <div>GST (18%): ₹{t.gst.toFixed(2)}</div>
                                  <div>SEBI Turnover Fees: ₹{t.sebi_charges.toFixed(2)}</div>
                                  <div>Stamp Duty: ₹{t.stamp_duty.toFixed(2)}</div>
                                  <div style={{ fontWeight: 800, color: "#b45309" }}>
                                    Total Friction: ₹{t.total_charges.toFixed(2)}
                                  </div>
                                </div>
                              </div>

                              {/* Capital & Margin Audit */}
                              <div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    color: "#64748b",
                                    fontWeight: 800,
                                    textTransform: "uppercase",
                                  }}
                                >
                                  Capital & Margin Audit
                                </div>
                                <div
                                  style={{
                                    fontSize: 11,
                                    marginTop: 4,
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 3,
                                    fontFamily: "monospace",
                                  }}
                                >
                                  <div>Margin Utilized: ₹{t.margin_utilized.toLocaleString("en-IN")}</div>
                                  <div>Agent Max Principal: ₹{t.agent_max_principal.toLocaleString("en-IN")}</div>
                                  <div>Gross P&L: ₹{t.gross_pnl.toFixed(2)}</div>
                                  <div style={{ fontWeight: 800, color: t.net_pnl >= 0 ? "#16a34a" : "#dc2626" }}>
                                    Net Realized P&L: {t.net_pnl >= 0 ? "+" : ""}₹{t.net_pnl.toFixed(2)}
                                  </div>
                                  <div>
                                    Post-Trade Balance: ₹
                                    {t.post_trade_balance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
