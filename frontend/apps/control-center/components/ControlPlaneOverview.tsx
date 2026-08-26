"use client";

import type { ControlPlaneOverview as Overview } from "@ats/api-client";
import { Card, DetailField, EmptyState } from "@ats/ui";

const shown = (value: string | null) => value ?? "UNKNOWN";

export function ControlPlaneOverview({ state }: { state: Overview }) {
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
        <input id="agent-question" disabled placeholder="Agent chat provider not attached" style={{ width: "100%" }} />
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
  capital: { total: null, available: null, reserved: null, inflight: null, committed: null },
  pnl: { realized: null, unrealized: null, hwm: null, drawdown: null },
  positions: 0, opportunities: 0, a04_decisions: 0, portfolio_decisions: 0,
  harness: "UNKNOWN", openrouter: "UNKNOWN", active_agents: [], champion: null,
  challengers: [], experiments: [], activity: [],
};
