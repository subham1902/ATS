"use client";

import type { LiveUnderlyingPrediction, ShadowModelPrediction } from "@ats/api-client";

function pct(v: number) { return (v * 100).toFixed(1); }

function ShadowRow({ m }: { m: ShadowModelPrediction }) {
  return (
    <tr>
      <td>{m.name}</td>
      <td>{m.direction}</td>
      <td>{pct(m.probability)}%</td>
      <td style={{ color: m.distance >= 0 ? "#067647" : "#667085" }}>{(m.distance * 100).toFixed(1)}pp</td>
      <td><span className={`pp-activate pp-activate-${m.would_activate ? "yes" : "no"}`}>{m.would_activate ? "YES" : "NO"}</span></td>
    </tr>
  );
}

export function PredictionPanel({ prediction }: { prediction: LiveUnderlyingPrediction }) {
  const bull = prediction.bullish_probability * 100;
  const bear = prediction.bearish_probability * 100;
  const hold = Math.max(0, 100 - bull - bear);
  const dist = prediction.distance_to_threshold * 100;

  return (
    <div className="pp-card">
      <div className="pp-header">
        <strong>{prediction.underlying}</strong>
        <span className={`pp-direction pp-dir-${prediction.predicted_direction.toLowerCase()}`}>{prediction.predicted_direction}</span>
        <span className="pp-decision">{prediction.decision}</span>
      </div>

      <div className="pp-probs">
        <div className="pp-prob-row">
          <span>Bullish</span>
          <div className="pp-bar"><div className="pp-bar-bull" style={{ width: `${bull}%` }} /></div>
          <strong>{pct(prediction.bullish_probability)}%</strong>
        </div>
        <div className="pp-prob-row">
          <span>Bearish</span>
          <div className="pp-bar"><div className="pp-bar-bear" style={{ width: `${bear}%` }} /></div>
          <strong>{pct(prediction.bearish_probability)}%</strong>
        </div>
        <div className="pp-prob-row">
          <span>Hold</span>
          <div className="pp-bar"><div className="pp-bar-hold" style={{ width: `${hold}%` }} /></div>
          <strong>{hold.toFixed(1)}%</strong>
        </div>
      </div>

      <div className="pp-metrics">
        <div><span>Threshold</span><strong>{pct(prediction.activation_threshold)}%</strong></div>
        <div><span>Distance</span><strong className={dist >= 0 ? "ats-positive" : "ats-negative"}>{dist >= 0 ? "+" : ""}{dist.toFixed(1)}pp</strong></div>
        <div><span>Confidence</span><strong>{pct(prediction.confidence)}%</strong></div>
        <div><span>Regime</span><strong>{prediction.regime}</strong></div>
      </div>

      {prediction.estimated_net_ev != null && (
        <div className="pp-ev">
          <span>Net EV</span>
          <strong className={prediction.estimated_net_ev > 0 ? "ats-positive" : "ats-negative"}>
            {prediction.estimated_net_ev > 0 ? "+" : ""}{prediction.estimated_net_ev.toFixed(3)}
          </strong>
          {prediction.estimated_gross_edge != null && <span>Gross: {prediction.estimated_gross_edge.toFixed(3)}</span>}
          {prediction.estimated_cost != null && <span>Cost: {prediction.estimated_cost.toFixed(3)}</span>}
        </div>
      )}

      <div className="pp-reason">{prediction.reason_code.replaceAll("_", " ")}</div>

      {prediction.shadow_models && prediction.shadow_models.length > 0 && (
        <details className="pp-shadows">
          <summary>Champion vs {prediction.shadow_models.length} Challengers</summary>
          <table>
            <thead><tr><th>Model</th><th>Dir</th><th>Prob</th><th>Dist</th><th>Activate</th></tr></thead>
            <tbody>
              <tr className="pp-champion"><td>C0 (Champion)</td><td>{prediction.predicted_direction}</td><td>{pct(prediction.calibrated_probability)}%</td><td>{dist.toFixed(1)}pp</td><td><span className={`pp-activate pp-activate-${prediction.decision !== "HOLD" ? "yes" : "no"}`}>{prediction.decision !== "HOLD" ? "YES" : "NO"}</span></td></tr>
              {prediction.shadow_models.map((m) => <ShadowRow key={m.model_id} m={m} />)}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}
