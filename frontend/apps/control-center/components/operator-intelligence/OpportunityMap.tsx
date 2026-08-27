"use client";

import React, { useState, useMemo } from "react";
import type {
  OpportunityMapPoint,
  CandidateClass,
  PortfolioBrainOutcome,
} from "@ats/api-client";
import { Card, Badge } from "@ats/ui";

export interface OpportunityMapProps {
  points: OpportunityMapPoint[] | null;
  onSelectCandidate?: (candidateId: string) => void;
  selectedCandidateId?: string | null;
}

export function OpportunityMap({
  points,
  onSelectCandidate,
  selectedCandidateId,
}: OpportunityMapProps) {
  const [hoveredPoint, setHoveredPoint] = useState<OpportunityMapPoint | null>(null);
  const [classFilter, setClassFilter] = useState<string>("ALL");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("ALL");

  const pointList = useMemo(() => points ?? [], [points]);

  const filteredPoints = useMemo(() => {
    return pointList.filter((p) => {
      if (classFilter !== "ALL" && p.candidate_class !== classFilter) return false;
      if (outcomeFilter !== "ALL" && p.portfolio_brain_outcome !== outcomeFilter) return false;
      return true;
    });
  }, [pointList, classFilter, outcomeFilter]);

  if (!points || points.length === 0) {
    return (
      <Card title="Market Opportunity Map">
        <div
          role="status"
          style={{
            padding: 32,
            textAlign: "center",
            color: "#6b7280",
            fontSize: 13,
            background: "#f9fafb",
            borderRadius: 8,
            border: "1px dashed #d1d5db",
          }}
        >
          No opportunity map data available · zero candidate telemetry emitted
        </div>
      </Card>
    );
  }

  // Chart dimensions & coordinate mapping
  const width = 800;
  const height = 440;
  const padding = { top: 30, right: 40, bottom: 50, left: 60 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  // X: Calibrated Conviction (0.0 to 1.0)
  const minX = 0.0;
  const maxX = 1.0;
  // Y: Expected Net Payoff / Net EV (-2.0R to +6.0R)
  const minY = -2.0;
  const maxY = 6.0;

  const scaleX = (x: number | null) => {
    const val = x !== null ? Math.max(minX, Math.min(maxX, x)) : 0.5;
    return padding.left + ((val - minX) / (maxX - minX)) * plotWidth;
  };

  const scaleY = (y: number | null) => {
    const val = y !== null ? Math.max(minY, Math.min(maxY, y)) : 0.0;
    return padding.top + plotHeight - ((val - minY) / (maxY - minY)) * plotHeight;
  };

  const scaleRadius = (liquidity: number | null) => {
    if (liquidity === null) return 8;
    return Math.max(6, Math.min(22, 6 + (liquidity / 100) * 16));
  };

  const getColorByClass = (c: CandidateClass) => {
    switch (c) {
      case "HIGH_CONVICTION":
        return { fill: "#2563eb", stroke: "#1d4ed8", text: "HIGH CONVICTION" };
      case "CONVEX":
        return { fill: "#9333ea", stroke: "#7e22ce", text: "CONVEX" };
      case "RARE_EVENT":
        return { fill: "#e11d48", stroke: "#be123c", text: "RARE EVENT" };
      case "STANDARD":
      default:
        return { fill: "#475569", stroke: "#334155", text: "STANDARD" };
    }
  };

  const xMid = scaleX(0.5);
  const yZero = scaleY(0.0);
  const yAsymThreshold = scaleY(2.0);

  return (
    <Card title="Market Opportunity Map (Calibrated Conviction vs Net Payoff)">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Controls & Filter Header */}
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
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600, color: "#475569" }}>Filters:</span>
            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              style={{ fontSize: 12, padding: "3px 8px", borderRadius: 4, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Class: All</option>
              <option value="STANDARD">STANDARD</option>
              <option value="HIGH_CONVICTION">HIGH_CONVICTION</option>
              <option value="CONVEX">CONVEX</option>
              <option value="RARE_EVENT">RARE_EVENT</option>
            </select>

            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              style={{ fontSize: 12, padding: "3px 8px", borderRadius: 4, border: "1px solid #cbd5e1" }}
            >
              <option value="ALL">Portfolio Outcome: All</option>
              <option value="ALLOW">ALLOW</option>
              <option value="ALLOW_REDUCED">ALLOW_REDUCED</option>
              <option value="DEFER">DEFER</option>
              <option value="DENY">DENY</option>
            </select>

            <span style={{ color: "#64748b" }}>
              Showing <strong>{filteredPoints.length}</strong> of {pointList.length} candidates
            </span>
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: 12, fontSize: 11, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#475569" }} />
              Standard
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#2563eb" }} />
              High Conviction
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#9333ea" }} />
              Convex
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#e11d48" }} />
              Rare Event
            </span>
          </div>
        </div>

        {/* Visual Map SVG Canvas */}
        <div style={{ position: "relative", width: "100%", overflowX: "auto" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: "100%", height: "auto", background: "#ffffff", borderRadius: 8, border: "1px solid #e2e8f0" }}
          >
            {/* Region Quadrants (OI5.1) */}
            {/* 1. Low Conviction / Low Payoff (Noise Zone) */}
            <rect
              x={padding.left}
              y={yAsymThreshold}
              width={xMid - padding.left}
              height={padding.top + plotHeight - yAsymThreshold}
              fill="#f8fafc"
              opacity={0.7}
            />
            <text x={padding.left + 10} y={padding.top + plotHeight - 12} fontSize="10" fill="#94a3b8" fontWeight="600">
              Low Conviction / Low Asymmetry (Noise / Drag)
            </text>

            {/* 2. Lower Conviction / High Convexity (Asymmetric Long-shot) */}
            <rect
              x={padding.left}
              y={padding.top}
              width={xMid - padding.left}
              height={yAsymThreshold - padding.top}
              fill="#faf5ff"
              opacity={0.7}
            />
            <text x={padding.left + 10} y={padding.top + 20} fontSize="10" fill="#a855f7" fontWeight="600">
              Lower Conviction / High Convexity (Tail Options)
            </text>

            {/* 3. High Conviction / Normal Asymmetry */}
            <rect
              x={xMid}
              y={yAsymThreshold}
              width={padding.left + plotWidth - xMid}
              height={padding.top + plotHeight - yAsymThreshold}
              fill="#eff6ff"
              opacity={0.5}
            />
            <text x={xMid + 10} y={padding.top + plotHeight - 12} fontSize="10" fill="#3b82f6" fontWeight="600">
              High Conviction / Normal Asymmetry (Directional Spreads)
            </text>

            {/* 4. High Conviction / High Convexity (Prime Opportunities) */}
            <rect
              x={xMid}
              y={padding.top}
              width={padding.left + plotWidth - xMid}
              height={yAsymThreshold - padding.top}
              fill="#f0fdf4"
              opacity={0.6}
            />
            <text x={xMid + 10} y={padding.top + 20} fontSize="10" fill="#15803d" fontWeight="700">
              High Conviction / High Convexity (Prime Edge)
            </text>

            {/* Zero EV Reference Line */}
            <line
              x1={padding.left}
              y1={yZero}
              x2={padding.left + plotWidth}
              y2={yZero}
              stroke="#cbd5e1"
              strokeDasharray="4 4"
              strokeWidth="1.5"
            />
            <text x={padding.left + plotWidth - 70} y={yZero - 4} fontSize="9" fill="#94a3b8">
              Net EV = 0.0R
            </text>

            {/* 0.5 Conviction Reference Line */}
            <line
              x1={xMid}
              y1={padding.top}
              x2={xMid}
              y2={padding.top + plotHeight}
              stroke="#e2e8f0"
              strokeDasharray="3 3"
              strokeWidth="1"
            />

            {/* Grid & Axis Lines */}
            <line
              x1={padding.left}
              y1={padding.top + plotHeight}
              x2={padding.left + plotWidth}
              y2={padding.top + plotHeight}
              stroke="#475569"
              strokeWidth="1.5"
            />
            <line
              x1={padding.left}
              y1={padding.top}
              x2={padding.left}
              y2={padding.top + plotHeight}
              stroke="#475569"
              strokeWidth="1.5"
            />

            {/* X-Axis Ticks & Labels */}
            {[0.0, 0.25, 0.5, 0.75, 1.0].map((t) => {
              const xPos = scaleX(t);
              return (
                <g key={t}>
                  <line x1={xPos} y1={padding.top + plotHeight} x2={xPos} y2={padding.top + plotHeight + 6} stroke="#475569" />
                  <text x={xPos} y={padding.top + plotHeight + 20} fontSize="10" fill="#475569" textAnchor="middle">
                    {(t * 100).toFixed(0)}%
                  </text>
                </g>
              );
            })}
            <text
              x={padding.left + plotWidth / 2}
              y={padding.top + plotHeight + 38}
              fontSize="11"
              fontWeight="600"
              fill="#1e293b"
              textAnchor="middle"
            >
              Calibrated Probability / Support Conviction &rarr;
            </text>

            {/* Y-Axis Ticks & Labels */}
            {[-2.0, 0.0, 2.0, 4.0, 6.0].map((t) => {
              const yPos = scaleY(t);
              return (
                <g key={t}>
                  <line x1={padding.left - 6} y1={yPos} x2={padding.left} y2={yPos} stroke="#475569" />
                  <text x={padding.left - 10} y={yPos + 3} fontSize="10" fill="#475569" textAnchor="end">
                    {t > 0 ? `+${t.toFixed(1)}R` : `${t.toFixed(1)}R`}
                  </text>
                </g>
              );
            })}
            <text
              x={-(padding.top + plotHeight / 2)}
              y={padding.left - 42}
              fontSize="11"
              fontWeight="600"
              fill="#1e293b"
              textAnchor="middle"
              transform="rotate(-90)"
            >
              Expected Net Payoff (Net EV in R) &rarr;
            </text>

            {/* Candidate Bubbles */}
            {filteredPoints.map((pt) => {
              const cx = scaleX(pt.calibrated_probability);
              const cy = scaleY(pt.expected_net_value);
              const r = scaleRadius(pt.liquidity_score);
              const colors = getColorByClass(pt.candidate_class);
              const isSelected = selectedCandidateId === pt.candidate_id;
              const isHovered = hoveredPoint?.candidate_id === pt.candidate_id;

              return (
                <g
                  key={pt.candidate_id}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHoveredPoint(pt)}
                  onMouseLeave={() => setHoveredPoint(null)}
                  onClick={() => onSelectCandidate?.(pt.candidate_id)}
                >
                  {/* Selection Ring */}
                  {(isSelected || isHovered) && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={r + 4}
                      fill="none"
                      stroke={isSelected ? "#0f172a" : colors.stroke}
                      strokeWidth="2.5"
                      strokeDasharray={isSelected ? "none" : "3 3"}
                    />
                  )}

                  {/* Main Bubble */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill={colors.fill}
                    stroke="#ffffff"
                    strokeWidth="1.5"
                    opacity={0.85}
                  />

                  {/* Candidate Label inside / adjacent */}
                  {r >= 12 && (
                    <text
                      x={cx}
                      y={cy + 3}
                      fontSize="9"
                      fill="#ffffff"
                      fontWeight="700"
                      textAnchor="middle"
                      pointerEvents="none"
                    >
                      {pt.instrument.slice(0, 5)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Interactive Hover Tooltip */}
          {hoveredPoint && (
            <div
              style={{
                position: "absolute",
                top: 10,
                right: 16,
                background: "rgba(15, 23, 42, 0.95)",
                color: "#ffffff",
                padding: "10px 14px",
                borderRadius: 8,
                fontSize: 11,
                lineHeight: 1.5,
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.2)",
                zIndex: 10,
                maxWidth: 280,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12, borderBottom: "1px solid #334155", paddingBottom: 4 }}>
                {hoveredPoint.instrument}
              </div>
              <div style={{ marginTop: 4, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px 8px" }}>
                <span>Class: <strong>{hoveredPoint.candidate_class}</strong></span>
                <span>Underlying: <strong>{hoveredPoint.underlying}</strong></span>
                <span>Calib Prob: <strong>{hoveredPoint.calibrated_probability !== null ? `${(hoveredPoint.calibrated_probability * 100).toFixed(1)}%` : "UNKNOWN"}</strong></span>
                <span>Net EV: <strong>{hoveredPoint.expected_net_value !== null ? `${hoveredPoint.expected_net_value.toFixed(2)}R` : "UNKNOWN"}</strong></span>
                <span>Asymmetry: <strong>{hoveredPoint.asymmetry !== null ? `${hoveredPoint.asymmetry.toFixed(1)}x` : "UNKNOWN"}</strong></span>
                <span>Liquidity: <strong>{hoveredPoint.liquidity_score !== null ? `${hoveredPoint.liquidity_score}/100` : "UNKNOWN"}</strong></span>
                <span>Spread: <strong>{hoveredPoint.spread_ticks !== null ? `${hoveredPoint.spread_ticks}t` : "UNKNOWN"}</strong></span>
                <span>Analogue Supp: <strong>{hoveredPoint.analogue_support !== null ? `${(hoveredPoint.analogue_support * 100).toFixed(0)}%` : "UNKNOWN"}</strong></span>
              </div>
              <div style={{ marginTop: 6, paddingTop: 4, borderTop: "1px solid #334155", display: "flex", justifyContent: "space-between" }}>
                <span>Portfolio: <strong>{hoveredPoint.portfolio_brain_outcome}</strong></span>
                <span>A04: <strong>{hoveredPoint.a04_outcome}</strong></span>
              </div>
              <div style={{ marginTop: 4, fontSize: 9, color: "#94a3b8", fontFamily: "monospace" }}>
                ID: {hoveredPoint.candidate_id}
              </div>
            </div>
          )}
        </div>

        {/* OI5.1 Disclaimer Notice */}
        <div
          style={{
            fontSize: 11,
            color: "#64748b",
            background: "#f8fafc",
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #e2e8f0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>
            ℹ️ <strong>Presentation visualization only</strong> — visual quadrant placement does not guarantee execution or profit.
          </span>
          <span style={{ fontWeight: 600 }}>Bubble size: Liquidity / Quality</span>
        </div>
      </div>
    </Card>
  );
}
