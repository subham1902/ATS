"use client";

import type { EdgeLedgerEntry } from "@ats/api-client";

const STAGES = [
  "OBSERVED",
  "FRESH",
  "FEATURES",
  "REGIME",
  "PREDICTION",
  "CALIBRATION",
  "THESIS",
  "CANDIDATE",
  "PORTFOLIO",
  "A04",
  "ORDER",
  "FILL",
] as const;

function stageStatus(entry: EdgeLedgerEntry, stage: string): "pass" | "fail" | "pending" {
  switch (stage) {
    case "OBSERVED": return "pass";
    case "FRESH": return "pass";
    case "FEATURES": return "pass";
    case "REGIME": return "pass";
    case "PREDICTION": return entry.predicted_probability != null ? "pass" : "fail";
    case "CALIBRATION": return entry.calibration_health === "HEALTHY" || entry.calibration_health === "DEGRADED" ? "pass" : entry.calibration_health === "INVALID" ? "fail" : "pending";
    case "THESIS": return entry.predicted_probability != null && entry.predicted_probability > 0.5 ? "pass" : "fail";
    case "CANDIDATE": return "pass";
    case "PORTFOLIO": return entry.portfolio_brain_outcome === "ALLOW" || entry.portfolio_brain_outcome === "ALLOW_REDUCED" ? "pass" : entry.portfolio_brain_outcome === "DENY" ? "fail" : "pending";
    case "A04": return entry.a04_outcome === "ALLOW" ? "pass" : entry.a04_outcome === "DENY" ? "fail" : "pending";
    case "ORDER": return entry.a04_outcome === "ALLOW" && entry.portfolio_brain_outcome !== "DENY" ? "pass" : "pending";
    case "FILL": return entry.eventual_outcome === "WIN" || entry.eventual_outcome === "LOSS" || entry.eventual_outcome === "SCRATCH" ? "pass" : "pending";
    default: return "pending";
  }
}

export function PipelineJourney({ entry }: { entry: EdgeLedgerEntry }) {
  const finalStage = entry.a04_outcome === "ALLOW" ? "QUALIFIED" : entry.portfolio_brain_outcome === "DENY" ? "PORTFOLIO DENIED" : entry.a04_outcome === "DENY" ? "A04 DENIED" : "EVALUATED";

  return (
    <div className="pj-container">
      <div className="pj-header">
        <strong>{entry.instrument}</strong>
        <span>{entry.underlying} · {entry.strategy}</span>
        <span className={`pj-final pj-final-${finalStage === "QUALIFIED" ? "pass" : "fail"}`}>{finalStage}</span>
      </div>
      <div className="pj-stages">
        {STAGES.map((stage) => {
          const status = stageStatus(entry, stage);
          return (
            <div key={stage} className={`pj-stage pj-stage-${status}`}>
              <span className="pj-stage-icon">{status === "pass" ? "✓" : status === "fail" ? "✕" : "—"}</span>
              <span className="pj-stage-label">{stage}</span>
            </div>
          );
        })}
      </div>
      <div className="pj-summary">
        <span>P={entry.predicted_probability ?? "—"}</span>
        <span>Net EV={entry.expected_net_value?.toFixed(3) ?? "—"}</span>
        <span>Portfolio={entry.portfolio_brain_outcome}</span>
        <span>A04={entry.a04_outcome}</span>
      </div>
    </div>
  );
}
