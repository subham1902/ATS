"use client";
import React, { useEffect, useState } from "react";
import { Card } from "@ats/ui";

interface StrategyItem {
  strategy_id: string;
  model_name: string;
  source_file: string;
  source_hash: string;
  source_format: string;
  authority: string;
  timeframes: string[];
  required_features: string[];
  compatibility_state: string;
  status: string;
  blockers: string[];
}

interface ShadowMetricItem {
  strategy_id: string;
  model_name: string;
  is_native: boolean;
  signals_generated: number;
  valid_signals: number;
  invalid_signals: number;
  long_count: number;
  short_count: number;
  open_trajectories: number;
  resolved_trajectories: number;
  support_count: number;
  support_target: number;
  wins: number;
  losses: number;
  gross_pnl: string;
  costs: string;
  net_pnl: string;
  cost_stress_base: string;
  cost_stress_1_5x: string;
  cost_stress_2_0x: string;
  win_rate: number;
  profit_factor: number;
  expectancy: string;
  max_drawdown: string;
  holding_time_seconds: number;
  latency_ms: number;
  regime: string;
  regime_classification: string;
  data_freshness_sec: number;
  jev_state: string;
  jev_incremental_benefit: boolean;
  sample_status: string;
  status: string;
}

interface OverviewData {
  total_files: number;
  admitted_count: number;
  quarantined_count: number;
  strategies: StrategyItem[];
  tournament: ShadowMetricItem[];
}

export default function ImportedStrategiesPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [includeNative, setIncludeNative] = useState(true);
  const [_error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const url = `http://localhost:8100/v1/strategies/imported?include_native=${includeNative}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async () => {
    try {
      setScanning(true);
      const res = await fetch(`http://localhost:8100/v1/strategies/imported/scan?include_native=${includeNative}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 5000);
    return () => clearInterval(timer);
  }, [includeNative]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 1400 }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>
              Multi-Session Prospective Shadow Validation (ATS-BIN-03)
            </h1>
            <span
              style={{
                fontSize: 12,
                fontWeight: 800,
                padding: "3px 8px",
                borderRadius: 4,
                background: "#dc2626",
                color: "#ffffff",
              }}
            >
              SHADOW ONLY
            </span>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
            Operating 9 frozen imported strategy versions and native research candidates (S17) against genuine live
            GOLDM data over MarketDataFabric.
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={includeNative} onChange={(e) => setIncludeNative(e.target.checked)} />
            Include Native Candidates (S17)
          </label>
          <button
            type="button"
            onClick={handleScan}
            disabled={scanning}
            style={{
              padding: "8px 16px",
              background: scanning ? "#9ca3af" : "#2563eb",
              color: "white",
              border: "none",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: scanning ? "not-allowed" : "pointer",
            }}
          >
            {scanning ? "Scanning Local BIN Folder..." : "Re-Scan Local BIN Folder"}
          </button>
        </div>
      </div>

      {/* Safety Invariant Badges */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#fef3c7",
            color: "#92400e",
          }}
        >
          AUTHORITY: RESEARCH_ONLY
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#dcfce7",
            color: "#166534",
          }}
        >
          LIVE_MONEY: FALSE
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#dcfce7",
            color: "#166534",
          }}
        >
          REAL ORDERS: 0
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#dbeafe",
            color: "#1e40af",
          }}
        >
          A04: ACTIVE
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#ede9fe",
            color: "#5b21b6",
          }}
        >
          PAPERBROKER: ISOLATED (NO ORDERS)
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 999,
            background: "#fee2e2",
            color: "#991b1b",
          }}
        >
          PROSPECTIVE SUPPORT TARGET: 20 TRADES
        </span>
      </div>

      {/* Unified Tournament Table */}
      <Card title="Unified Live Prospective Tournament Leaderboard (SHADOW ONLY)">
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", background: "#f9fafb" }}>
                <th style={{ padding: "8px 10px" }}>Origin</th>
                <th style={{ padding: "8px 10px" }}>ID</th>
                <th style={{ padding: "8px 10px" }}>Model</th>
                <th style={{ padding: "8px 10px" }}>Signals</th>
                <th style={{ padding: "8px 10px" }}>Support (X/20)</th>
                <th style={{ padding: "8px 10px" }}>W / L</th>
                <th style={{ padding: "8px 10px" }}>Gross P&L</th>
                <th style={{ padding: "8px 10px" }}>Costs (Base / 1.5x / 2.0x)</th>
                <th style={{ padding: "8px 10px" }}>Net P&L</th>
                <th style={{ padding: "8px 10px" }}>PF</th>
                <th style={{ padding: "8px 10px" }}>Regime</th>
                <th style={{ padding: "8px 10px" }}>Jev State</th>
                <th style={{ padding: "8px 10px" }}>Evidence</th>
                <th style={{ padding: "8px 10px" }}>Data Health</th>
                <th style={{ padding: "8px 10px" }}>Live Status</th>
              </tr>
            </thead>
            <tbody>
              {data && data.tournament.length > 0 ? (
                data.tournament.map((t) => (
                  <tr key={t.strategy_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: t.is_native ? "#f0fdf4" : "#eff6ff",
                          color: t.is_native ? "#166534" : "#1e40af",
                        }}
                      >
                        {t.is_native ? "NATIVE" : "IMPORTED"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace", fontWeight: 700 }}>{t.strategy_id}</td>
                    <td style={{ padding: "8px 10px", fontWeight: 600 }}>{t.model_name}</td>
                    <td style={{ padding: "8px 10px" }}>{t.signals_generated}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontWeight: 700, fontFamily: "monospace" }}>
                          {t.support_count || t.resolved_trajectories}/20
                        </span>
                        <div
                          style={{ width: 40, height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden" }}
                        >
                          <div
                            style={{
                              width: `${Math.min(100, ((t.support_count || t.resolved_trajectories) / 20) * 100)}%`,
                              height: "100%",
                              background: (t.support_count || t.resolved_trajectories) >= 20 ? "#16a34a" : "#3b82f6",
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      {t.wins} / {t.losses}
                    </td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace" }}>
                      ₹{parseFloat(t.gross_pnl || "0").toFixed(2)}
                    </td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace", fontSize: 11, color: "#4b5563" }}>
                      ₹{parseFloat(t.cost_stress_base || t.costs || "0").toFixed(0)} / ₹
                      {parseFloat(t.cost_stress_1_5x || "0").toFixed(0)} / ₹
                      {parseFloat(t.cost_stress_2_0x || "0").toFixed(0)}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        fontFamily: "monospace",
                        fontWeight: 700,
                        color: parseFloat(t.net_pnl || "0") >= 0 ? "#16a34a" : "#dc2626",
                      }}
                    >
                      ₹{parseFloat(t.net_pnl || "0").toFixed(2)}
                    </td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace" }}>
                      {(t.profit_factor || 0).toFixed(2)}
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: "#f3f4f6",
                          color: "#374151",
                        }}
                      >
                        {t.regime || "UNKNOWN"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: "#fdf4ff",
                          color: "#86198f",
                        }}
                      >
                        {t.jev_state || "RESEARCH_ONLY"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: t.sample_status === "VALIDATED" ? "#dcfce7" : "#fee2e2",
                          color: t.sample_status === "VALIDATED" ? "#166534" : "#991b1b",
                        }}
                      >
                        {t.sample_status || "INSUFFICIENT_EVIDENCE"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace", fontSize: 11 }}>
                      <span style={{ color: t.data_freshness_sec > 5 ? "#dc2626" : "#16a34a" }}>
                        {t.data_freshness_sec}s
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background:
                            t.status === "SHADOW_RUNNING"
                              ? "#dcfce7"
                              : t.status === "REVIEW_REQUIRED"
                                ? "#fef08a"
                                : "#e0e7ff",
                          color:
                            t.status === "SHADOW_RUNNING"
                              ? "#15803d"
                              : t.status === "REVIEW_REQUIRED"
                                ? "#854d0e"
                                : "#3730a3",
                        }}
                      >
                        {t.status || "SHADOW_READY"}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={14} style={{ padding: "16px 12px", textAlign: "center", color: "#6b7280" }}>
                    {loading ? "Loading prospective tournament data..." : "No tournament candidates available."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Strategy Inventory & Cryptographic Freeze Matrix */}
      <Card title="Frozen Imported Strategy Registry (ATS_BIN_02_FROZEN_STRATEGIES.json / ATS_BIN_03_SESSION_LEDGER.csv)">
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", background: "#f9fafb" }}>
                <th style={{ padding: "8px 10px" }}>Strategy ID</th>
                <th style={{ padding: "8px 10px" }}>Source File</th>
                <th style={{ padding: "8px 10px" }}>SHA-256 (Source)</th>
                <th style={{ padding: "8px 10px" }}>Format</th>
                <th style={{ padding: "8px 10px" }}>Timeframes</th>
                <th style={{ padding: "8px 10px" }}>Required Data</th>
                <th style={{ padding: "8px 10px" }}>Compatibility</th>
                <th style={{ padding: "8px 10px" }}>Mutation Policy</th>
              </tr>
            </thead>
            <tbody>
              {data && data.strategies.length > 0 ? (
                data.strategies.map((s) => (
                  <tr key={s.strategy_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace", fontWeight: 700 }}>{s.strategy_id}</td>
                    <td style={{ padding: "8px 10px", fontWeight: 600 }}>{s.source_file}</td>
                    <td style={{ padding: "8px 10px", fontFamily: "monospace", fontSize: 11, color: "#6b7280" }}>
                      {s.source_hash.slice(0, 12)}...
                    </td>
                    <td style={{ padding: "8px 10px" }}>{s.source_format}</td>
                    <td style={{ padding: "8px 10px" }}>{s.timeframes.join(", ")}</td>
                    <td style={{ padding: "8px 10px" }}>{s.required_features.join(", ")}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 4,
                          background: "#dcfce7",
                          color: "#166534",
                        }}
                      >
                        {s.compatibility_state}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px" }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: "#fef3c7",
                          color: "#92400e",
                        }}
                      >
                        FROZEN_RULE_IMMUTABLE
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} style={{ padding: "16px 12px", textAlign: "center", color: "#6b7280" }}>
                    {loading ? "Loading frozen registry..." : "No strategies registered."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
