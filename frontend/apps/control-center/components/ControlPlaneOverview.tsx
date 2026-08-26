"use client";

import { useState } from "react";
import type { AgentChatAnswer, ControlPlaneOverview as Overview, RuntimeCommandRequest } from "@ats/api-client";
import { Card, DetailField, EmptyState } from "@ats/ui";

const shown = (value: string | null) => value ?? "UNKNOWN";

export function ControlPlaneOverview({
  state,
  onChat,
  onCommand,
}: {
  state: Overview;
  onChat?: (question: string) => Promise<AgentChatAnswer>;
  onCommand?: (command: RuntimeCommandRequest) => Promise<unknown>;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AgentChatAnswer | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const ask = async () => {
    if (!onChat || !question.trim()) return;
    try { setAnswer(await onChat(question)); setChatError(null); }
    catch { setChatError("Agent chat unavailable; no action was taken."); }
  };
  return (
    <section aria-label="ATS intelligence overview" style={{ display: "grid", gap: 16 }}>
      <Card title="System / Session / Feed">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 12 }}>
          <DetailField label="SYSTEM" value={state.system} />
          <DetailField label="SESSION" value={state.session} />
          <DetailField label="FEED" value={state.feed} />
          <DetailField label="PAPER BROKER" value={state.broker} />
          <DetailField label="USER MODE" value={state.user_mode} />
          <DetailField label="EFFECTIVE MODE" value={state.effective_mode} />
          <DetailField label="MODE REASON" value={state.mode_reason ?? "—"} />
        </div>
      </Card>
      <Card title="NIFTY / BANKNIFTY">
        {state.underlyings.map((item) => (
          <div key={item.symbol} aria-label={`${item.symbol} ${item.freshness}`}>
            {item.symbol}: {shown(item.price)} · {item.freshness}
          </div>
        ))}
      </Card>
      <Card title="Capital / P&L">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 12 }}>
          {Object.entries(state.capital).map(([key, value]) => <DetailField key={key} label={key.toUpperCase()} value={shown(value)} />)}
          {Object.entries(state.pnl).map(([key, value]) => <DetailField key={key} label={key.toUpperCase()} value={shown(value)} />)}
        </div>
      </Card>
      <Card title="Portfolio Intelligence">
        <p>POSITIONS {state.positions} · OPPORTUNITIES {state.opportunities}</p>
        <p>A04 DECISIONS {state.a04_decisions} · PORTFOLIO BRAIN DECISIONS {state.portfolio_decisions}</p>
      </Card>
      <Card title="Agents / R&D">
        <p>HARNESS {state.harness} · OPENROUTER {state.openrouter}</p>
        <p>ACTIVE AGENTS {state.active_agents.join(", ") || "NONE"}</p>
        <p>CHAMPION {state.champion ?? "NOT PROMOTED"}</p>
        <p>CHALLENGERS {state.challengers.join(", ") || "NONE"}</p>
        <p>R&D EXPERIMENTS {state.experiments.join(", ") || "NONE"}</p>
      </Card>
      <Card title="Recent Activity">
        {state.activity.length ? <ul>{state.activity.map((item) => <li key={item}>{item}</li>)}</ul> : <EmptyState message="No recorded activity" hint="UNKNOWN is never treated as healthy." />}
      </Card>
      <Card title="Evidence-backed Agent Chat">
        <p>Answers cite recorded candidate, thesis, position, allocation, risk, event, strategy, or experiment evidence.</p>
        <p>Requested changes create a RuntimeChangeProposal. Chat cannot place orders or mutate risk.</p>
        <label htmlFor="agent-question">Question</label>
        <input id="agent-question" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={!onChat} placeholder={onChat ? "Ask ATS about recorded evidence" : "Agent chat provider not attached"} style={{ width: "100%" }} />
        <button type="button" disabled={!onChat || !question.trim()} onClick={() => void ask()}>Ask</button>
        {answer ? <div role="status"><p>{answer.answer}</p><p>AUTHORITY {answer.authority}</p><p>EVIDENCE {answer.evidence_refs.join(", ") || "NONE"}</p>{answer.proposal_id ? <p>PROPOSAL {answer.proposal_id}</p> : null}</div> : null}
        {chatError ? <p role="alert">{chatError}</p> : null}
      </Card>
      <Card title="A2 Paper Controls">
        <p>All controls enter deterministic runtime authority. No live-money control exists.</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {(["SAFE", "NORMAL", "AGGRESSIVE"] as const).map((mode) => <button key={mode} type="button" disabled={!onCommand} onClick={() => void onCommand?.({ command: "SET_MODE", mode })}>{mode}</button>)}
          <button type="button" disabled={!onCommand} onClick={() => void onCommand?.({ command: "PAUSE_NEW_ENTRIES" })}>PAUSE NEW ENTRIES</button>
          <button type="button" disabled={!onCommand} onClick={() => void onCommand?.({ command: "RESUME_NEW_ENTRIES" })}>RESUME</button>
          <button type="button" disabled={!onCommand} onClick={() => void onCommand?.({ command: "FLATTEN_PORTFOLIO" })}>FLATTEN</button>
          <button type="button" disabled={!onCommand} onClick={() => void onCommand?.({ command: "HALT_SYSTEM" })}>HALT</button>
        </div>
      </Card>
    </section>
  );
}

export const UNKNOWN_CONTROL_PLANE: Overview = {
  system: "UNKNOWN", session: "UNKNOWN", feed: "UNKNOWN", broker: "UNKNOWN",
  user_mode: "SAFE", effective_mode: "SAFE", mode_reason: "CONTROL_PLANE_NOT_ATTACHED",
  underlyings: [
    { symbol: "NIFTY", price: null, freshness: "UNKNOWN" },
    { symbol: "BANKNIFTY", price: null, freshness: "UNKNOWN" },
  ],
  capital: { total: null, deployable: null, available: null, reserved: null, inflight: null, committed: null },
  pnl: { realized: null, unrealized: null, hwm: null, drawdown: null },
  positions: 0, opportunities: 0, a04_decisions: 0, portfolio_decisions: 0,
  harness: "UNKNOWN", openrouter: "UNKNOWN", active_agents: [], champion: null,
  challengers: [], experiments: [], activity: [],
};
