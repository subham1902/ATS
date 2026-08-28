"use client";

import React from "react";

export interface EvidenceRecorderHealthProps {
  health: "HEALTHY" | "DEGRADED" | "FAILED";
  eventCount: number;
  predictions: number;
  rejections: number;
  candidates: number;
  portfolioDecisions: number;
  a04Decisions: number;
  orders: number;
  fills: number;
  lastWrite?: string;
  dbPersistence: string;
  mirrorAvailable: boolean;
  integrityStatus: string;
}

export function EvidenceRecorderHealth({
  health,
  eventCount,
  predictions,
  rejections,
  candidates,
  portfolioDecisions,
  a04Decisions,
  orders,
  fills,
  lastWrite,
  dbPersistence,
  mirrorAvailable,
  integrityStatus,
}: EvidenceRecorderHealthProps) {
  const tone = health === "HEALTHY" ? "success" : health === "DEGRADED" ? "warn" : "danger";
  const badgeColor = tone === "success" ? "#166534" : tone === "warn" ? "#92400e" : "#991b1b";
  const bgColor = tone === "success" ? "#f0fdf4" : tone === "warn" ? "#fffbeb" : "#fef2f2";
  const borderColor = tone === "success" ? "#86efac" : tone === "warn" ? "#fde68a" : "#fca5a5";

  return (
    <div
      style={{
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        padding: 16,
        background: bgColor,
        marginBottom: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.06em", color: badgeColor }}>
            EVIDENCE RECORDER
          </div>
          <div style={{ fontSize: 16, fontWeight: 800, color: badgeColor, marginTop: 4 }}>
            {health}
          </div>
        </div>
        <div style={{ textAlign: "right", fontSize: 11, color: badgeColor }}>
          <div>Integrity: <strong>{integrityStatus}</strong></div>
          <div>DB: <strong>{dbPersistence}</strong></div>
          <div>Mirror: <strong>{mirrorAvailable ? "AVAILABLE" : "NOT INITIALIZED"}</strong></div>
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))",
          gap: 8,
          marginTop: 10,
        }}
      >
        <Metric label="Events" value={eventCount} />
        <Metric label="Predictions" value={predictions} />
        <Metric label="Rejections" value={rejections} />
        <Metric label="Candidates" value={candidates} />
        <Metric label="Portfolio" value={portfolioDecisions} />
        <Metric label="A04" value={a04Decisions} />
        <Metric label="Orders" value={orders} />
        <Metric label="Fills" value={fills} />
      </div>
      {lastWrite && (
        <div style={{ fontSize: 11, color: badgeColor, marginTop: 6, opacity: 0.8 }}>
          Last event: {lastWrite}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        borderRadius: 6,
        padding: "6px 8px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 10, color: "#64748b", fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{value}</div>
    </div>
  );
}
