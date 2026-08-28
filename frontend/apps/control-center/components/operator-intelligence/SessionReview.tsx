"use client";

import React from "react";

export interface SessionReviewProps {
  sessionId?: string;
  session?: {
    session_id: string;
    trading_date: string;
    champion: string;
    mode: string;
    finalPnl?: string;
    maxDrawdown?: string;
    tradeCount?: number;
    integrityStatus?: string;
    funnel?: {
      observations?: number;
      predictions?: number;
      rejections?: number;
      candidates?: number;
      portfolio?: { allow?: number; deny?: number; defer?: number };
      a04?: { allow?: number; deny?: number };
      orders?: number;
      fills?: number;
      positions?: { opened?: number; closed?: number };
    };
    timeline?: Array<{
      event_time_utc: string;
      event_type: string;
      decision?: string;
      reason_code?: string;
    }>;
    predictions?: Array<{
      probability: number;
      model_id: string;
      underlying: string;
      decision: string;
    }>;
    rejections?: {
      total?: number;
      by_reason?: Record<string, { count: number }>;
    };
    gateAudit?: Record<string, { state: string; reached: boolean }>;
    whyNoTrade?: {
      primary_cause: string;
    };
  } | null;
}

export function SessionReview({ session }: SessionReviewProps) {
  if (!session) {
    return (
      <div style={{ padding: 24, background: "#f9fafb", borderRadius: 8, border: "1px dashed #d1d5db", color: "#6b7280" }}>
        No session selected. Evidence recorder operates over durable local mirror only (LOCAL_DURABLE_ONLY). Select a session to view forensic review.
      </div>
    );
  }

  const integrityStatus = session.integrityStatus || "VALID";
  const integrityColor = integrityStatus === "VALID" ? "#166534" : (integrityStatus === "INCOMPLETE" ? "#92400e" : "#991b1b");
  const integrityBg = integrityStatus === "VALID" ? "#f0fdf4" : (integrityStatus === "INCOMPLETE" ? "#fffbeb" : "#fef2f2");
  const integrityBorder = integrityStatus === "VALID" ? "#86efac" : (integrityStatus === "INCOMPLETE" ? "#fde68a" : "#fca5a5");

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", color: "#111827" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#0f172a" }}>
            Session Review — {session.session_id.slice(0, 8)}...
          </h2>
          <div style={{ fontSize: 13, color: "#64748b", marginTop: 4 }}>
            {session.trading_date} · Champion: {session.champion} · Mode: {session.mode}
          </div>
        </div>
        <div
          style={{
            border: `2px solid ${integrityBorder}`,
            background: integrityBg,
            color: integrityColor,
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          EVIDENCE INTEGRITY: {integrityStatus}
        </div>
      </div>

      {/* Pipeline Funnel */}
      <section style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
          PIPELINE FUNNEL
        </h3>
        <FunnelRow funnel={session.funnel || {}} />
      </section>

      {/* Why No Trade */}
      {session.whyNoTrade && (
        <section style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
            WHY NO TRADE?
          </h3>
          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: 14,
              background: "#ffffff",
            }}
          >
            <div style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
              Primary Cause: {session.whyNoTrade.primary_cause}
            </div>
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
              {session.whyNoTrade.label || session.whyNoTrade.supporting_facts ? "See evidence ledger for full reconstruction." : ""}
            </div>
            {session.whyNoTrade.supporting_facts && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#374151" }}>
                <pre style={{ background: "#f8fafc", padding: 8, borderRadius: 6, overflow: "auto" }}>
                  {JSON.stringify(session.whyNoTrade.supporting_facts, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Gate Audit */}
      {session.gateAudit && (
        <section style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
            GATE AUDIT
          </h3>
          <GateTable gates={session.gateAudit} />
        </section>
      )}

      {/* Predictions / Near Activations */}
      <section style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
          MODEL PREDICTION DISTRIBUTION
        </h3>
        <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>
            Production champion predictions: {session.funnel?.predictions || 0}
          </div>
          <div style={{ fontSize: 12, color: "#6b7280" }}>
            Threshold: <strong>0.55</strong> · Shadow-only predictions are not counted toward activation.
          </div>
        </div>
      </section>

      {/* Rejection Breakdown */}
      {session.rejections && session.rejections.by_reason && Object.keys(session.rejections.by_reason).length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
            REJECTION BREAKDOWN
          </h3>
          <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 14 }}>
            {(Object.entries(session.rejections.by_reason) as [string, { count: number }][])
              .filter(([, info]) => info.count > 0)
              .map(([code, info]) => (
                <div key={code} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0" }}>
                  <span style={{ color: "#374151" }}>{code}</span>
                  <span style={{ fontWeight: 700, color: "#0f172a" }}>{info.count}</span>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Timeline preview */}
      {session.timeline && session.timeline.length > 0 && (
        <section>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", color: "#374151", marginBottom: 8 }}>
            DECISION TIMELINE
          </h3>
          <div style={{ fontSize: 11, color: "#6b7280" }}>
            Showing {session.timeline.length} events · UTC authority timestamps preserved
          </div>
          <div style={{ marginTop: 8 }}>
            {session.timeline.slice(0, 8).map((ev) => (
              <div key={ev.event_time_utc} style={{ fontSize: 11, padding: "2px 0", borderBottom: "1px solid #f3f4f6" }}>
                <span style={{ color: "#6b7280" }}>{ev.event_time_utc.slice(11, 19)}</span>
                <span style={{ marginLeft: 8, fontWeight: 600 }}>{ev.event_type}</span>
                {ev.decision && <span style={{ marginLeft: 4, color: "#0f172a" }}>· {ev.decision}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function FunnelRow({ funnel }: { funnel: Record<string, unknown> }) {
  const items = [
    { label: "Observations", value: (funnel.observations as number) || 0 },
    { label: "Predictions", value: (funnel.predictions as number) || 0 },
    { label: "Rejections", value: (funnel.rejections as number) || 0 },
    { label: "Candidates", value: (funnel.candidates as number) || 0 },
    { label: "Portfolio", value: (funnel.portfolio as { allow?: number })?.allow || 0 },
    { label: "A04 ALLOW", value: (funnel.a04 as { allow?: number })?.allow || 0 },
    { label: "Orders", value: (funnel.orders as number) || 0 },
    { label: "Fills", value: (funnel.fills as number) || 0 },
    { label: "Positions Opened", value: (funnel.positions as { opened?: number })?.opened || 0 },
    { label: "Positions Closed", value: (funnel.positions as { closed?: number })?.closed || 0 },
  ];
  return (
    <div style={{ display: "flex", gap: 4, overflowX: "auto" }}>
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            minWidth: 72,
            textAlign: "center",
            border: "1px solid #e5e7eb",
            borderRadius: 6,
            padding: "6px 8px",
            background: "#f8fafc",
          }}
        >
          <div style={{ fontSize: 9, color: "#64748b", fontWeight: 600 }}>{item.label}</div>
          <div style={{ fontSize: 16, fontWeight: 800, color: "#0f172a" }}>{item.value}</div>
        </div>
      ))}
    </div>
  );
}

function GateTable({ gates }: { gates: Record<string, { state: string; reached: boolean }> }) {
  return (
    <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ background: "#f8fafc" }}>
          <th style={{ textAlign: "left", padding: 6, borderBottom: "1px solid #e5e7eb" }}>Gate</th>
          <th style={{ textAlign: "left", padding: 6, borderBottom: "1px solid #e5e7eb" }}>State</th>
          <th style={{ textAlign: "left", padding: 6, borderBottom: "1px solid #e5e7eb" }}>Reached</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(gates).map(([name, gate]) => (
          <tr key={name} style={{ borderBottom: "1px solid #f3f4f6" }}>
            <td style={{ padding: 4 }}>{name}</td>
            <td style={{ padding: 4, fontWeight: 700, color: gate.state === "NOT_REACHED" ? "#64748b" : (gate.state === "DENY" ? "#991b1b" : (gate.state === "ALLOW" ? "#166534" : "#92400e")) }}>
              {gate.state}
            </td>
            <td style={{ padding: 4 }}>{gate.reached ? "YES" : "NO"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
