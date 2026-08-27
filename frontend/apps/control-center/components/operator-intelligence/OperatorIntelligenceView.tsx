"use client";

import React, { useState } from "react";
import type {
  OperatorIntelligenceSnapshot,
  FixtureScenarioId,
  ProvenanceType,
} from "@ats/api-client";
import { Badge } from "@ats/ui";
import { SurvivalTelemetry } from "./SurvivalTelemetry";
import { OpportunityScanner } from "./OpportunityScanner";
import { EdgeLedger } from "./EdgeLedger";
import { AgentAccountability } from "./AgentAccountability";
import { OpportunityMap } from "./OpportunityMap";
import { EvidenceDrilldown } from "./EvidenceDrilldown";
import { FIXTURE_SCENARIOS, getFixtureScenario } from "./fixtures";

export interface OperatorIntelligenceViewProps {
  initialSnapshot?: OperatorIntelligenceSnapshot;
  isLiveAvailable?: boolean;
}

export function OperatorIntelligenceView({
  initialSnapshot,
  isLiveAvailable = false,
}: OperatorIntelligenceViewProps) {
  const [selectedScenarioId, setSelectedScenarioId] = useState<FixtureScenarioId>("NORMAL_QUIET_MARKET");
  const [provenanceMode, setProvenanceMode] = useState<ProvenanceType>(
    initialSnapshot?.provenance ?? "FIXTURE"
  );
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  // Active snapshot: live snapshot if mode is LIVE and available, else selected fixture
  const snapshot: OperatorIntelligenceSnapshot =
    provenanceMode === "LIVE" && initialSnapshot && initialSnapshot.provenance === "LIVE"
      ? initialSnapshot
      : getFixtureScenario(selectedScenarioId);

  const scenarioList: Array<{ id: FixtureScenarioId; label: string }> = [
    { id: "NORMAL_QUIET_MARKET", label: "1. NORMAL Quiet Market Baseline" },
    { id: "HIGH_CONVICTION_CANDIDATE", label: "2. HIGH_CONVICTION Candidate (Bull Call Spread)" },
    { id: "HYPOTHETICAL_CONVEX_CANDIDATE", label: "3. Hypothetical CONVEX Candidate (OTM Tail)" },
    { id: "HYPOTHETICAL_RARE_EVENT_CANDIDATE", label: "4. Hypothetical RARE_EVENT Candidate (Gap Trigger)" },
    { id: "SAFE_DUE_DRAWDOWN", label: "5. SAFE Due Drawdown (-1.8% Auto De-escalation)" },
    { id: "HALTED", label: "6. SYSTEM HALTED (Emergency Circuit Breaker)" },
    { id: "HARNESS_UNAVAILABLE", label: "7. Harness Unavailable (Defensive Fallback)" },
    { id: "STALE_AGENT_ADVISORY", label: "8. Stale Agent Advisory (Lagging TTL)" },
    { id: "CANDIDATE_REJECTED_PORTFOLIO_BRAIN", label: "9. Candidate Rejected by Portfolio Brain (Capacity Limit)" },
    { id: "CANDIDATE_DENIED_A04", label: "10. Candidate Denied by A04 Kernel (Spread Exceeded)" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 1200 }}>
      {/* Top Header & Provenance Controller Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          background: "#ffffff",
          padding: "12px 18px",
          borderRadius: 10,
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
            Operator Intelligence & Observability
          </h1>
          <Badge tone={snapshot.provenance === "LIVE" ? "success" : "neutral"}>
            {snapshot.provenance === "LIVE"
              ? "● LIVE TELEMETRY"
              : `FIXTURE: ${snapshot.scenario_id ?? "SYNTHETIC"}`}
          </Badge>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "#6b7280",
              border: "1px solid #e5e7eb",
              padding: "2px 8px",
              borderRadius: 999,
            }}
          >
            ADVISORY_ONLY · NO REAL ORDERS
          </span>
        </div>

        {/* Provenance & Fixture Scenario Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {isLiveAvailable && (
            <button
              type="button"
              onClick={() => setProvenanceMode("LIVE")}
              style={{
                fontSize: 12,
                fontWeight: 600,
                padding: "5px 10px",
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                background: provenanceMode === "LIVE" ? "#0f172a" : "#ffffff",
                color: provenanceMode === "LIVE" ? "#ffffff" : "#334155",
                cursor: "pointer",
              }}
            >
              Live Feed
            </button>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              Scenario Replay:
            </span>
            <select
              aria-label="Scenario Replay Selector"
              value={selectedScenarioId}
              onChange={(e) => {
                setProvenanceMode("FIXTURE");
                setSelectedScenarioId(e.target.value as FixtureScenarioId);
              }}
              style={{
                fontSize: 12,
                padding: "5px 10px",
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                background: "#ffffff",
                fontWeight: 500,
                color: "#0f172a",
                cursor: "pointer",
              }}
            >
              {scenarioList.map((sc) => (
                <option key={sc.id} value={sc.id}>
                  {sc.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Scenario Context Banner */}
      {snapshot.scenario_description && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 8,
            padding: "8px 14px",
            fontSize: 12,
            color: "#1e40af",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            <strong>Active Scenario Context:</strong> {snapshot.scenario_description}
          </span>
          <span style={{ fontSize: 11, color: "#3b82f6" }}>
            Synthetic validation fixture (OI7)
          </span>
        </div>
      )}

      {/* Section 1: ATS Survival & Autonomy Telemetry (OI3) */}
      <SurvivalTelemetry telemetry={snapshot.survival} />

      {/* Section 2: Opportunity Scanner (OI1) & Market Opportunity Map (OI5) */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <OpportunityScanner
          scanner={snapshot.scanner}
          onSelectCandidate={(id) => setSelectedCandidateId(id)}
          selectedCandidateId={selectedCandidateId}
        />

        <OpportunityMap
          points={snapshot.opportunity_map}
          onSelectCandidate={(id) => setSelectedCandidateId(id)}
          selectedCandidateId={selectedCandidateId}
        />
      </div>

      {/* Section 3: Edge Ledger (OI2 & OI2.1) */}
      <EdgeLedger
        ledger={snapshot.edge_ledger}
        onSelectCandidate={(id) => setSelectedCandidateId(id)}
        selectedCandidateId={selectedCandidateId}
      />

      {/* Section 4: Agent Accountability & Timeline (OI4 & OI4.1) */}
      <AgentAccountability
        agents={snapshot.agents}
        timeline={snapshot.timeline}
        onSelectEvidence={(ref) => setSelectedCandidateId(ref)}
      />

      {/* Section 5: Machine Evidence Lineage Drill-Down (OI6) */}
      <EvidenceDrilldown
        candidateId={selectedCandidateId}
        lineageMap={snapshot.evidence_lineage}
        onSelectCandidate={(id) => setSelectedCandidateId(id)}
      />
    </div>
  );
}
