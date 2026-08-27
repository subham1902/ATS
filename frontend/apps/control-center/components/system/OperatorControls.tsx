"use client";

import { useEffect, useState } from "react";
import type { RuntimeCommandRequest } from "@ats/api-client";
import { useOperatorState } from "./OperatorStateProvider";
import { SystemHealthIndicator } from "./SystemHealthIndicator";

type Pending = { request: RuntimeCommandRequest; title: string; detail: string };

export function OperatorControls({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { runtime, command, commandStatus } = useOperatorState();
  const [pending, setPending] = useState<Pending | null>(null);
  const [positionId, setPositionId] = useState("");
  useEffect(() => { if (open && runtime?.open_positions.length && !positionId) setPositionId(runtime.open_positions[0].position_id); }, [open, positionId, runtime?.open_positions]);
  useEffect(() => { if (!open) setPending(null); }, [open]);
  if (!open) return null;
  const run = async (request: RuntimeCommandRequest) => { const ok = await command(request); if (ok) { setPending(null); if (request.command === "HALT_SYSTEM" || request.command === "FLATTEN_PORTFOLIO") onClose(); } };
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="control-drawer" role="dialog" aria-modal="true" aria-labelledby="operator-controls-title">
        <div className="control-heading"><div><span className="eyebrow">BOUNDED RUNTIME COMMANDS</span><h2 id="operator-controls-title">Operator controls</h2></div><button className="ats-btn ats-btn-quiet" type="button" onClick={onClose} aria-label="Close operator controls">✕</button></div>
        <div className="safety-banner"><SystemHealthIndicator state="ACTIVE" label="A2 PAPER" compact /><span>Commands enter deterministic runtime authority. Live-money enablement and order entry are not available.</span></div>
        <section className="control-section" aria-labelledby="mode-heading"><div className="control-label"><h3 id="mode-heading">Operating mode</h3><span>User selected <strong>{runtime?.trading_mode.user_selected ?? "UNKNOWN"}</strong></span></div><div className="segmented-control">{(["SAFE", "NORMAL", "AGGRESSIVE"] as const).map((mode) => <button key={mode} type="button" aria-pressed={runtime?.trading_mode.user_selected === mode} disabled={commandStatus.state === "submitting"} onClick={() => void run({ command: "SET_MODE", mode })}>{mode}</button>)}</div><div className="effective-mode"><span>Effective mode</span><strong>{runtime?.trading_mode.effective ?? "UNKNOWN"}</strong>{runtime?.trading_mode.deescalation_reason ? <p><span aria-hidden="true">▲</span> Auto-deescalated: {runtime.trading_mode.deescalation_reason}</p> : <p>No automatic de-escalation active.</p>}</div></section>
        <section className="control-section" aria-labelledby="entry-heading"><div className="control-label"><h3 id="entry-heading">New entries</h3><span>{runtime?.paused_new_entries ? "Paused" : "Enabled by runtime state"}</span></div><div className="control-row"><button className="ats-btn" type="button" disabled={runtime?.paused_new_entries || commandStatus.state === "submitting"} onClick={() => void run({ command: "PAUSE_NEW_ENTRIES" })}>Pause new entries</button><button className="ats-btn" type="button" disabled={!runtime?.paused_new_entries || commandStatus.state === "submitting"} onClick={() => void run({ command: "RESUME_NEW_ENTRIES" })}>Resume</button></div></section>
        <section className="control-section" aria-labelledby="position-heading"><div className="control-label"><h3 id="position-heading">Position reduction</h3><span>{runtime?.open_positions.length ?? 0} open</span></div>{runtime?.open_positions.length ? <div className="position-exit"><label htmlFor="exit-position">Position</label><select id="exit-position" value={positionId} onChange={(event) => setPositionId(event.target.value)}>{runtime.open_positions.map((position) => <option key={position.position_id} value={position.position_id}>{position.instrument_id} · {position.quantity}</option>)}</select><button className="ats-btn" type="button" disabled={!positionId || commandStatus.state === "submitting"} onClick={() => setPending({ request: { command: "EXIT_POSITION", position_id: positionId }, title: "Exit this paper position?", detail: "The request will be evaluated and executed by the bounded runtime." })}>Exit position</button></div> : <p className="control-empty">No open positions to exit.</p>}</section>
        <section className="emergency-zone" aria-labelledby="emergency-heading"><div className="control-label"><h3 id="emergency-heading">Emergency controls</h3><span>Confirmation required</span></div><p>Use only to reduce exposure or stop autonomous operation.</p><div className="control-row"><button className="ats-btn ats-btn-danger" type="button" onClick={() => setPending({ request: { command: "FLATTEN_PORTFOLIO" }, title: "Flatten the paper portfolio?", detail: "Runtime will attempt to exit every open paper position. This cannot create a live-money order." })}>Flatten portfolio</button><button className="ats-btn ats-btn-danger" type="button" onClick={() => setPending({ request: { command: "HALT_SYSTEM" }, title: "Halt ATS?", detail: "Runtime will halt new activity according to the canonical session and risk state machines." })}>Halt system</button></div></section>
        {commandStatus.message ? <div className={`control-message control-message-${commandStatus.state}`} role="status">{commandStatus.message}</div> : null}
        {pending ? <div className="confirmation" role="alertdialog" aria-modal="true" aria-labelledby="confirmation-title"><div><span className="confirmation-icon" aria-hidden="true">!</span><h3 id="confirmation-title">{pending.title}</h3><p>{pending.detail}</p><label className="confirm-check"><input type="checkbox" id="confirm-command" /> I understand this runtime action.</label><div className="control-row"><button className="ats-btn" type="button" onClick={() => setPending(null)}>Cancel</button><button className="ats-btn ats-btn-danger" type="button" onClick={(event) => { const checkbox = event.currentTarget.parentElement?.parentElement?.querySelector<HTMLInputElement>("#confirm-command"); if (checkbox?.checked) void run(pending.request); else checkbox?.focus(); }}>Confirm action</button></div></div></div> : null}
      </section>
    </div>
  );
}
