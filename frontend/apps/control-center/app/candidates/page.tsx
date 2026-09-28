"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

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

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<GovernedCandidate[]>([]);
  const [filter, setFilter] = useState<string>("ALL");
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/v1/governance/candidates")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setCandidates(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  const filtered = candidates.filter((c) => {
    const matchesFilter =
      filter === "ALL" ||
      (filter === "EXECUTED" && (c.status === "EXECUTED" || c.status === "APPROVED")) ||
      (filter === "DENIED_A04" && c.status === "A04_DENIED") ||
      (filter === "DENIED_CAPITAL" && c.status === "CAPITAL_DENIED") ||
      (filter === "DENIED_RISK" && (c.status === "EXECUTION_DENIED" || c.status === "RISK_DENIED"));

    const matchesSearch =
      search === "" ||
      c.candidate_id.toLowerCase().includes(search.toLowerCase()) ||
      c.strategy_id.toLowerCase().includes(search.toLowerCase()) ||
      c.instrument.toLowerCase().includes(search.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  const executedCount = candidates.filter((c) => c.status === "EXECUTED" || c.status === "APPROVED").length;
  const a04DeniedCount = candidates.filter((c) => c.status === "A04_DENIED").length;
  const capitalDeniedCount = candidates.filter((c) => c.status === "CAPITAL_DENIED").length;
  const riskDeniedCount = candidates.filter((c) => c.status === "EXECUTION_DENIED" || c.status === "RISK_DENIED").length;

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
      {/* Header */}
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 24 }}>🎯</span>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
              Opportunity Candidates Funnel
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
              MULTI-AGENT PIPELINE
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#94a3b8" }}>
            Real-time trade proposals emitted by alpha strategy agents and evaluated sequentially across all 4 governance gates.
          </p>
        </div>

        <Link
          href="/governance?tab=workflow"
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 700,
            background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
            color: "#ffffff",
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          🧪 Test Candidate in Simulator →
        </Link>
      </div>

      {/* KPI Funnel Row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 14,
          marginBottom: 24,
        }}
      >
        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.75)", border: "1px solid rgba(51, 65, 85, 0.5)", borderRadius: 10 }}>
          <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>TOTAL PROPOSALS</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#f8fafc", marginTop: 4 }}>{candidates.length}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>From S17, S02, S04</div>
        </div>

        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.75)", border: "1px solid rgba(16, 185, 129, 0.4)", borderRadius: 10 }}>
          <div style={{ fontSize: 11, color: "#34d399", fontWeight: 600 }}>APPROVED / EXECUTED</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#34d399", marginTop: 4 }}>{executedCount}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Passed all 4 gates</div>
        </div>

        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.75)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 10 }}>
          <div style={{ fontSize: 11, color: "#f87171", fontWeight: 600 }}>GATE 1 A04 DENIED</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#f87171", marginTop: 4 }}>{a04DeniedCount}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>P(win) &lt; 0.52 or low edge</div>
        </div>

        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.75)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: 10 }}>
          <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 600 }}>GATE 2 CAPITAL DENIED</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#fbbf24", marginTop: 4 }}>{capitalDeniedCount}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Margin &gt; available</div>
        </div>

        <div style={{ padding: 16, background: "rgba(15, 23, 42, 0.75)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 10 }}>
          <div style={{ fontSize: 11, color: "#f87171", fontWeight: 600 }}>GATE 3 RISK DENIED</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#f87171", marginTop: 4 }}>{riskDeniedCount}</div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>Max loss or concurrency limit</div>
        </div>
      </div>

      {/* Filter Bar & Search */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[
            { id: "ALL", label: `All (${candidates.length})` },
            { id: "EXECUTED", label: `Approved / Executed (${executedCount})` },
            { id: "DENIED_A04", label: `Gate 1 A04 (${a04DeniedCount})` },
            { id: "DENIED_CAPITAL", label: `Gate 2 Capital (${capitalDeniedCount})` },
            { id: "DENIED_RISK", label: `Gate 3 Risk (${riskDeniedCount})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id)}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                background: filter === tab.id ? "rgba(99, 102, 241, 0.3)" : "rgba(30, 41, 59, 0.5)",
                color: filter === tab.id ? "#ffffff" : "#94a3b8",
                borderBottom: filter === tab.id ? "2px solid #818cf8" : "none",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Filter candidate, strategy, instrument..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "8px 12px",
            borderRadius: 6,
            background: "rgba(30, 41, 59, 0.8)",
            border: "1px solid rgba(71, 85, 105, 0.6)",
            color: "#f8fafc",
            fontSize: 12,
            width: 260,
          }}
        />
      </div>

      {/* Candidates List */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {filtered.map((c) => (
          <div
            key={c.candidate_id}
            style={{
              padding: 16,
              borderRadius: 10,
              background:
                c.status === "EXECUTED" || c.status === "APPROVED"
                  ? "rgba(16, 185, 129, 0.08)"
                  : "rgba(15, 23, 42, 0.75)",
              border: `1px solid ${
                c.status === "EXECUTED" || c.status === "APPROVED"
                  ? "rgba(16, 185, 129, 0.3)"
                  : "rgba(51, 65, 85, 0.5)"
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
                <span style={{ fontSize: 14, fontWeight: 800, color: "#f8fafc" }}>{c.candidate_id}</span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: c.direction === "BUY" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)",
                    color: c.direction === "BUY" ? "#34d399" : "#f87171",
                  }}
                >
                  {c.direction} {c.instrument}
                </span>
                <span style={{ fontSize: 12, color: "#818cf8", fontWeight: 600 }}>{c.strategy_id}</span>
              </div>

              <div style={{ display: "flex", gap: 20, fontSize: 12, color: "#cbd5e1", marginTop: 6 }}>
                <span>Entry: <strong>₹{c.entry_price.toLocaleString()}</strong></span>
                <span>Expected Edge: <strong>{c.expected_edge_r}R</strong></span>
                <span>P(win): <strong>{c.calibrated_prob}</strong></span>
              </div>

              {c.rejection_reason && (
                <div style={{ fontSize: 11, color: "#f87171", marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <span>✗</span>
                  <span>{c.rejection_reason}</span>
                </div>
              )}
            </div>

            <span
              style={{
                fontSize: 11,
                fontWeight: 800,
                padding: "5px 12px",
                borderRadius: 6,
                background:
                  c.status === "EXECUTED"
                    ? "rgba(16, 185, 129, 0.2)"
                    : c.status === "APPROVED"
                    ? "rgba(99, 102, 241, 0.2)"
                    : "rgba(239, 68, 68, 0.2)",
                color:
                  c.status === "EXECUTED"
                    ? "#34d399"
                    : c.status === "APPROVED"
                    ? "#a5b4fc"
                    : "#f87171",
              }}
            >
              {c.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
