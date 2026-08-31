"use client";

import type { LiveUnderlyingPrediction } from "@ats/api-client";
import { formatTimeIST } from "../../lib/formatTime";

function pct(v: number | null) { return v === null ? "—" : `${(v * 100).toFixed(1)}%`; }

interface ScannerFeedProps {
  predictions: LiveUnderlyingPrediction[];
  maxRows?: number;
}

export function ScannerFeed({ predictions, maxRows = 50 }: ScannerFeedProps) {
  const rows = predictions.slice(-maxRows).reverse();

  if (rows.length === 0) {
    return <div className="sf-empty">No scanner activity. Waiting for market data.</div>;
  }

  return (
    <div className="sf-container">
      <div className="sf-scroll">
        <table className="sf-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Underlying</th>
              <th>Spot</th>
              <th>Regime</th>
              <th>Dir</th>
              <th>Bull %</th>
              <th>Bear %</th>
              <th>Expression</th>
              <th>Net EV</th>
              <th>Decision</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.underlying}-${r.timestamp}-${i}`} className={`sf-row sf-decision-${r.decision.toLowerCase()}`}>
                <td className="sf-mono">{formatTimeIST(r.timestamp)}</td>
                <td><strong>{r.underlying}</strong></td>
                <td className="sf-mono">₹{r.spot_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                <td>{r.regime}</td>
                <td><span className={`sf-dir sf-dir-${r.predicted_direction.toLowerCase()}`}>{r.predicted_direction}</span></td>
                <td>{pct(r.bullish_probability)}</td>
                <td>{pct(r.bearish_probability)}</td>
                <td>{r.preferred_expression}</td>
                <td className={r.estimated_net_ev != null && r.estimated_net_ev > 0 ? "ats-positive" : ""}>{r.estimated_net_ev?.toFixed(3) ?? "—"}</td>
                <td><span className={`sf-badge sf-badge-${r.decision.toLowerCase()}`}>{r.decision}</span></td>
                <td className="sf-reason">{r.reason_code.replaceAll("_", " ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
