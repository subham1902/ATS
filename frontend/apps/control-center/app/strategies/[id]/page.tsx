"use client";

import React, { useEffect, useState } from "react";
import { Card } from "@ats/ui";
import { useParams } from "next/navigation";

export default function StrategyDetailPage() {
  const { id } = useParams();
  const [report, setReport] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("OVERVIEW");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`http://127.0.0.1:8000/v1/strategies/registry/${id}/report`);
        if (res.ok) {
          setReport(await res.json());
        }
      } catch (err) {
        console.error("Failed to load strategy details", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <div style={{ padding: 24 }}>Loading strategy details...</div>;
  if (!report) return <div style={{ padding: 24, color: "red" }}>Strategy {id} not found in Canonical Registry.</div>;

  const tabs = ["OVERVIEW", "LIVE STATE", "SIGNALS", "TRADES", "RUNS", "PERFORMANCE", "EVIDENCE"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1200 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>{report.strategy.name}</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
          ID: {report.strategy.strategy_id} | Class: {report.strategy.classification} | Tier:{" "}
          {report.strategy.evidence_tier}
        </p>
      </div>

      <div style={{ display: "flex", gap: 8, borderBottom: "1px solid #e5e7eb", paddingBottom: 8 }}>
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            style={{
              padding: "6px 12px",
              background: activeTab === t ? "#eef2ff" : "transparent",
              color: activeTab === t ? "#4f46e5" : "#6b7280",
              fontWeight: activeTab === t ? 700 : 500,
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {activeTab === "OVERVIEW" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
          <Card title="Strategy Profile">
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Family</span>
                <span style={{ fontWeight: 600 }}>{report.strategy.family || "N/A"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Badge</span>
                <span style={{ fontWeight: 600 }}>{report.strategy.badge}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Hypothesis</span>
                <span style={{ fontWeight: 600 }}>{report.strategy.hypothesis || "Not specified"}</span>
              </div>
            </div>
          </Card>

          <Card title="Lifetime Metrics">
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Total Trades</span>
                <span style={{ fontWeight: 600, fontFamily: "monospace" }}>{report.strategy.total_trades}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Total Net P&L</span>
                <span
                  style={{
                    fontWeight: 600,
                    fontFamily: "monospace",
                    color: report.strategy.total_net_pnl >= 0 ? "#16a34a" : "#dc2626",
                  }}
                >
                  ₹{report.strategy.total_net_pnl}
                </span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === "RUNS" && (
        <Card title="Historical Evidence Runs">
          <div style={{ fontSize: 13 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>
                  <th style={{ padding: 8 }}>Context</th>
                  <th style={{ padding: 8 }}>Timeframe</th>
                  <th style={{ padding: 8 }}>Trades</th>
                  <th style={{ padding: 8 }}>Net P&L</th>
                  <th style={{ padding: 8 }}>Max DD</th>
                  <th style={{ padding: 8 }}>Measured At</th>
                </tr>
              </thead>
              <tbody>
                {report.strategy.performance_records.map((run: any, idx: number) => (
                  <tr key={idx} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: 8 }}>
                      <span style={{ padding: "2px 6px", background: "#f3f4f6", borderRadius: 4, fontWeight: 600 }}>
                        {run.execution_context}
                      </span>
                    </td>
                    <td style={{ padding: 8 }}>{run.timeframe}</td>
                    <td style={{ padding: 8, fontFamily: "monospace" }}>{run.trades_count}</td>
                    <td
                      style={{
                        padding: 8,
                        fontFamily: "monospace",
                        color: run.net_pnl >= 0 ? "#16a34a" : "#dc2626",
                        fontWeight: 700,
                      }}
                    >
                      ₹{run.net_pnl}
                    </td>
                    <td style={{ padding: 8, fontFamily: "monospace", color: "#dc2626" }}>₹{run.max_drawdown}</td>
                    <td style={{ padding: 8, color: "#9ca3af" }}>{run.measured_at}</td>
                  </tr>
                ))}
                {report.strategy.performance_records.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 16, textAlign: "center", color: "#9ca3af" }}>
                      No verified historical runs recorded in the evidence ledger.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {(activeTab === "TRADES" || activeTab === "SIGNALS") && (
        <Card title={`${activeTab} History`}>
          <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
            {activeTab} detailed drill-down is available for verified shadow and live-paper sessions only.
          </div>
        </Card>
      )}

      {(activeTab === "LIVE STATE" || activeTab === "PERFORMANCE" || activeTab === "EVIDENCE") && (
        <Card title={`${activeTab} Overview`}>
          <div style={{ padding: 24, textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
            Displaying subset of {activeTab} attributes linked to latest model evaluation...
          </div>
        </Card>
      )}
    </div>
  );
}
