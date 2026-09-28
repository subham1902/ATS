"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

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

export default function TokensPage() {
  const [autonomy, setAutonomy] = useState<AutonomyData | null>(null);
  const [_loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/v1/governance/autonomy")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setAutonomy(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

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
            <span style={{ fontSize: 24 }}>🔑</span>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
              Autonomy & Token Vault (Safe View)
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
              A2_PAPER SAFE VIEW
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#94a3b8" }}>
            Cryptographic single-use trade authorization tokens. Safe view guarantees zero private nonces or secret
            hashes are exposed.
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

      {/* Current Operational State Card */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.75)",
          border: "1px solid rgba(16, 185, 129, 0.4)",
          borderRadius: 14,
          padding: 24,
          marginBottom: 24,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.37)",
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
            <div style={{ fontSize: 11, fontWeight: 700, color: "#34d399" }}>CURRENT ACTIVE AUTONOMY LEVEL</div>
            <h2 style={{ fontSize: 22, fontWeight: 800, margin: "4px 0 8px", color: "#f8fafc" }}>
              A2_PAPER: Autonomous Paper Trading
            </h2>
            <p style={{ margin: 0, fontSize: 13, color: "#cbd5e1", maxWidth: 700, lineHeight: 1.5 }}>
              {autonomy?.description ||
                "Autonomous agent decision execution exclusively inside PaperBroker. Automated 4-gate candidate evaluation and dynamic margin management. Live money operations are strictly rejected at the architectural level."}
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <div
              style={{
                padding: "8px 14px",
                background: "rgba(30, 41, 59, 0.8)",
                borderRadius: 8,
                border: "1px solid rgba(56, 189, 248, 0.3)",
              }}
            >
              <div style={{ fontSize: 10, color: "#94a3b8" }}>HARDWARE LOCK</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#38bdf8" }}>LIVE_MONEY = False</div>
            </div>
            <div
              style={{
                padding: "8px 14px",
                background: "rgba(30, 41, 59, 0.8)",
                borderRadius: 8,
                border: "1px solid rgba(139, 92, 246, 0.3)",
              }}
            >
              <div style={{ fontSize: 10, color: "#94a3b8" }}>EXECUTION TARGET</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: "#a78bfa" }}>PaperBroker Only</div>
            </div>
          </div>
        </div>

        {/* Security Invariants Checklist */}
        <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid rgba(51, 65, 85, 0.4)" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#cbd5e1", marginBottom: 10 }}>
            ENFORCED ARCHITECTURAL GUARDS:
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
                <span style={{ color: "#34d399" }}>✓</span>
                <span>{g}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Active Tokens Table */}
      <div
        style={{
          background: "rgba(15, 23, 42, 0.75)",
          border: "1px solid rgba(51, 65, 85, 0.5)",
          borderRadius: 14,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: "#f8fafc" }}>
            Active Autonomy Tokens (Safe View)
          </h3>
          <span style={{ fontSize: 11, color: "#94a3b8" }}>Single-use cryptographic execution tokens (TTL 60s)</span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {(autonomy?.active_tokens || []).map((t, idx) => (
            <div
              key={idx}
              style={{
                padding: 14,
                borderRadius: 8,
                background: "rgba(30, 41, 59, 0.5)",
                border: "1px solid rgba(71, 85, 105, 0.4)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 13, fontWeight: 800, color: "#818cf8", fontFamily: "monospace" }}>
                    {t.token_id}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: "rgba(99, 102, 241, 0.2)",
                      color: "#a5b4fc",
                    }}
                  >
                    Scope: {t.scope}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>
                  Bound Candidate: <strong style={{ color: "#cbd5e1" }}>{t.candidate_id}</strong> · Nonces protected ·
                  Safe View Active
                </div>
              </div>

              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "3px 10px",
                  borderRadius: 4,
                  background: t.status === "CONSUMED" ? "rgba(16, 185, 129, 0.2)" : "rgba(56, 189, 248, 0.2)",
                  color: t.status === "CONSUMED" ? "#34d399" : "#38bdf8",
                }}
              >
                {t.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
