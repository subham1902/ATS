"use client";

import type { FunnelCounts, RejectionBreakdown } from "@ats/api-client";

interface RejectionFunnelProps {
  funnel: FunnelCounts;
  rejections: RejectionBreakdown;
  qualified: number;
}

export function RejectionFunnel({ funnel, rejections, qualified }: RejectionFunnelProps) {
  const totalRejected = Object.values(rejections).reduce((s, v) => s + (v ?? 0), 0);
  const evaluated = Math.max(0, funnel.fresh - funnel.invalid_reference);
  const stages = [
    { label: "OBSERVED", value: funnel.universe_observed, cls: "" },
    { label: "FRESH", value: funnel.fresh, cls: "" },
    { label: "EVALUATED", value: evaluated, cls: "" },
    { label: "REJECTED", value: totalRejected, cls: "rf-rejected" },
    { label: "QUALIFIED", value: qualified, cls: "rf-qualified" },
  ];

  const rejectionItems = [
    { label: "Neutral Thesis", value: rejections.neutral_thesis ?? 0 },
    { label: "Calibration", value: rejections.calibration },
    { label: "Liquidity", value: rejections.liquidity },
    { label: "Spread", value: rejections.spread },
    { label: "Negative EV", value: rejections.negative_ev },
    { label: "Portfolio Cap", value: rejections.portfolio_capacity },
    { label: "A04", value: rejections.a04 },
  ].filter((r) => r.value > 0);

  const maxRejection = Math.max(1, ...rejectionItems.map((r) => r.value));

  return (
    <div className="rf-container">
      <div className="rf-stages">
        {stages.map((stage, i) => (
          <div key={stage.label} className={`rf-stage ${stage.cls}`}>
            <strong>{stage.value}</strong>
            <span>{stage.label}</span>
            {i < stages.length - 1 && <i className="rf-arrow" aria-hidden="true">→</i>}
          </div>
        ))}
      </div>

      {rejectionItems.length > 0 && (
        <div className="rf-breakdown">
          <div className="rf-breakdown-title">Rejection Distribution</div>
          <div className="rf-bars">
            {rejectionItems.map((r) => (
              <div key={r.label} className="rf-bar-row">
                <span className="rf-bar-label">{r.label}</span>
                <div className="rf-bar-track">
                  <div className="rf-bar-fill" style={{ width: `${(r.value / maxRejection) * 100}%` }} />
                </div>
                <strong className="rf-bar-value">{r.value}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
