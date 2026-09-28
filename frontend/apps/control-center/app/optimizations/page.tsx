"use client";

import { useEffect, useState } from "react";
import { Card } from "@ats/ui";

interface OptimizationState {
  status: string;
  active_trials: number;
  total_trials: number;
  best_results: Record<
    string,
    {
      value: number;
      params: Record<string, any>;
      updated_at: string;
    }
  >;
  recent_trials: Array<{
    strategy: string;
    trial_id: string;
    params: Record<string, any>;
    score: number;
    timestamp: string;
  }>;
}

export default function LiveOptimizationsPage() {
  const [optState, setOptState] = useState<OptimizationState | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch("/v1/optimization/status");
        if (res.ok) {
          const data = await res.json();
          setOptState(data);
        }
      } catch (e) {
        console.error("Failed to fetch opt state", e);
      }
    };

    fetchState();
    const intv = setInterval(fetchState, 2000);
    return () => clearInterval(intv);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 14,
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.04)",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 32, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em" }}>
            Live Optimizations
          </h1>
          <div style={{ fontSize: 16, color: "#475569", marginTop: 6, fontWeight: 500 }}>
            Continuous Bayesian parameter search & validation across active strategies
          </div>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            padding: "5px 12px",
            borderRadius: 8,
            background: optState?.status === "RUNNING" ? "#f0fdf4" : "#f1f5f9",
            border: `1px solid ${optState?.status === "RUNNING" ? "#bbf7d0" : "#cbd5e1"}`,
            fontSize: 11,
            fontWeight: 600,
            color: optState?.status === "RUNNING" ? "#15803d" : "#64748b",
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: optState?.status === "RUNNING" ? "#22c55e" : "#94a3b8",
              boxShadow: optState?.status === "RUNNING" ? "0 0 8px rgba(34,197,94,0.6)" : "none",
              animation: optState?.status === "RUNNING" ? "pulse-dot 2s infinite ease-in-out" : "none",
            }}
          />
          <span style={{ fontSize: 14 }}>Worker: {optState?.status || "UNKNOWN"}</span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        <Card title="Global Worker Stats">
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 16, color: "#475569", fontWeight: 600 }}>Total Trials Evaluated</span>
              <span style={{ fontSize: 32, fontWeight: 800, color: "#0f172a" }}>{optState?.total_trials || 0}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 16, color: "#475569", fontWeight: 600 }}>Currently Active Searches</span>
              <span style={{ fontSize: 28, fontWeight: 700, color: "#0284c7" }}>{optState?.active_trials || 0}</span>
            </div>
          </div>
        </Card>

        {optState &&
          Object.entries(optState.best_results).map(([strat, result]) => (
            <Card key={strat} title={`Best Known: ${strat}`}>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontSize: 14, color: "#64748b", fontWeight: 600 }}>Peak Score</span>
                  <span style={{ fontSize: 28, fontWeight: 800, color: "#16a34a" }}>{result.value.toFixed(2)}</span>
                </div>
                <div
                  style={{
                    background: "#f8fafc",
                    padding: "12px",
                    borderRadius: 8,
                    fontSize: 13,
                    fontFamily: "monospace",
                    color: "#334155",
                    border: "1px solid #e2e8f0",
                  }}
                >
                  {JSON.stringify(result.params, null, 2)}
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8", textAlign: "right", fontWeight: 500 }}>
                  Last improved: {new Date(result.updated_at).toLocaleTimeString()}
                </div>
              </div>
            </Card>
          ))}
      </div>

      <Card title="Live Evolution Feed">
        {optState && optState.recent_trials.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #e2e8f0", color: "#64748b" }}>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>Time</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>Strategy</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>Trial ID</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>Score</th>
                  <th style={{ padding: "12px 8px", fontWeight: 700 }}>Parameters Executed</th>
                </tr>
              </thead>
              <tbody>
                {optState.recent_trials.map((t, idx) => (
                  <tr
                    key={idx}
                    style={{ borderBottom: "1px solid #f1f5f9", transition: "background 0.2s", cursor: "default" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <td style={{ padding: "10px 8px", color: "#94a3b8" }}>
                      {new Date(t.timestamp).toLocaleTimeString()}
                    </td>
                    <td style={{ padding: "10px 8px", fontWeight: 700, color: "#334155" }}>{t.strategy}</td>
                    <td style={{ padding: "10px 8px", fontFamily: "monospace", color: "#0284c7" }}>{t.trial_id}</td>
                    <td
                      style={{
                        padding: "10px 8px",
                        fontWeight: 800,
                        fontSize: 15,
                        color: t.score > 0 ? "#16a34a" : "#dc2626",
                      }}
                    >
                      {t.score.toFixed(2)}
                    </td>
                    <td style={{ padding: "10px 8px", fontFamily: "monospace", fontSize: 13, color: "#475569" }}>
                      {JSON.stringify(t.params)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: "30px", textAlign: "center", color: "#94a3b8", fontSize: 16, fontWeight: 500 }}>
            Waiting for first optimization trials to complete...
          </div>
        )}
      </Card>
    </div>
  );
}
