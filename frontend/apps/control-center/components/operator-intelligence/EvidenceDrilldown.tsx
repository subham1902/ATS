"use client";

import React, { useState } from "react";
import type {
  EvidenceLineageNode,
  EvidenceNodeType,
} from "@ats/api-client";
import { Card, Badge } from "@ats/ui";
import { formatTimeIST } from "../../lib/formatTime";

export interface EvidenceDrilldownProps {
  candidateId?: string | null;
  lineageMap?: Record<string, EvidenceLineageNode[]> | null;
  onSelectCandidate?: (id: string) => void;
}

export function EvidenceDrilldown({
  candidateId,
  lineageMap,
  onSelectCandidate,
}: EvidenceDrilldownProps) {
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [manualInputId, setManualInputId] = useState<string>("");

  const activeCandidateId = candidateId || (lineageMap ? Object.keys(lineageMap)[0] : null);
  const lineage = activeCandidateId && lineageMap ? lineageMap[activeCandidateId] ?? [] : [];

  if (!lineageMap || Object.keys(lineageMap).length === 0) {
    return (
      <Card title="Machine Evidence Lineage Drill-Down">
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
          No machine evidence lineage available · select or enter a candidate ID
        </div>
      </Card>
    );
  }

  const renderNodeStatusBadge = (status: EvidenceLineageNode["status"]) => {
    switch (status) {
      case "VERIFIED":
        return <Badge tone="success">VERIFIED</Badge>;
      case "PENDING":
        return <Badge tone="warn">PENDING</Badge>;
      case "REJECTED":
        return <Badge tone="danger">REJECTED</Badge>;
      case "BYPASSED":
        return <Badge tone="neutral">BYPASSED</Badge>;
      case "UNKNOWN":
      default:
        return <Badge tone="unknown">UNKNOWN</Badge>;
    }
  };

  const getNodeIcon = (type: EvidenceNodeType) => {
    switch (type) {
      case "MarketSnapshot":
        return "📊";
      case "FeatureBundle":
        return "📐";
      case "RegimeEvidence":
        return "🧭";
      case "EnsembleForecast":
        return "🔮";
      case "CalibratedOutcomeDistribution":
        return "🎯";
      case "MarketThesis":
        return "💡";
      case "OpportunityCandidate":
        return "⚡";
      case "PortfolioAllocationDecision":
        return "⚖️";
      case "RiskDecision":
        return "🛡️";
      case "A04Decision":
        return "🔒";
      case "Position":
        return "📈";
      case "TradeReview":
        return "📝";
      case "HistoricalAnalogueEvidence":
        return "📚";
      case "ConvexityEvidence":
        return "📈";
      default:
        return "📄";
    }
  };

  return (
    <Card title="Machine Evidence Lineage Drill-Down (OI6)">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Candidate Selector Bar */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 10,
            background: "#f8fafc",
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid #e2e8f0",
            fontSize: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 600, color: "#475569" }}>Active Candidate:</span>
            <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#0f172a" }}>
              {activeCandidateId ?? "NONE SELECTED"}
            </span>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="text"
              placeholder="Candidate UUID / Hash..."
              value={manualInputId}
              onChange={(e) => setManualInputId(e.target.value)}
              style={{ fontSize: 12, padding: "3px 8px", borderRadius: 4, border: "1px solid #cbd5e1", minWidth: 180 }}
            />
            <button
              type="button"
              onClick={() => {
                if (manualInputId.trim()) {
                  onSelectCandidate?.(manualInputId.trim());
                }
              }}
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: "3px 8px",
                background: "#0f172a",
                color: "#ffffff",
                border: "none",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Lookup Lineage
            </button>
          </div>
        </div>

        {/* Lineage Flow Sequence */}
        {lineage.length === 0 ? (
          <div style={{ padding: 20, textAlign: "center", color: "#94a3b8", fontStyle: "italic" }}>
            No evidence lineage trace found for candidate ID {activeCandidateId}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.05em", color: "#64748b", textTransform: "uppercase" }}>
              Lineage DAG Trace ({lineage.length} stages)
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {lineage.map((node, idx) => {
                const isSelected = activeNodeId === node.node_id;
                const isLast = idx === lineage.length - 1;

                return (
                  <React.Fragment key={node.node_id}>
                    <div
                      onClick={() => setActiveNodeId(isSelected ? null : node.node_id)}
                      style={{
                        background: isSelected ? "#f0fdf4" : "#ffffff",
                        border: `1px solid ${isSelected ? "#16a34a" : "#e2e8f0"}`,
                        borderRadius: 8,
                        padding: "10px 14px",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                        boxShadow: isSelected ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                      }}
                    >
                      {/* Node Header */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 16 }}>{getNodeIcon(node.node_type)}</span>
                          <span style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>
                            {node.node_type}
                          </span>
                          <span style={{ fontFamily: "monospace", fontSize: 11, color: "#64748b" }}>
                            #{node.hash.slice(0, 10)}
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 11, color: "#94a3b8" }}>
                            {formatTimeIST(node.timestamp)}
                          </span>
                          {renderNodeStatusBadge(node.status)}
                        </div>
                      </div>

                      {/* Summary */}
                      <div style={{ fontSize: 12, color: "#334155" }}>
                        {node.summary}
                      </div>

                      {/* Extracted Metrics / Hash Inspector */}
                      {isSelected && Object.keys(node.metrics).length > 0 && (
                        <div
                          style={{
                            marginTop: 6,
                            padding: "8px 12px",
                            background: "#f8fafc",
                            borderRadius: 6,
                            border: "1px solid #e2e8f0",
                            fontSize: 11,
                          }}
                        >
                          <div style={{ fontWeight: 600, color: "#475569", marginBottom: 4 }}>
                            Extracted Verified Parameters:
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "4px 12px" }}>
                            {Object.entries(node.metrics).map(([k, v]) => (
                              <div key={k} style={{ color: "#64748b" }}>
                                <span style={{ color: "#334155", fontWeight: 500 }}>{k}:</span>{" "}
                                <strong style={{ color: "#0f172a" }}>
                                  {v !== null ? String(v) : "UNKNOWN"}
                                </strong>
                              </div>
                            ))}
                          </div>
                          <div style={{ marginTop: 6, fontSize: 10, fontFamily: "monospace", color: "#94a3b8" }}>
                            Full Hash: {node.hash} · Node ID: {node.node_id}
                          </div>
                        </div>
                      )}
                    </div>

                    {!isLast && (
                      <div style={{ display: "flex", justifyContent: "center", margin: "-4px 0" }}>
                        <span style={{ color: "#94a3b8", fontSize: 14 }}>&darr;</span>
                      </div>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
