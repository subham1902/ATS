"use client";

import { useMemo } from "react";
import { useOperatorState } from "../system/OperatorStateProvider";
import { StatusBadge } from "../system/SystemHealthIndicator";

const amount = (v: string | undefined) => v === undefined ? "UNKNOWN" : `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export function CapitalPanel() {
  const { runtime } = useOperatorState();
  const totalPnl = useMemo(() => Number(runtime?.pnl.realized ?? 0) + Number(runtime?.pnl.unrealized ?? 0), [runtime?.pnl.realized, runtime?.pnl.unrealized]);
  const drawdown = runtime ? Number(runtime.pnl.drawdown_fraction) * 100 : null;
  const lossState = runtime?.loss_state ?? "UNKNOWN";

  return (
    <div className="cap-panel">
      <div className="cap-header">
        <strong>Capital & Survival</strong>
        <StatusBadge state={lossState === "NORMAL" ? "HEALTHY" : lossState === "HALTED" ? "HALTED" : runtime ? "DEGRADED" : "UNKNOWN"}>{lossState}</StatusBadge>
      </div>

      <div className="cap-grid">
        <div className="cap-item cap-total"><span>Total Capital</span><strong>{amount(runtime?.capital.total)}</strong></div>
        <div className="cap-item"><span>Available</span><strong>{amount(runtime?.capital.available)}</strong></div>
        <div className="cap-item"><span>Reserved</span><strong>{amount(runtime?.capital.reserved)}</strong></div>
        <div className="cap-item"><span>Inflight</span><strong>{amount(runtime?.capital.inflight)}</strong></div>
        <div className="cap-item"><span>Committed</span><strong>{amount(runtime?.capital.used)}</strong></div>
      </div>

      <div className="cap-pnl">
        <div className="cap-pnl-item"><span>Realized P&L</span><strong className={Number(runtime?.pnl.realized ?? 0) >= 0 ? "ats-positive" : "ats-negative"}>{amount(runtime?.pnl.realized)}</strong></div>
        <div className="cap-pnl-item"><span>Unrealized P&L</span><strong className={Number(runtime?.pnl.unrealized ?? 0) >= 0 ? "ats-positive" : "ats-negative"}>{amount(runtime?.pnl.unrealized)}</strong></div>
        <div className="cap-pnl-item"><span>Session Total</span><strong className={totalPnl >= 0 ? "ats-positive" : "ats-negative"}>{amount(String(totalPnl))}</strong></div>
        <div className="cap-pnl-item"><span>Session HWM</span><strong>{amount(runtime?.pnl.session_peak)}</strong></div>
        <div className="cap-pnl-item"><span>Drawdown</span><strong className={drawdown != null && drawdown > 0 ? "ats-negative" : ""}>{drawdown != null ? `${drawdown.toFixed(2)}%` : "UNKNOWN"}</strong></div>
      </div>

      <div className="cap-bar">
        <div className="cap-bar-track">
          {runtime && (
            <>
              <div className="cap-bar-used" style={{ width: `${Math.min(100, (Number(runtime.capital.used) / Math.max(Number(runtime.capital.total), 1)) * 100)}%` }} />
              <div className="cap-bar-reserved" style={{ width: `${Math.min(100, (Number(runtime.capital.reserved) / Math.max(Number(runtime.capital.total), 1)) * 100)}%` }} />
              <div className="cap-bar-inflight" style={{ width: `${Math.min(100, (Number(runtime.capital.inflight) / Math.max(Number(runtime.capital.total), 1)) * 100)}%` }} />
            </>
          )}
        </div>
        <div className="cap-bar-legend">
          <span><i className="cap-legend-used" />Used</span>
          <span><i className="cap-legend-reserved" />Reserved</span>
          <span><i className="cap-legend-inflight" />Inflight</span>
        </div>
      </div>
    </div>
  );
}
