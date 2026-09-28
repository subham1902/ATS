"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

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

export default function AdvisoriesPage() {
  const [advisories, setAdvisories] = useState<SupervisorAdvisory[]>([]);
  const [filter, setFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/v1/governance/advisories")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setAdvisories(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  const handleAcknowledge = async (id: string) => {
    try {
      const res = await fetch(`/v1/governance/advisories/${id}/acknowledge`, { method: "POST" });
      if (res.ok) {
        setAdvisories((prev) =>
          prev.map((a) => (a.advisory_id === id ? { ...a, acknowledged: true } : a))
        );
      }
    } catch (e) {
      console.error("Failed to acknowledge", e);
    }
  };

  const filtered = advisories.filter((a) => {
    if (filter === "ALL") return true;
    return a.severity === filter;
  });

  const criticalCount = advisories.filter((a) => a.severity === "CRITICAL").length;
  const warningCount = advisories.filter((a) => a.severity === "WARNING").length;
  const infoCount = advisories.filter((a) => a.severity === "INFO").length;

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
            <span style={{ fontSize: 24 }}>💡</span>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
              Supervisor Advisories & Risk Guidance
            </h1>
            <span
              style={{
                fontSize: 11,
                padding: "3px 10px",
                borderRadius: 20,
                fontWeight: 700,
                background: "rgba(56, 189, 248, 0.15)",
                color: "#38bdf8",
                border: "1px solid rgba(56, 189, 248, 0.3)",
              }}
            >
              REAL-TIME RISK COPILOT
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#94a3b8" }}>
            Autonomous supervisor notices highlighting market regime transitions, capital allocation stress, and portfolio correlations.
          </p>
        </div>

        <Link
          href="/governance?tab=workflow"
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 700,
            background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
            color: "#ffffff",
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          🧭 Open Governance Workflow →
        </Link>
      </div>

      {/* Severity Filter Bar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { id: "ALL", label: `All Advisories (${advisories.length})`, color: "#818cf8" },
          { id: "CRITICAL", label: `Critical (${criticalCount})`, color: "#f87171" },
          { id: "WARNING", label: `Warnings (${warningCount})`, color: "#fbbf24" },
          { id: "INFO", label: `Informational (${infoCount})`, color: "#38bdf8" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              background: filter === tab.id ? "rgba(99, 102, 241, 0.3)" : "rgba(30, 41, 59, 0.5)",
              color: filter === tab.id ? "#ffffff" : "#94a3b8",
              borderBottom: filter === tab.id ? `2px solid ${tab.color}` : "none",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Advisories Feed */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {filtered.map((a) => (
          <div
            key={a.advisory_id}
            style={{
              padding: 20,
              borderRadius: 12,
              background:
                a.severity === "CRITICAL"
                  ? "rgba(239, 68, 68, 0.1)"
                  : a.severity === "WARNING"
                  ? "rgba(245, 158, 11, 0.08)"
                  : "rgba(15, 23, 42, 0.75)",
              border: `1px solid ${
                a.severity === "CRITICAL"
                  ? "rgba(239, 68, 68, 0.35)"
                  : a.severity === "WARNING"
                  ? "rgba(245, 158, 11, 0.3)"
                  : "rgba(51, 65, 85, 0.5)"
              }`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 800,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background:
                        a.severity === "CRITICAL"
                          ? "#ef4444"
                          : a.severity === "WARNING"
                          ? "#f59e0b"
                          : "#0284c7",
                      color: "#ffffff",
                    }}
                  >
                    {a.severity}
                  </span>
                  <span style={{ fontSize: 12, color: "#818cf8", fontWeight: 700 }}>{a.category}</span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>· {a.advisory_id}</span>
                </div>

                <h2 style={{ fontSize: 16, fontWeight: 800, color: "#f8fafc", margin: "8px 0 6px" }}>
                  {a.title}
                </h2>

                <p style={{ margin: "0 0 10px", fontSize: 13, color: "#cbd5e1", lineHeight: 1.5 }}>
                  {a.message}
                </p>

                <div
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "rgba(30, 41, 59, 0.6)",
                    fontSize: 12,
                    color: "#38bdf8",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span style={{ fontWeight: 700 }}>Operator Guidance:</span>
                  <span>{a.recommendation}</span>
                </div>

                {a.evidence_refs.length > 0 && (
                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                    {a.evidence_refs.map((ref, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: 10,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: "rgba(51, 65, 85, 0.6)",
                          color: "#94a3b8",
                          fontFamily: "monospace",
                        }}
                      >
                        Evidence: {ref}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <button
                onClick={() => handleAcknowledge(a.advisory_id)}
                disabled={a.acknowledged}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: a.acknowledged ? "default" : "pointer",
                  background: a.acknowledged ? "rgba(148, 163, 184, 0.2)" : "rgba(16, 185, 129, 0.2)",
                  color: a.acknowledged ? "#94a3b8" : "#34d399",
                  border: `1px solid ${a.acknowledged ? "rgba(148, 163, 184, 0.3)" : "rgba(16, 185, 129, 0.4)"}`,
                  whiteSpace: "nowrap",
                }}
              >
                {a.acknowledged ? "✓ Acknowledged" : "Acknowledge Notice"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
