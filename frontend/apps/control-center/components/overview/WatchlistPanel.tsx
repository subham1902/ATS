"use client";

import { useOperatorState } from "../system/OperatorStateProvider";
import { StatusBadge } from "../system/SystemHealthIndicator";
import type { LiveUnderlyingPrediction } from "@ats/api-client";

interface WatchlistPanelProps {
  predictions: LiveUnderlyingPrediction[];
}

export function WatchlistPanel({ predictions }: WatchlistPanelProps) {
  const { runtime, pipeline } = useOperatorState();
  const feedHealthy = runtime?.feed_healthy;

  const instruments = [
    {
      underlying: "NIFTY",
      price: pipeline?.nifty_last,
      atm: pipeline?.nifty_atm,
      regime: pipeline?.nifty_regime,
      prediction: predictions.find((p) => p.underlying === "NIFTY"),
    },
    {
      underlying: "BANKNIFTY",
      price: pipeline?.banknifty_last,
      atm: pipeline?.banknifty_atm,
      regime: pipeline?.banknifty_regime,
      prediction: predictions.find((p) => p.underlying === "BANKNIFTY"),
    },
  ];

  return (
    <div className="wl-panel">
      <div className="wl-header">
        <strong>Active Watchlist</strong>
        <span>{instruments.length} instruments · {feedHealthy ? "FRESH" : "STALE"}</span>
      </div>
      <table className="wl-table">
        <thead>
          <tr>
            <th>Underlying</th>
            <th>LTP</th>
            <th>ATM</th>
            <th>Regime</th>
            <th>Feed</th>
            <th>Direction</th>
            <th>Bull %</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {instruments.map((inst) => (
            <tr key={inst.underlying}>
              <td><strong>{inst.underlying}</strong></td>
              <td className="wl-mono">{inst.price ?? "—"}</td>
              <td>{inst.atm ?? "UNKNOWN"}</td>
              <td>{inst.regime ?? "UNKNOWN"}</td>
              <td><StatusBadge state={feedHealthy ? "HEALTHY" : runtime ? "STALE" : "UNKNOWN"}>{feedHealthy ? "FRESH" : "STALE"}</StatusBadge></td>
              <td>{inst.prediction?.predicted_direction ?? "—"}</td>
              <td className="wl-mono">{inst.prediction ? `${(inst.prediction.bullish_probability * 100).toFixed(1)}%` : "—"}</td>
              <td><span className={`wl-decision wl-decision-${(inst.prediction?.decision ?? "hold").toLowerCase()}`}>{inst.prediction?.decision ?? "—"}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
