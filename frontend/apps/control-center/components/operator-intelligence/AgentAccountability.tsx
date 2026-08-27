"use client";

import React, { useState } from "react";
import type {
  AgentAccountabilityEntry,
  TimelineEvent,
  AgentStatus,
  GovernorResult,
} from "@ats/api-client";
import { Card, Badge } from "@ats/ui";
import { formatTimeIST } from "../../lib/formatTime";

export interface AgentAccountabilityProps {
  agents: AgentAccountabilityEntry[] | null;
  timeline?: TimelineEvent[] | null;
  onSelectEvidence?: (evidenceRef: string) => void;
}

export function AgentAccountability({
  agents,
  timeline,
  onSelectEvidence,
}: AgentAccountabilityProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  if (!agents || agents.length === 0) {
    return (
      <Card title="Agent Accountability & Advisory Telemetry">
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
          No agent accountability telemetry available · intelligence harness offline or unattached
        </div>
      </Card>
    );
  }

  const renderStatusBadge = (status: AgentStatus) => {
    switch (status) {
      case "ACTIVE":
        return <Badge tone="success">ACTIVE</Badge>;
      case "IDLE":
        return <Badge tone="neutral">IDLE</Badge>;
      case "STALE":
        return <Badge tone="warn">STALE ADVISORY</Badge>;
      case "DEGRADED":
        return <Badge tone="warn">DEGRADED</Badge>;
      case "OFFLINE":
        return <Badge tone="danger">OFFLINE</Badge>;
      case "UNKNOWN":
      default:
        return <Badge tone="unknown">UNKNOWN</Badge>;
    }
  };

  const renderGovernorBadge = (res: GovernorResult) => {
    switch (res) {
      case "APPROVED":
        return <Badge tone="success">APPROVED</Badge>;
      case "REJECTED":
        return <Badge tone="danger">REJECTED</Badge>;
      case "DEFERRED":
        return <Badge tone="warn">DEFERRED</Badge>;
      case "GOVERNOR_BLOCKED":
        return <Badge tone="danger">BLOCKED BY GOVERNOR</Badge>;
      case "NO_CHANGE":
      default:
        return <Badge tone="neutral">NO CHANGE</Badge>;
    }
  };

  return (
    <Card title="Agent Accountability & Governance Timeline">
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {/* Top Invariant Notice */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "#f1f5f9",
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid #cbd5e1",
            fontSize: 12,
            flexWrap: "wrap",
            gap: 8,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 700, color: "#1e293b" }}>HARNESS AUTHORITY:</span>
            <Badge tone="warn">ADVISORY ONLY</Badge>
            <span style={{ color: "#64748b", fontSize: 11 }}>
              Agents propose hypotheses; deterministic ATS Governor & A04 authorize all orders.
            </span>
          </div>
          <div style={{ fontSize: 11, color: "#475569" }}>
            Monitored Agents: <strong>{agents.length}</strong>
          </div>
        </div>

        {/* Agent Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 12,
          }}
        >
          {agents.map((agent) => {
            const isSelected = selectedAgentId === agent.agent_id;
            return (
              <div
                key={agent.agent_id}
                onClick={() => setSelectedAgentId(isSelected ? null : agent.agent_id)}
                style={{
                  background: isSelected ? "#f8fafc" : "#ffffff",
                  border: `1px solid ${isSelected ? "#0f172a" : "#e2e8f0"}`,
                  borderRadius: 8,
                  padding: 12,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  cursor: "pointer",
                  boxShadow: isSelected ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                }}
              >
                {/* Agent Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 6 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: "#0f172a" }}>
                      {agent.role}
                    </div>
                    <div style={{ fontFamily: "monospace", fontSize: 10, color: "#64748b" }}>
                      {agent.agent_id}
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                    {renderStatusBadge(agent.status)}
                    {agent.is_stale && (
                      <span style={{ fontSize: 10, color: "#b45309", fontWeight: 700 }}>
                        ⚠️ STALE
                      </span>
                    )}
                  </div>
                </div>

                {/* Wake Reason & Recommendation */}
                <div style={{ background: "#f8fafc", padding: "6px 8px", borderRadius: 6, fontSize: 11 }}>
                  <div style={{ color: "#64748b" }}>
                    Last Trigger: <strong>{agent.wake_reason ?? "UNKNOWN"}</strong>
                  </div>
                  <div style={{ marginTop: 2, color: "#0f172a", fontWeight: 600 }}>
                    Recommendation:{" "}
                    <span style={{ color: agent.recommendation ? "#1d4ed8" : "#94a3b8" }}>
                      {agent.recommendation ?? "NONE / UNKNOWN"}
                    </span>
                  </div>
                </div>

                {/* Telemetry Details */}
                <div style={{ fontSize: 11, color: "#64748b", display: "flex", flexDirection: "column", gap: 2 }}>
                  <div>
                    Last Wake:{" "}
                    <strong>
                      {formatTimeIST(agent.last_wake)}
                    </strong>
                  </div>
                  <div>
                    Data Cutoff:{" "}
                    <strong>
                      {formatTimeIST(agent.data_cutoff)}
                    </strong>
                  </div>
                  <div>
                    Authority:{" "}
                    <span style={{ fontWeight: 700, color: "#b45309" }}>{agent.authority}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                    <span>Latency: {agent.latency_ms !== null ? `${agent.latency_ms}ms` : "—"}</span>
                    <span>Tools: {agent.tool_calls_count}</span>
                  </div>
                  {agent.provider_model && (
                    <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2, fontFamily: "monospace" }}>
                      Model: {agent.provider_model}
                    </div>
                  )}
                </div>

                {/* Evidence References */}
                {agent.evidence_refs.length > 0 && (
                  <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: 6, marginTop: 4 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: "#64748b", marginBottom: 4 }}>
                      Evidence Lineage Refs ({agent.evidence_refs.length}):
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {agent.evidence_refs.map((ref) => (
                        <button
                          key={ref}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectEvidence?.(ref);
                          }}
                          style={{
                            fontFamily: "monospace",
                            fontSize: 10,
                            padding: "2px 6px",
                            borderRadius: 4,
                            border: "1px solid #cbd5e1",
                            background: "#ffffff",
                            cursor: "pointer",
                          }}
                        >
                          {ref}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* OI4.1 Chronological Agent Activity Timeline */}
        {timeline && timeline.length > 0 && (
          <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 14 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "#475569",
                marginBottom: 10,
              }}
            >
              Chronological Agent & Governor Activity Timeline
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {timeline.map((event) => (
                <div
                  key={event.event_id}
                  style={{
                    background: "#ffffff",
                    border: "1px solid #e2e8f0",
                    borderRadius: 6,
                    padding: "8px 12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontFamily: "monospace", fontSize: 11, color: "#64748b" }}>
                        {formatTimeIST(event.timestamp)}
                      </span>
                      <strong style={{ color: "#0f172a" }}>{event.material_event}</strong>
                      <span style={{ color: "#94a3b8" }}>&rarr;</span>
                      <span style={{ color: "#1e40af", fontWeight: 600 }}>{event.agent_wake}</span>
                    </div>
                    <div>{renderGovernorBadge(event.governor_result)}</div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "#475569" }}>
                    <div>
                      Recommendation: <strong>{event.recommendation}</strong>
                      {event.proposal_id && (
                        <span style={{ marginLeft: 6, fontFamily: "monospace", color: "#64748b" }}>
                          (Proposal: {event.proposal_id})
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 10, color: "#64748b", fontStyle: "italic" }}>
                      {event.authority_note}
                    </span>
                  </div>

                  {event.evidence_queried.length > 0 && (
                    <div style={{ fontSize: 10, color: "#94a3b8" }}>
                      Evidence queried: {event.evidence_queried.join(", ")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
