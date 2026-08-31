"use client";

import { useOperatorState } from "../system/OperatorStateProvider";
import { StatusBadge } from "../system/SystemHealthIndicator";

const money = (v: string | number | undefined, signed = false) =>
  v === undefined || v === null ? "—" : `${signed && Number(v) >= 0 ? "+" : ""}₹${Math.abs(Number(v)).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export function PositionPanel() {
  const { runtime, command } = useOperatorState();
  const positions = runtime?.open_positions ?? [];

  if (positions.length === 0) {
    return (
      <div className="pos-panel">
        <div className="pos-header"><strong>Open Positions</strong><span>PAPER BROKER</span></div>
        <div className="pos-empty">No open positions. ATS monitoring market.</div>
      </div>
    );
  }

  return (
    <div className="pos-panel">
      <div className="pos-header">
        <strong>Open Positions</strong>
        <span>{positions.length} active · PAPER</span>
      </div>
      <div className="pos-grid">
        {positions.map((p) => {
          const pnl = Number(p.unrealized_pnl);
          const isManual = p.origin === "OPERATOR_MANUAL";
          return (
            <article key={p.position_id} className={`pos-card ${pnl < 0 ? "pos-negative" : "pos-positive"}`}>
              <div className="pos-card-header">
                <strong>{p.instrument_id}</strong>
                <StatusBadge state="ACTIVE">{isManual ? "MANUAL" : "AUTO"}</StatusBadge>
              </div>
              <div className="pos-metrics">
                <div><span>Entry</span><strong>{p.entry_price}</strong></div>
                <div><span>Mark</span><strong>{p.mark_price ?? "—"}</strong></div>
                <div><span>Qty</span><strong>{p.quantity}</strong></div>
                <div><span>P&L</span><strong className={pnl < 0 ? "ats-negative" : "ats-positive"}>{money(p.unrealized_pnl, true)}</strong></div>
                <div><span>Stop</span><strong>{p.current_stop ?? "—"}</strong></div>
                <div><span>Trailing</span><strong>{p.trailing_stop ?? "Inactive"}</strong></div>
                <div><span>Held</span><strong>{p.time_held_minutes ?? 0}m</strong></div>
                <div><span>Exit Mode</span><strong>{p.managed_exit_mode ?? "ATS_MANAGED_EXIT"}</strong></div>
              </div>
              {p.last_recommendation && (
                <div className="pos-recommendation">{p.last_recommendation} · {(p.recommendation_reasons ?? []).join(" · ").replaceAll("_", " ")}</div>
              )}
              <div className="pos-actions">
                <button type="button" className="ats-btn" onClick={() => void command({ command: p.managed_exit_mode === "ATS_MANAGED_EXIT" ? "SET_MONITOR_ONLY" : "SET_MANAGED_EXIT", position_id: p.position_id })}>
                  {p.managed_exit_mode === "ATS_MANAGED_EXIT" ? "Monitor Only" : "ATS Exit"}
                </button>
                <button type="button" className="ats-btn ats-btn-danger" onClick={() => { if (window.confirm("Exit this PAPER position?")) void command({ command: "EXIT_POSITION", position_id: p.position_id }); }}>
                  Exit
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
