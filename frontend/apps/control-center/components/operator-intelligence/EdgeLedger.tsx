"use client";

import React, { useState, useMemo } from "react";
import type {
  EdgeLedgerEntry,
  EdgeLedgerReadModel,
  CandidateClass,
  PortfolioBrainOutcome,
} from "@ats/api-client";
import { Card, Badge } from "@ats/ui";

export interface EdgeLedgerProps {
  ledger: EdgeLedgerReadModel | null;
  onSelectCandidate?: (candidateId: string) => void;
  selectedCandidateId?: string | null;
}

export function EdgeLedger({ ledger, onSelectCandidate, selectedCandidateId }: EdgeLedgerProps) {
  const [underlyingFilter, setUnderlyingFilter] = useState<string>("ALL");
  const [classFilter, setClassFilter] = useState<string>("ALL");
  const [strategyFilter, setStrategyFilter] = useState<string>("ALL");
  const [decisionFilter, setDecisionFilter] = useState<string>("ALL");
  const [evFilter, setEvFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedCandidateId, setExpandedCandidateId] = useState<string | null>(null);

  const entries = useMemo(() => ledger?.entries ?? [], [ledger]);

  // Extract unique filter options
  const underlyings = useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => set.add(e.underlying));
    return Array.from(set);
  }, [entries]);

  const strategies = useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => set.add(e.strategy));
    return Array.from(set);
  }, [entries]);

  // Filter entries
  const filteredEntries = useMemo(() => {
    return entries.filter((e) => {
      if (underlyingFilter !== "ALL" && e.underlying !== underlyingFilter) return false;
      if (classFilter !== "ALL" && e.candidate_class !== classFilter) return false;
      if (strategyFilter !== "ALL" && e.strategy !== strategyFilter) return false;
      if (decisionFilter !== "ALL") {
        if (decisionFilter === "ALLOW" && e.portfolio_brain_outcome !== "ALLOW") return false;
        if (decisionFilter === "ALLOW_REDUCED" && e.portfolio_brain_outcome !== "ALLOW_REDUCED")
          return false;
        if (decisionFilter === "DEFER" && e.portfolio_brain_outcome !== "DEFER") return false;
        if (decisionFilter === "DENY" && e.portfolio_brain_outcome !== "DENY") return false;
      }
      if (evFilter === "POSITIVE_NET_EV") {
        if (e.expected_net_value === null || e.expected_net_value <= 0) return false;
      } else if (evFilter === "NEGATIVE_OR_ZERO_NET_EV") {
        if (e.expected_net_value !== null && e.expected_net_value > 0) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = e.candidate_id.toLowerCase().includes(q);
        const matchInst = e.instrument.toLowerCase().includes(q);
        if (!matchId && !matchInst) return false;
      }
      return true;
    });
  }, [entries, underlyingFilter, classFilter, strategyFilter, decisionFilter, evFilter, searchQuery]);

  // Export functions (OI2.1)
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(filteredEntries, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `edge_ledger_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    if (filteredEntries.length === 0) return;
    const headers = [
      "candidate_id",
      "timestamp",
      "underlying",
      "instrument",
      "direction",
      "strategy",
      "candidate_class",
      "predicted_probability",
      "market_implied_probability",
      "gross_edge",
      "spread_cost",
      "slippage_estimate",
      "fees_estimate",
      "theta_cost",
      "execution_uncertainty",
      "calibration_uncertainty",
      "calibration_health",
      "expected_net_value",
      "portfolio_penalty",
      "approved_capital",
      "approved_quantity",
      "portfolio_brain_outcome",
      "a04_outcome",
      "eventual_outcome",
      "realized_pnl",
    ];
    const csvRows = [headers.join(",")];
    for (const e of filteredEntries) {
      const row = [
        e.candidate_id,
        e.timestamp,
        e.underlying,
        e.instrument,
        e.direction,
        e.strategy,
        e.candidate_class,
        e.predicted_probability ?? "",
        e.market_implied_probability ?? "",
        e.gross_edge ?? "",
        e.spread_cost ?? "",
        e.slippage_estimate ?? "",
        e.fees_estimate ?? "",
        e.theta_cost ?? "",
        e.execution_uncertainty ?? "",
        e.calibration_uncertainty ?? "",
        e.calibration_health ?? "UNKNOWN",
        e.expected_net_value ?? "",
        e.portfolio_penalty ?? "",
        e.approved_capital ?? "",
        e.approved_quantity ?? "",
        e.portfolio_brain_outcome,
        e.a04_outcome,
        e.eventual_outcome ?? "",
        e.realized_pnl ?? "",
      ];
      csvRows.push(row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
    }
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `edge_ledger_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!ledger) {
    return (
      <Card title="Edge Ledger">
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
          No Edge Ledger records available · state unknown
        </div>
      </Card>
    );
  }

  const renderClassBadge = (c: CandidateClass) => {
    switch (c) {
      case "HIGH_CONVICTION":
        return <Badge tone="success">HIGH CONV</Badge>;
      case "CONVEX":
        return <Badge tone="warn">CONVEX</Badge>;
      case "RARE_EVENT":
        return <Badge tone="danger">RARE EVENT</Badge>;
      case "STANDARD":
      default:
        return <Badge tone="neutral">STANDARD</Badge>;
    }
  };

  const renderOutcomeBadge = (outcome: PortfolioBrainOutcome) => {
    switch (outcome) {
      case "ALLOW":
        return <Badge tone="success">ALLOW</Badge>;
      case "ALLOW_REDUCED":
        return <Badge tone="warn">ALLOW REDUCED</Badge>;
      case "DEFER":
        return <Badge tone="neutral">DEFER</Badge>;
      case "DENY":
        return <Badge tone="danger">DENY</Badge>;
      case "UNKNOWN":
      default:
        return <Badge tone="unknown">UNKNOWN</Badge>;
    }
  };

  return (
    <Card title="Edge Ledger (Gross Edge vs Realized Net EV)">
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Top Control & Filter Bar */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
            justifyContent: "space-between",
            background: "#f8fafc",
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
          }}
        >
          {/* Filters */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <input
              type="text"
              placeholder="Search candidate / instrument..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                fontSize: 12,
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid #cbd5e1",
                minWidth: 180,
              }}
            />

            <select
              value={underlyingFilter}
              onChange={(e) => setUnderlyingFilter(e.target.value)}
              style={{ fontSize: 12, padding: "4px 8px", borderRadius: 6, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Underlying: All</option>
              {underlyings.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>

            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              style={{ fontSize: 12, padding: "4px 8px", borderRadius: 6, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Class: All</option>
              <option value="STANDARD">STANDARD</option>
              <option value="HIGH_CONVICTION">HIGH_CONVICTION</option>
              <option value="CONVEX">CONVEX</option>
              <option value="RARE_EVENT">RARE_EVENT</option>
            </select>

            {strategies.length > 0 && (
              <select
                value={strategyFilter}
                onChange={(e) => setStrategyFilter(e.target.value)}
                style={{ fontSize: 12, padding: "4px 8px", borderRadius: 6, border: "1px solid #cbd5e1" }}
              >
                <option value="ALL">Strategy: All</option>
                {strategies.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}

            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              style={{ fontSize: 12, padding: "4px 8px", borderRadius: 6, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Decision: All</option>
              <option value="ALLOW">ALLOW</option>
              <option value="ALLOW_REDUCED">ALLOW_REDUCED</option>
              <option value="DEFER">DEFER</option>
              <option value="DENY">DENY</option>
            </select>

            <select
              value={evFilter}
              onChange={(e) => setEvFilter(e.target.value)}
              style={{ fontSize: 12, padding: "4px 8px", borderRadius: 6, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Net EV: All</option>
              <option value="POSITIVE_NET_EV">Positive Net EV (&gt; 0)</option>
              <option value="NEGATIVE_OR_ZERO_NET_EV">Negative / Zero Net EV (&le; 0)</option>
            </select>
          </div>

          {/* Export Actions */}
          <div style={{ display: "flex", gap: 6 }}>
            <button
              type="button"
              onClick={exportCsv}
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 8px",
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Export CSV
            </button>
            <button
              type="button"
              onClick={exportJson}
              style={{
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 8px",
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              Export JSON
            </button>
          </div>
        </div>

        {/* Ledger Table */}
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              textAlign: "left",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "2px solid #cbd5e1",
                  background: "#f1f5f9",
                  color: "#475569",
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                <th style={{ padding: "8px 6px" }}>Candidate / Time</th>
                <th style={{ padding: "8px 6px" }}>Instrument / Dir</th>
                <th style={{ padding: "8px 6px" }}>Class</th>
                <th style={{ padding: "8px 6px", textAlign: "right" }}>Prob (Pred / Mkt)</th>
                <th style={{ padding: "8px 6px", textAlign: "right" }}>Gross Edge</th>
                <th style={{ padding: "8px 6px", textAlign: "right" }}>Cost Drag</th>
                <th style={{ padding: "8px 6px", textAlign: "right" }}>Net EV</th>
                <th style={{ padding: "8px 6px" }}>Portfolio Brain</th>
                <th style={{ padding: "8px 6px" }}>A04 Kernel</th>
                <th style={{ padding: "8px 6px" }}>Realized</th>
                <th style={{ padding: "8px 6px" }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredEntries.length === 0 ? (
                <tr>
                  <td
                    colSpan={11}
                    style={{
                      padding: 24,
                      textAlign: "center",
                      color: "#94a3b8",
                      fontStyle: "italic",
                    }}
                  >
                    No matching edge ledger entries
                  </td>
                </tr>
              ) : (
                filteredEntries.map((row) => {
                  const isSelected = selectedCandidateId === row.candidate_id;
                  const isExpanded = expandedCandidateId === row.candidate_id;

                  // Total cost drag
                  const costDrag =
                    row.spread_cost !== null ||
                    row.slippage_estimate !== null ||
                    row.fees_estimate !== null ||
                    row.theta_cost !== null
                      ? ((row.spread_cost ?? 0) +
                          (row.slippage_estimate ?? 0) +
                          (row.fees_estimate ?? 0) +
                          (row.theta_cost ?? 0))
                      : null;

                  return (
                    <React.Fragment key={row.candidate_id}>
                      <tr
                        style={{
                          borderBottom: "1px solid #e2e8f0",
                          background: isSelected
                            ? "#f0fdf4"
                            : isExpanded
                            ? "#f8fafc"
                            : "transparent",
                          cursor: "pointer",
                        }}
                        onClick={() => onSelectCandidate?.(row.candidate_id)}
                      >
                        {/* Candidate / Time */}
                        <td style={{ padding: "8px 6px" }}>
                          <div style={{ fontFamily: "monospace", fontWeight: 700, color: "#0f172a" }}>
                            {row.candidate_id.slice(0, 8)}
                          </div>
                          <div style={{ fontSize: 10, color: "#64748b" }}>
                            {row.timestamp ? new Date(row.timestamp).toLocaleTimeString() : "—"}
                          </div>
                        </td>

                        {/* Instrument / Direction */}
                        <td style={{ padding: "8px 6px" }}>
                          <div style={{ fontWeight: 600, color: "#1e293b" }}>{row.instrument}</div>
                          <div style={{ fontSize: 10, color: "#64748b" }}>
                            {row.underlying} · {row.direction} · {row.strategy}
                          </div>
                        </td>

                        {/* Candidate Class */}
                        <td style={{ padding: "8px 6px" }}>
                          {renderClassBadge(row.candidate_class)}
                        </td>

                        {/* Probabilities */}
                        <td style={{ padding: "8px 6px", textAlign: "right" }}>
                          <span style={{ fontWeight: 600, color: "#0f172a" }}>
                            {row.predicted_probability !== null
                              ? `${(row.predicted_probability * 100).toFixed(1)}%`
                              : "UNKNOWN"}
                          </span>
                          <span style={{ fontSize: 10, color: "#64748b", marginLeft: 4 }}>
                            /{" "}
                            {row.market_implied_probability !== null
                              ? `${(row.market_implied_probability * 100).toFixed(1)}%`
                              : "—"}
                          </span>
                        </td>

                        {/* Gross Edge */}
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace" }}>
                          {row.gross_edge !== null ? (
                            <span style={{ color: row.gross_edge >= 0 ? "#15803d" : "#b91c1c" }}>
                              {row.gross_edge >= 0 ? `+${row.gross_edge.toFixed(2)}R` : `${row.gross_edge.toFixed(2)}R`}
                            </span>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>—</span>
                          )}
                        </td>

                        {/* Cost Drag */}
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace", color: "#64748b" }}>
                          {costDrag !== null ? `-${costDrag.toFixed(2)}R` : "—"}
                        </td>

                        {/* Net EV */}
                        <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "monospace" }}>
                          {row.expected_net_value !== null ? (
                            <span
                              style={{
                                fontWeight: 700,
                                padding: "2px 6px",
                                borderRadius: 4,
                                background: row.expected_net_value > 0 ? "#dcfce7" : "#fee2e2",
                                color: row.expected_net_value > 0 ? "#15803d" : "#b91c1c",
                              }}
                            >
                              {row.expected_net_value > 0 ? `+${row.expected_net_value.toFixed(2)}R` : `${row.expected_net_value.toFixed(2)}R`}
                            </span>
                          ) : (
                            <span style={{ color: "#94a3b8" }}>UNKNOWN</span>
                          )}
                        </td>

                        {/* Portfolio Brain */}
                        <td style={{ padding: "8px 6px" }}>
                          {renderOutcomeBadge(row.portfolio_brain_outcome)}
                        </td>

                        {/* A04 */}
                        <td style={{ padding: "8px 6px" }}>
                          <Badge
                            tone={
                              row.a04_outcome === "ALLOW"
                                ? "success"
                                : row.a04_outcome === "DENY"
                                ? "danger"
                                : "unknown"
                            }
                          >
                            {row.a04_outcome}
                          </Badge>
                        </td>

                        {/* Eventual Outcome */}
                        <td style={{ padding: "8px 6px" }}>
                          {row.eventual_outcome ? (
                            <span style={{ fontSize: 11, fontWeight: 600 }}>
                              {row.eventual_outcome}{" "}
                              {row.realized_pnl && `(${row.realized_pnl})`}
                            </span>
                          ) : (
                            <span style={{ color: "#94a3b8", fontSize: 11 }}>—</span>
                          )}
                        </td>

                        {/* Expand Button */}
                        <td style={{ padding: "8px 6px" }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedCandidateId(isExpanded ? null : row.candidate_id);
                            }}
                            style={{
                              fontSize: 11,
                              padding: "2px 6px",
                              borderRadius: 4,
                              border: "1px solid #cbd5e1",
                              background: "#ffffff",
                              cursor: "pointer",
                            }}
                          >
                            {isExpanded ? "Hide" : "Cost Breakdown"}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded Cost Decomposition Inspector */}
                      {isExpanded && (
                        <tr style={{ background: "#f8fafc", borderBottom: "1px solid #cbd5e1" }}>
                          <td colSpan={11} style={{ padding: "12px 16px" }}>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                                gap: 12,
                                fontSize: 11,
                              }}
                            >
                              <div style={{ background: "#ffffff", padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                                <div style={{ fontWeight: 600, color: "#475569" }}>Cost Decomposition</div>
                                <div style={{ marginTop: 4, color: "#64748b", lineHeight: 1.6 }}>
                                  Spread Cost: <strong>{row.spread_cost !== null ? `${row.spread_cost}R` : "UNKNOWN"}</strong><br />
                                  Slippage Est: <strong>{row.slippage_estimate !== null ? `${row.slippage_estimate}R` : "UNKNOWN"}</strong><br />
                                  Fees Est: <strong>{row.fees_estimate !== null ? `${row.fees_estimate}R` : "UNKNOWN"}</strong><br />
                                  Theta Cost: <strong>{row.theta_cost !== null ? `${row.theta_cost}R` : "UNKNOWN"}</strong>
                                </div>
                              </div>

                              <div style={{ background: "#ffffff", padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                                <div style={{ fontWeight: 600, color: "#475569" }}>Uncertainty Penalties</div>
                                <div style={{ marginTop: 4, color: "#64748b", lineHeight: 1.6 }}>
                                  Execution Uncert: <strong>{row.execution_uncertainty !== null ? `${row.execution_uncertainty}R` : "UNKNOWN"}</strong><br />
                                  Calibration Uncert: <strong>{row.calibration_uncertainty !== null ? `${row.calibration_uncertainty}R` : "UNKNOWN"}</strong><br />
                                  Calibration Health: <strong>{row.calibration_health ?? "UNKNOWN"}</strong><br />
                                  Portfolio Penalty: <strong>{row.portfolio_penalty !== null ? `${row.portfolio_penalty}R` : "0R"}</strong>
                                </div>
                              </div>

                              <div style={{ background: "#ffffff", padding: 8, borderRadius: 6, border: "1px solid #e2e8f0" }}>
                                <div style={{ fontWeight: 600, color: "#475569" }}>Approved Sizing & Limits</div>
                                <div style={{ marginTop: 4, color: "#64748b", lineHeight: 1.6 }}>
                                  Approved Capital: <strong>{row.approved_capital ?? "UNKNOWN"}</strong><br />
                                  Approved Quantity: <strong>{row.approved_quantity ?? "UNKNOWN"}</strong><br />
                                  Full Candidate ID: <code style={{ fontSize: 10 }}>{row.candidate_id}</code>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
