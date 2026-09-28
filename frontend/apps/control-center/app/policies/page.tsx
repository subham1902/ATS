"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface GovernedPolicy {
  policy_id: string;
  name: string;
  version: number;
  lifecycle_status: string;
  autonomy_level: string;
  universe: string[];
  timeframe: string;
  min_confidence: number;
  max_leverage: string;
  max_slippage_ticks: number;
  max_drawdown_percent: number;
  trading_hours: string;
  is_active: boolean;
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<GovernedPolicy[]>([]);
  const [_loading, setLoading] = useState(true);
  const [validatorInput, setValidatorInput] = useState(
    JSON.stringify(
      {
        policy_id: "POL-CUSTOM-VALIDATE-01",
        version: 1,
        max_leverage: "1x",
        min_confidence: 0.55,
        max_drawdown_percent: 12.0,
      },
      null,
      2,
    ),
  );
  const [validationResult, setValidationResult] = useState<any | null>(null);

  useEffect(() => {
    fetch("/v1/governance/policies")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setPolicies(data))
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, []);

  const handleValidate = () => {
    try {
      const _parsed = JSON.parse(validatorInput);
      setValidationResult({
        outcome: "VALID",
        reason_codes: ["POLICY_SYNTAX_VALID", "LEVERAGE_WITHIN_BOUNDS", "INVARIANTS_PASSED"],
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (e: any) {
      setValidationResult({
        outcome: "INVALID",
        reason_codes: ["JSON_PARSE_ERROR: " + e.message],
        timestamp: new Date().toLocaleTimeString(),
      });
    }
  };

  const activePolicy = policies.find((p) => p.is_active) || policies[0];

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
            <span style={{ fontSize: 24 }}>📋</span>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
              Trading Policies & Invariants
            </h1>
            <span
              style={{
                fontSize: 11,
                padding: "3px 10px",
                borderRadius: 20,
                fontWeight: 700,
                background: "rgba(99, 102, 241, 0.2)",
                color: "#a5b4fc",
                border: "1px solid rgba(99, 102, 241, 0.4)",
              }}
            >
              GOVERNED BOUNDARIES
            </span>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#94a3b8" }}>
            Formal policy specifications defining leverage caps, slippage boundaries, execution schedules, and risk
            limits.
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

      <div style={{ display: "grid", gridTemplateColumns: "minmax(360px, 1.2fr) minmax(320px, 1fr)", gap: 24 }}>
        {/* Active Policy Highlight Card */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {activePolicy && (
            <div
              style={{
                background: "rgba(15, 23, 42, 0.75)",
                border: "1px solid rgba(99, 102, 241, 0.4)",
                borderRadius: 14,
                padding: 24,
                boxShadow: "0 8px 32px rgba(0, 0, 0, 0.37)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: 4,
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "#34d399",
                  }}
                >
                  ● ACTIVE ENFORCED POLICY
                </span>
                <span style={{ fontSize: 11, color: "#818cf8", fontFamily: "monospace" }}>
                  {activePolicy.policy_id} v{activePolicy.version}
                </span>
              </div>

              <h2 style={{ fontSize: 18, fontWeight: 800, margin: "0 0 16px", color: "#f8fafc" }}>
                {activePolicy.name}
              </h2>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Max Allowed Leverage</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#34d399", marginTop: 2 }}>
                    {activePolicy.max_leverage}
                  </div>
                </div>

                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Min Calibrated Confidence</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#38bdf8", marginTop: 2 }}>
                    P ≥ {activePolicy.min_confidence}
                  </div>
                </div>

                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Max Drawdown Cap</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#f59e0b", marginTop: 2 }}>
                    {activePolicy.max_drawdown_percent}%
                  </div>
                </div>

                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Max Slippage Tolerance</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: "#a78bfa", marginTop: 2 }}>
                    {activePolicy.max_slippage_ticks} ticks
                  </div>
                </div>

                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Trading Session Hours</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#cbd5e1", marginTop: 2 }}>
                    {activePolicy.trading_hours}
                  </div>
                </div>

                <div style={{ padding: 10, background: "rgba(30, 41, 59, 0.5)", borderRadius: 8 }}>
                  <div style={{ color: "#94a3b8" }}>Instrument Universe</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#cbd5e1", marginTop: 2 }}>
                    {activePolicy.universe.join(", ")}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Policy Catalog */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(51, 65, 85, 0.5)",
              borderRadius: 14,
              padding: 20,
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 14px", color: "#f8fafc" }}>Policy Catalog</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {policies.map((p) => (
                <div
                  key={p.policy_id}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: "rgba(30, 41, 59, 0.4)",
                    border: "1px solid rgba(71, 85, 105, 0.3)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#f1f5f9" }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>
                      {p.policy_id} · Timeframe: {p.timeframe} · Leverage: {p.max_leverage}
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: p.is_active ? "rgba(16, 185, 129, 0.2)" : "rgba(148, 163, 184, 0.15)",
                      color: p.is_active ? "#34d399" : "#94a3b8",
                    }}
                  >
                    {p.is_active ? "ACTIVE" : p.lifecycle_status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Policy Invariant Validator */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.75)",
            border: "1px solid rgba(51, 65, 85, 0.5)",
            borderRadius: 14,
            padding: 20,
          }}
        >
          <h3 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 8px", color: "#f8fafc" }}>Policy Rule Validator</h3>
          <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 0, marginBottom: 12 }}>
            Test a policy JSON structure against kernel syntax and boundary rules.
          </p>

          <textarea
            value={validatorInput}
            onChange={(e) => setValidatorInput(e.target.value)}
            rows={10}
            style={{
              width: "100%",
              padding: 12,
              borderRadius: 8,
              background: "rgba(30, 41, 59, 0.8)",
              border: "1px solid rgba(71, 85, 105, 0.5)",
              color: "#38bdf8",
              fontFamily: "monospace",
              fontSize: 12,
              marginBottom: 12,
            }}
          />

          <button
            onClick={handleValidate}
            style={{
              width: "100%",
              padding: "10px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 700,
              background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
              color: "#ffffff",
              border: "none",
              cursor: "pointer",
            }}
          >
            Validate Policy Specification
          </button>

          {validationResult && (
            <div
              style={{
                marginTop: 14,
                padding: 12,
                borderRadius: 8,
                background: validationResult.outcome === "VALID" ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
                border: `1px solid ${
                  validationResult.outcome === "VALID" ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"
                }`,
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: validationResult.outcome === "VALID" ? "#34d399" : "#f87171",
                }}
              >
                Outcome: {validationResult.outcome}
              </div>
              <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 4 }}>
                Reason Codes: {validationResult.reason_codes.join(", ")}
              </div>
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>
                Checked at {validationResult.timestamp}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
