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
    rejections.a04 +
    (rejections.neutral_thesis ?? 0);
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
              { label: "Neutral Thesis", value: rejections.neutral_thesis ?? 0, desc: "P < 0.55 activation hurdle" },
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

        {/* 4. Live Continuous Predictions & Market Theses */}
        {scanner.predictions && Object.keys(scanner.predictions).length > 0 && (
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
              Continuous Predictions & Real-Time Directional Theses
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: 12,
              }}
            >
              {Object.values(scanner.predictions).map((pred) => {
                const isBull = pred.predicted_direction === "BULLISH";
                const isBear = pred.predicted_direction === "BEARISH";
                const pUp = (pred.bullish_probability * 100).toFixed(2);
                const pDown = (pred.bearish_probability * 100).toFixed(2);
                const distPp = (pred.distance_to_threshold * 100).toFixed(2);

                return (
                  <div
                    key={pred.underlying}
                    style={{
                      background: "#ffffff",
                      border: "1px solid #cbd5e1",
                      borderRadius: 8,
                      padding: 12,
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <strong style={{ fontSize: 14, color: "#0f172a" }}>
                          {pred.underlying}
                        </strong>
                        <span style={{ fontSize: 12, color: "#64748b" }}>
                          ₹{pred.spot_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <Badge
                        tone={
                          pred.decision === "QUALIFIED"
                            ? "success"
                            : isBull
                            ? "success"
                            : isBear
                            ? "danger"
                            : "neutral"
                        }
                      >
                        {pred.predicted_direction}
                      </Badge>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 6,
                        background: "#f8fafc",
                        padding: 8,
                        borderRadius: 6,
                        fontSize: 11,
                      }}
                    >
                      <div>
                        <span style={{ color: "#64748b" }}>P(UP): </span>
                        <strong>{pUp}%</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>P(DOWN): </span>
                        <strong>{pDown}%</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Hurdle: </span>
                        <strong>55.00%</strong>
                      </div>
                      <div>
                        <span style={{ color: "#64748b" }}>Hurdle Dist: </span>
                        <strong style={{ color: Number(distPp) >= 0 ? "#16a34a" : "#dc2626" }}>
                          {Number(distPp) >= 0 ? `+${distPp}` : distPp} pp
                        </strong>
                      </div>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 11,
                        color: "#475569",
                        borderTop: "1px solid #f1f5f9",
                        paddingTop: 6,
                      }}
                    >
                      <span>
                        Regime: <strong>{pred.regime}</strong> ({pred.volatility})
                      </span>
                      <span>
                        Expression: <strong>{pred.preferred_expression}</strong>
                      </span>
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 10,
                        color: "#64748b",
                      }}
                    >
                      <span>
                        ATM: <strong>{pred.atm_strike ?? "—"}</strong>
                      </span>
                      <span>
                        Decision: <strong>{pred.decision}</strong> ({pred.reason_code})
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 5. Champion vs Shadow Challengers Live Benchmark */}
        {scanner.predictions && Object.values(scanner.predictions)[0]?.shadow_models && (
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
              Champion vs. Shadow Challengers (Zero Live Authority)
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f1f5f9", textAlign: "left", color: "#475569" }}>
                    <th style={{ padding: "6px 8px" }}>Model</th>
                    <th style={{ padding: "6px 8px" }}>Direction</th>
                    <th style={{ padding: "6px 8px" }}>Probability</th>
                    <th style={{ padding: "6px 8px" }}>Distance to 55%</th>
                    <th style={{ padding: "6px 8px" }}>Would Activate</th>
                    <th style={{ padding: "6px 8px" }}>Authority Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.values(scanner.predictions)[0].shadow_models?.map((sm) => (
                    <tr key={sm.model_id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "6px 8px", fontWeight: 600 }}>{sm.name}</td>
                      <td style={{ padding: "6px 8px" }}>{sm.direction}</td>
                      <td style={{ padding: "6px 8px" }}>{(sm.probability * 100).toFixed(2)}%</td>
                      <td
                        style={{
                          padding: "6px 8px",
                          color: sm.distance >= 0 ? "#16a34a" : "#64748b",
                        }}
                      >
                        {(sm.distance * 100).toFixed(2)} pp
                      </td>
                      <td style={{ padding: "6px 8px" }}>
                        <Badge tone={sm.would_activate ? "success" : "neutral"}>
                          {sm.would_activate ? "YES" : "NO"}
                        </Badge>
                      </td>
                      <td style={{ padding: "6px 8px", fontSize: 10, color: "#64748b" }}>
                        {sm.status}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 6. Active Candidate IDs Quick Selector */}
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

        {/* 7. Rolling Continuous Predictions Log */}
        {scanner.recent_predictions && scanner.recent_predictions.length > 0 && (
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
              Recent Continuous Prediction Stream ({scanner.recent_predictions.length} recorded)
            </div>
            <div style={{ maxHeight: 200, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
              <table style={{ width: "100%", fontSize: 10, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f8fafc", textAlign: "left", color: "#64748b", position: "sticky", top: 0 }}>
                    <th style={{ padding: "4px 6px" }}>Time (IST)</th>
                    <th style={{ padding: "4px 6px" }}>Underlying</th>
                    <th style={{ padding: "4px 6px" }}>Mark</th>
                    <th style={{ padding: "4px 6px" }}>Dir</th>
                    <th style={{ padding: "4px 6px" }}>P(UP)</th>
                    <th style={{ padding: "4px 6px" }}>Dist</th>
                    <th style={{ padding: "4px 6px" }}>Expression</th>
                    <th style={{ padding: "4px 6px" }}>Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {scanner.recent_predictions.slice(-20).reverse().map((rp, idx) => (
                    <tr key={`${rp.underlying}-${rp.timestamp}-${idx}`} style={{ borderBottom: "1px solid #f1f5f9" }}>
                      <td style={{ padding: "4px 6px", fontFamily: "monospace" }}>{formatTimeIST(rp.timestamp)}</td>
                      <td style={{ padding: "4px 6px", fontWeight: 600 }}>{rp.underlying}</td>
                      <td style={{ padding: "4px 6px" }}>₹{rp.spot_price.toFixed(1)}</td>
                      <td style={{ padding: "4px 6px" }}>{rp.predicted_direction}</td>
                      <td style={{ padding: "4px 6px" }}>{(rp.bullish_probability * 100).toFixed(2)}%</td>
                      <td style={{ padding: "4px 6px", color: rp.distance_to_threshold >= 0 ? "#16a34a" : "#64748b" }}>
                        {(rp.distance_to_threshold * 100).toFixed(2)} pp
                      </td>
                      <td style={{ padding: "4px 6px" }}>{rp.preferred_expression}</td>
                      <td style={{ padding: "4px 6px", color: rp.decision === "QUALIFIED" ? "#16a34a" : "#64748b" }}>
                        {rp.decision}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
