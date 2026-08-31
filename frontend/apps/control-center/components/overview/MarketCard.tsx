"use client";

import { useOperatorState } from "../system/OperatorStateProvider";
import { StatusBadge } from "../system/SystemHealthIndicator";
import type { LiveUnderlyingPrediction } from "@ats/api-client";

function age(iso: string | undefined) {
  if (!iso) return "UNKNOWN";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`;
}

interface MarketCardProps {
  symbol: "NIFTY" | "BANKNIFTY";
  prediction?: LiveUnderlyingPrediction;
}

export function MarketCard({ symbol, prediction }: MarketCardProps) {
  const { runtime, pipeline } = useOperatorState();
  const price = symbol === "NIFTY" ? pipeline?.nifty_last : pipeline?.banknifty_last;
  const atm = symbol === "NIFTY" ? pipeline?.nifty_atm : pipeline?.banknifty_atm;
  const regime = symbol === "NIFTY" ? pipeline?.nifty_regime : pipeline?.banknifty_regime;
  const volatility = symbol === "NIFTY" ? pipeline?.nifty_volatility : pipeline?.banknifty_volatility;
  const feedHealthy = runtime?.feed_healthy;
  const updatedAt = runtime?.updated_at;

  const bullPct = prediction ? (prediction.bullish_probability * 100).toFixed(1) : null;
  const bearPct = prediction ? (prediction.bearish_probability * 100).toFixed(1) : null;
  const decision = prediction?.decision ?? null;
  const expression = prediction?.preferred_expression ?? null;
  const reason = prediction?.reason_code ?? null;

  return (
    <div className="mc-card">
      <div className="mc-header">
        <div className="mc-symbol">
          <strong>{symbol}</strong>
          <StatusBadge state={feedHealthy ? "HEALTHY" : runtime ? "STALE" : "UNKNOWN"}>FEED</StatusBadge>
        </div>
        <span className="mc-age">{age(updatedAt)} ago</span>
      </div>

      <div className="mc-price-row">
        <div className="mc-price">
          <strong>{price ?? "—"}</strong>
          <span className="mc-change">CHANGE UNAVAILABLE</span>
        </div>
        {decision && (
          <div className={`mc-decision mc-decision-${decision === "QUALIFIED" ? "bull" : decision === "HOLD" ? "hold" : "bear"}`}>
            {expression === "LONG_CE" ? "LONG CE" : expression === "LONG_PE" ? "LONG PE" : decision}
          </div>
        )}
      </div>

      <div className="mc-grid">
        <div className="mc-field"><span>ATM</span><strong>{atm ?? "UNKNOWN"}</strong></div>
        <div className="mc-field"><span>REGIME</span><strong>{regime ?? "UNKNOWN"}</strong></div>
        <div className="mc-field"><span>VOL</span><strong>{volatility ?? "UNKNOWN"}</strong></div>
        <div className="mc-field"><span>OPTION WINDOW</span><strong>{pipeline?.attached ? "ACTIVE" : "UNKNOWN"}</strong></div>
      </div>

      {prediction && (
        <div className="mc-prediction">
          <div className="mc-prob-bar">
            <div className="mc-prob-bull" style={{ width: `${prediction.bullish_probability * 100}%` }}>
              {bullPct}%
            </div>
            <div className="mc-prob-bear" style={{ width: `${prediction.bearish_probability * 100}%` }}>
              {bearPct}%
            </div>
          </div>
          <div className="mc-pred-details">
            <span>Threshold: {(prediction.activation_threshold * 100).toFixed(1)}%</span>
            <span>Distance: {(prediction.distance_to_threshold * 100).toFixed(1)}pp</span>
            {reason && <span className="mc-reason">{reason.replaceAll("_", " ")}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
