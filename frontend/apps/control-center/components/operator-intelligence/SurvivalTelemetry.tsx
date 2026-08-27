"use client";

import React from "react";
import type {
  SurvivalTelemetryReadModel,
  OperatorSurvivalState,
  RuntimeStatusReadModel,
  SystemReadModel,
} from "@ats/api-client";
import { Card, Badge } from "@ats/ui";

export interface SurvivalTelemetryProps {
  telemetry: SurvivalTelemetryReadModel | null;
}

/**
 * Deterministic helper to resolve OperatorSurvivalState from ATS Runtime & System models.
 * Invariant: UNKNOWN is never mapped to healthy (NORMAL).
 */
export function resolveSurvivalState(
  runtime?: RuntimeStatusReadModel | null,
  system?: SystemReadModel | null
): OperatorSurvivalState {
  if (!runtime && !system) return "UNKNOWN";

  if (runtime?.halted || system?.halted || runtime?.trading_mode?.effective === "HALTED") {
    return "HALTED";
  }

  if (runtime?.session?.must_flatten || runtime?.loss_state === "HALTED") {
    return "HALTED";
  }

  if (
    runtime?.loss_state === "COOLDOWN" ||
    system?.loss_state === "COOLDOWN" ||
    runtime?.paused_new_entries
  ) {
    return "COOLDOWN";
  }

  if (
    runtime?.session?.can_reduce &&
    !runtime?.session?.can_enter &&
    !runtime?.paused_new_entries
  ) {
    return "EXIT_ONLY";
  }

  if (
    runtime?.trading_mode?.effective === "SAFE" ||
    runtime?.loss_state === "CAUTION" ||
    system?.loss_state === "CAUTION" ||
    !runtime?.feed_healthy ||
    !runtime?.broker_healthy ||
    system?.system_state === "DEGRADED" ||
    system?.reconciliation_active
  ) {
    return "SAFE";
  }

  if (
    runtime?.trading_mode?.effective === "NORMAL" &&
    runtime?.feed_healthy &&
    runtime?.broker_healthy &&
    system?.system_state === "READY" &&
    !runtime?.halted
  ) {
    return "NORMAL";
  }

  if (
    runtime?.trading_mode?.effective === "AGGRESSIVE" &&
    runtime?.feed_healthy &&
    runtime?.broker_healthy &&
    system?.system_state === "READY" &&
    !runtime?.halted
  ) {
    return "NORMAL";
  }

  return "UNKNOWN";
}

export function SurvivalTelemetry({ telemetry }: SurvivalTelemetryProps) {
  if (!telemetry) {
    return (
      <Card title="ATS Survival & Autonomy Telemetry">
        <div
          role="status"
          style={{
            padding: 24,
            textAlign: "center",
            color: "#6b7280",
            fontSize: 13,
            background: "#f9fafb",
            borderRadius: 8,
            border: "1px dashed #d1d5db",
          }}
        >
          No survival telemetry available · state unknown · not healthy
        </div>
      </Card>
    );
  }

  const {
    effective_survival_state,
    user_selected_mode,
    effective_mode,
    reason_codes,
    session_equity,
    hwm,
    drawdown_fraction,
    available_risk,
    open_positions,
    new_entry_permission,
    reduction_permission,
    feed_healthy,
    broker_healthy,
    reconciliation_active,
    last_state_at,
  } = telemetry;

  // Visual tones and descriptions for survival states
  const getSurvivalStyle = (state: OperatorSurvivalState) => {
    switch (state) {
      case "NORMAL":
        return {
          bg: "#f0fdf4",
          border: "#86efac",
          text: "#166534",
          badgeTone: "success" as const,
          label: "NORMAL · Unrestricted Bounded Execution",
        };
      case "CAUTION":
        return {
          bg: "#fffbeb",
          border: "#fde68a",
          text: "#92400e",
          badgeTone: "warn" as const,
          label: "CAUTION · Calibration / Feed Latency Elevated",
        };
      case "SAFE":
        return {
          bg: "#fefce8",
          border: "#fef08a",
          text: "#854d0e",
          badgeTone: "warn" as const,
          label: "SAFE · Tightened Risk Envelopes & Single Position Max",
        };
      case "COOLDOWN":
        return {
          bg: "#fff7ed",
          border: "#fed7aa",
          text: "#9a3412",
          badgeTone: "warn" as const,
          label: "COOLDOWN · Post-Loss Pause / Settle Period",
        };
      case "EXIT_ONLY":
        return {
          bg: "#fef2f2",
          border: "#fecaca",
          text: "#991b1b",
          badgeTone: "danger" as const,
          label: "EXIT ONLY · New Entries Prohibited · Managing Existing Risk",
        };
      case "HALTED":
        return {
          bg: "#450a0a",
          border: "#dc2626",
          text: "#ffffff",
          badgeTone: "danger" as const,
          label: "SYSTEM HALTED · All Trading Blocked · Emergency Protocol",
        };
      case "UNKNOWN":
      default:
        return {
          bg: "#f3f4f6",
          border: "#9ca3af",
          text: "#374151",
          badgeTone: "unknown" as const,
          label: "UNKNOWN · System State Unverified (No Risk Permitted)",
        };
    }
  };

  const style = getSurvivalStyle(effective_survival_state);
  const drawdownNum = drawdown_fraction !== null ? parseFloat(drawdown_fraction) : null;
  const drawdownPercent = drawdownNum !== null ? (drawdownNum * 100).toFixed(2) : "UNKNOWN";

  return (
    <Card title="ATS Survival & Autonomy Telemetry">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Effective Survival State Hero Banner */}
        <div
          style={{
            background: style.bg,
            border: `2px solid ${style.border}`,
            borderRadius: 8,
            padding: "12px 16px",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: style.text }}>
              EFFECTIVE SURVIVAL STATE
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: style.text }}>
              {style.label}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Badge tone={style.badgeTone}>{effective_survival_state}</Badge>
            <span style={{ fontSize: 11, color: style.text }}>
              As of: {last_state_at ? new Date(last_state_at).toLocaleTimeString() : "UNKNOWN"}
            </span>
          </div>
        </div>

        {/* Mode Comparison & Reason Codes */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
          }}
        >
          {/* Mode Escalation/De-escalation State */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 14px",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b" }}>Trading Mode Resolution</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: 13 }}>
              <span>User: <strong>{user_selected_mode}</strong></span>
              <span style={{ color: "#94a3b8" }}>&rarr;</span>
              <span>Effective: <strong>{effective_mode}</strong></span>
            </div>
            {effective_mode !== user_selected_mode && (
              <div style={{ fontSize: 11, color: "#b45309", marginTop: 4 }}>
                ⚠️ De-escalated by deterministic governor
              </div>
            )}
          </div>

          {/* Reason Codes */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 14px",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b" }}>Active Reason Codes</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
              {reason_codes.length === 0 ? (
                <span style={{ fontSize: 12, color: "#166534", fontWeight: 500 }}>
                  NONE (Envelopes Healthy)
                </span>
              ) : (
                reason_codes.map((code) => (
                  <Badge key={code} tone="warn">
                    {code}
                  </Badge>
                ))
              )}
            </div>
          </div>

          {/* Permission Gates */}
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 14px",
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b" }}>Permission Gates</div>
            <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span>New Entries:</span>
                <Badge tone={new_entry_permission ? "success" : "danger"}>
                  {new_entry_permission ? "ALLOWED" : "PROHIBITED"}
                </Badge>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span>Reductions:</span>
                <Badge tone={reduction_permission ? "success" : "danger"}>
                  {reduction_permission ? "ALLOWED" : "PROHIBITED"}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        {/* Financial Risk & Capital Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 10,
          }}
        >
          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>Session Equity</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", marginTop: 2 }}>
              {session_equity ? `₹${parseFloat(session_equity).toLocaleString()}` : "UNKNOWN"}
            </div>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>Session Peak (HWM)</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", marginTop: 2 }}>
              {hwm ? `₹${parseFloat(hwm).toLocaleString()}` : "UNKNOWN"}
            </div>
          </div>

          <div
            style={{
              background: drawdownNum !== null && drawdownNum > 0.01 ? "#fef2f2" : "#f8fafc",
              border: `1px solid ${drawdownNum !== null && drawdownNum > 0.01 ? "#fecaca" : "#e2e8f0"}`,
              borderRadius: 8,
              padding: "10px 12px",
            }}
          >
            <div style={{ fontSize: 11, color: drawdownNum !== null && drawdownNum > 0.01 ? "#991b1b" : "#64748b" }}>
              Drawdown
            </div>
            <div
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: drawdownNum !== null && drawdownNum > 0.01 ? "#dc2626" : "#0f172a",
                marginTop: 2,
              }}
            >
              {drawdownPercent !== "UNKNOWN" ? `-${drawdownPercent}%` : "UNKNOWN"}
            </div>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>Available Risk</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", marginTop: 2 }}>
              {available_risk ? `₹${parseFloat(available_risk).toLocaleString()}` : "UNKNOWN"}
            </div>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>Open Positions</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", marginTop: 2 }}>
              {open_positions}
            </div>
          </div>

          <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: "#64748b" }}>Health & Feed</div>
            <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
              <Badge tone={feed_healthy ? "success" : "danger"}>
                {feed_healthy ? "Feed OK" : "Feed Stale"}
              </Badge>
              <Badge tone={broker_healthy ? "success" : "danger"}>
                {broker_healthy ? "Broker OK" : "Broker Down"}
              </Badge>
              {reconciliation_active && <Badge tone="warn">Reconciling</Badge>}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
