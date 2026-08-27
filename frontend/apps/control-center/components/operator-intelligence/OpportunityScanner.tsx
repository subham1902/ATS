"use client";

import React from "react";
import type { OpportunityScannerReadModel } from "@ats/api-client";
import { Card, Badge } from "@ats/ui";
import { formatTimeIST } from "../../lib/formatTime";

export interface OpportunityScannerProps {
  scanner: OpportunityScannerReadModel | null;
  onSelectCandidate?: (candidateId: string) => void;
  selectedCandidateId?: string | null;
}

export function OpportunityScanner({
  scanner,
  onSelectCandidate,
  selectedCandidateId,
}: OpportunityScannerProps) {
  if (!scanner) {
    return (
      <Card title="Opportunity Scanner">
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
          No scanner telemetry available · state unknown · not active
        </div>
      </Card>
    );
  }

  const { funnel, rejections, candidates_by_class, source_state, last_scan_at, data_cutoff, candidate_ids } = scanner;
  const totalRejected =
    rejections.liquidity +
    rejections.spread +
    rejections.calibration +
    rejections.negative_ev +
    rejections.portfolio_capacity +
    rejections.a04;
  const totalCandidates =
    candidates_by_class.standard +
    candidates_by_class.high_conviction +
    candidates_by_class.convex +
    candidates_by_class.rare_event;

  return (
    <Card title="Opportunity Scanner">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Top Status & Metadata Bar */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 10,
            padding: "8px 12px",
            background: "#f8fafc",
            borderRadius: 6,
            border: "1px solid #e2e8f0",
            fontSize: 12,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600, color: "#475569" }}>Source:</span>
            <Badge
              tone={
                source_state === "LIVE"
                  ? "success"
                  : source_state === "REPLAY"
                  ? "neutral"
                  : source_state === "FIXTURE"
                  ? "neutral"
                  : source_state === "STALE"
                  ? "warn"
                  : "unknown"
              }
            >
              {source_state}
            </Badge>
            {source_state === "STALE" && (
              <span style={{ color: "#b45309", fontWeight: 600 }}>⚠️ Scan telemetry stale</span>
            )}
          </div>
          <div style={{ display: "flex", gap: 16, color: "#64748b", flexWrap: "wrap" }}>
            <span>
              <strong>Last Scan:</strong>{" "}
              {formatTimeIST(last_scan_at)}
            </span>
            <span>
              <strong>Data Cutoff:</strong>{" "}
              {formatTimeIST(data_cutoff)}
            </span>
            <span>
              <strong>Active Candidates:</strong> {candidate_ids.length}
            </span>
          </div>
        </div>

        {/* 1. Funnel Section */}
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#64748b",
              marginBottom: 8,
            }}
          >
            Universe Observed & Data Quality
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: 10,
            }}
          >
            <div
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "#64748b" }}>Universe Observed</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", marginTop: 2 }}>
                {funnel.universe_observed}
              </div>
            </div>
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #bbf7d0",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "#166534" }}>Fresh</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#15803d", marginTop: 2 }}>
                {funnel.fresh}
              </div>
            </div>
            <div
              style={{
                background: funnel.stale > 0 ? "#fffbeb" : "#ffffff",
                border: `1px solid ${funnel.stale > 0 ? "#fde68a" : "#e2e8f0"}`,
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: funnel.stale > 0 ? "#92400e" : "#64748b" }}>
                Stale
              </div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: funnel.stale > 0 ? "#b45309" : "#0f172a",
                  marginTop: 2,
                }}
              >
                {funnel.stale}
              </div>
            </div>
            <div
              style={{
                background: funnel.invalid_reference > 0 ? "#fef2f2" : "#ffffff",
                border: `1px solid ${funnel.invalid_reference > 0 ? "#fecaca" : "#e2e8f0"}`,
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: funnel.invalid_reference > 0 ? "#991b1b" : "#64748b",
                }}
              >
                Invalid Reference
              </div>
              <div
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: funnel.invalid_reference > 0 ? "#dc2626" : "#0f172a",
                  marginTop: 2,
                }}
              >
                {funnel.invalid_reference}
              </div>
            </div>
          </div>
        </div>

        {/* 2. Rejection Breakdown */}
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 8,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "#64748b",
              }}
            >
              Rejection Breakdown ({totalRejected} total rejected)
            </div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: 8,
            }}
          >
            {[
              { label: "Liquidity", value: rejections.liquidity, desc: "Min volume/depth fail" },
              { label: "Spread", value: rejections.spread, desc: "Exceeds tick tolerance" },
              { label: "Calibration", value: rejections.calibration, desc: "ECE / Brier degraded" },
              { label: "Negative EV", value: rejections.negative_ev, desc: "Net EV <= 0 after costs" },
              { label: "Portfolio Capacity", value: rejections.portfolio_capacity, desc: "Cap/sector limit" },
              { label: "A04 Kernel", value: rejections.a04, desc: "Deterministic governor" },
            ].map((rej) => (
              <div
                key={rej.label}
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: 6,
                  padding: "8px 10px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 600, color: "#334155" }}>
                    {rej.label}
                  </span>
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: rej.value > 0 ? "#475569" : "#94a3b8",
                    }}
                  >
                    {rej.value}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>{rej.desc}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Candidate Funnel Output Classes */}
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#64748b",
              marginBottom: 8,
            }}
          >
            Candidates Produced ({totalCandidates} total qualified)
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 10,
            }}
          >
            <div
              style={{
                background: "#f8fafc",
                border: "1px solid #cbd5e1",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: "#475569" }}>STANDARD</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#1e293b", marginTop: 2 }}>
                {candidates_by_class.standard}
              </div>
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>
                Core calibrated edge
              </div>
            </div>

            <div
              style={{
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: "#1e40af" }}>HIGH CONVICTION</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#1d4ed8", marginTop: 2 }}>
                {candidates_by_class.high_conviction}
              </div>
              <div style={{ fontSize: 10, color: "#3b82f6", marginTop: 2 }}>
                P(edge) &gt; 0.70 + support
              </div>
            </div>

            <div
              style={{
                background: "#faf5ff",
                border: "1px solid #e9d5ff",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: "#6b21a8" }}>CONVEX</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#7e22ce", marginTop: 2 }}>
                {candidates_by_class.convex}
              </div>
              <div style={{ fontSize: 10, color: "#a855f7", marginTop: 2 }}>
                Asymmetric payoff ratio
              </div>
            </div>

            <div
              style={{
                background: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: 8,
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 600, color: "#9f1239" }}>RARE EVENT</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#be123c", marginTop: 2 }}>
                {candidates_by_class.rare_event}
              </div>
              <div style={{ fontSize: 10, color: "#f43f5e", marginTop: 2 }}>
                Tail shock / gap trigger
              </div>
            </div>
          </div>
        </div>

        {/* 4. Active Candidate IDs Quick Selector */}
        {candidate_ids.length > 0 ? (
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                color: "#64748b",
                marginBottom: 6,
              }}
            >
              Active Candidate Funnel IDs
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {candidate_ids.map((id) => {
                const isSelected = selectedCandidateId === id;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onSelectCandidate?.(id)}
                    style={{
                      fontFamily: "monospace",
                      fontSize: 11,
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: `1px solid ${isSelected ? "#0f172a" : "#cbd5e1"}`,
                      background: isSelected ? "#0f172a" : "#ffffff",
                      color: isSelected ? "#ffffff" : "#334155",
                      cursor: "pointer",
                    }}
                  >
                    {id}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div
            style={{
              padding: "10px 14px",
              background: "#f8fafc",
              border: "1px dashed #cbd5e1",
              borderRadius: 6,
              fontSize: 12,
              color: "#64748b",
              textAlign: "center",
            }}
          >
            NO LIVE CANDIDATES · Zero candidates currently qualifying for risk allocation
          </div>
        )}
      </div>
    </Card>
  );
}
