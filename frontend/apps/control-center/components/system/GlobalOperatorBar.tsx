"use client";

import { useMemo, useState } from "react";
import { useOperatorState } from "./OperatorStateProvider";
import { SystemHealthIndicator, type HealthState } from "./SystemHealthIndicator";
import { OperatorControls } from "./OperatorControls";

function money(value: number) {
  return `${value >= 0 ? "+" : "−"}₹${Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
function truth(value: string | null | undefined): HealthState {
  if (value === "HEALTHY") return "HEALTHY";
  if (value === "READY") return "READY";
  if (value === "HALTED") return "HALTED";
  if (value === "DEGRADED" || value === "RECONCILING") return "DEGRADED";
  if (value === "STOPPED" || value === "OFFLINE") return "OFFLINE";
  return "UNKNOWN";
}

function Datum({ label, value, title, tone }: { label: string; value: string; title?: string; tone?: "good" | "bad" | "warn" }) {
  return <div className="operator-datum" title={title}><span>{label}</span><strong className={tone === "good" ? "ats-positive" : tone === "bad" ? "ats-negative" : tone === "warn" ? "operator-warn" : undefined}>{value}</strong></div>;
}

export function GlobalOperatorBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { system, runtime, pipeline, harness, sseStatus, loading, commandStatus } = useOperatorState();
  const [controlsOpen, setControlsOpen] = useState(false);
  const pnl = useMemo(() => Number(runtime?.pnl.realized ?? 0) + Number(runtime?.pnl.unrealized ?? 0), [runtime?.pnl.realized, runtime?.pnl.unrealized]);
  const session = runtime?.session.phase ?? "UNKNOWN";
  const market = session === "ENTRY_ALLOWED" ? "OPEN" : session === "CLOSED" ? "CLOSED" : session;
  const feedState: HealthState = runtime ? (runtime.feed_healthy ? "HEALTHY" : "STALE") : "UNKNOWN";
  const harnessState = truth(harness?.harness.state);
  const target = harness?.harness.execution_target ?? "PAPER";
  const liveMoney = harness?.harness.live_money ?? "OFF";
  return (
    <header className="operator-bar" aria-label="ATS system status and controls">
      <div className="operator-brand"><span className="operator-mark" aria-hidden="true">A</span><div><strong>ATS</strong><small>A2 CONTROL CENTER</small></div></div>
      <div className="operator-state-grid" aria-live="polite" aria-busy={loading}>
        <SystemHealthIndicator state={truth(system?.system_state)} label="SYSTEM" compact detail={system?.degradation_indicators.join(", ")} />
        <Datum label="MARKET" value={market} tone={market === "OPEN" ? "good" : undefined} />
        <SystemHealthIndicator state={feedState} label="FEED" compact detail={`Stream: ${sseStatus}`} />
        <Datum label="SESSION" value={session} title="Canonical runtime session phase" />
        <Datum label="TARGET" value={target} />
        <Datum label="USER" value={runtime?.trading_mode.user_selected ?? "UNKNOWN"} />
        <Datum label="EFFECTIVE" value={runtime?.trading_mode.effective ?? "UNKNOWN"} tone={runtime?.trading_mode.effective === "HALTED" ? "bad" : runtime?.trading_mode.deescalation_reason ? "warn" : undefined} title={runtime?.trading_mode.deescalation_reason ?? "No automatic de-escalation"} />
        <Datum label="MONEY" value={`PAPER · LIVE ${liveMoney}`} tone={liveMoney === "OFF" || liveMoney === "DISABLED" ? "good" : "bad"} />
        <Datum label="P&L" value={runtime ? money(pnl) : "—"} tone={runtime ? (pnl >= 0 ? "good" : "bad") : undefined} />
        <Datum label="POS" value={String(runtime?.open_positions.length ?? 0)} />
        <Datum label="OPP" value={String(pipeline?.candidates_qualified ?? 0)} />
        <SystemHealthIndicator state={harnessState} label="HARNESS" compact />
      </div>
      <div className="operator-actions">
        {commandStatus.state !== "idle" ? <span className={`command-result command-result-${commandStatus.state}`} role="status" title={commandStatus.message ?? undefined}>{commandStatus.state === "submitting" ? "WORKING" : commandStatus.state.toUpperCase()}</span> : null}
        <button className="command-trigger" type="button" onClick={onOpenPalette} aria-label="Open command palette"><span aria-hidden="true">⌕</span><kbd>Ctrl K</kbd></button>
        <button className="ats-btn ats-btn-primary" type="button" onClick={() => setControlsOpen(true)}>Controls</button>
      </div>
      <OperatorControls open={controlsOpen} onClose={() => setControlsOpen(false)} />
    </header>
  );
}
