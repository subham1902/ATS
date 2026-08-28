"use client";

import Link from "next/link";
import { useMemo } from "react";
import { MetricStrip } from "../system/MetricStrip";
import { useOperatorState } from "../system/OperatorStateProvider";
import { EmptyState, ErrorState, LoadingState, Panel } from "../system/SurfaceStates";
import { StatusBadge } from "../system/SystemHealthIndicator";
import { MarketPanel } from "./MarketPanel";
import { formatTimeIST } from "../../lib/formatTime";

const amount = (value: string | undefined) => value === undefined ? "—" : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const pnl = (value: number) => `${value >= 0 ? "+" : "−"}₹${Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export function LiveOverview() {
  const state = useOperatorState();
  const { runtime, pipeline, harness, activity, loading, error, refresh } = state;
  const totalPnl = useMemo(() => Number(runtime?.pnl.realized ?? 0) + Number(runtime?.pnl.unrealized ?? 0), [runtime?.pnl.realized, runtime?.pnl.unrealized]);
  const decisionCounts = useMemo<Record<string, number>>(() => {
    const counts: Record<string, number> = {};
    for (const decision of runtime?.recent_decisions ?? []) {
      const key = String(decision.decision ?? decision.outcome ?? "RECORDED").toUpperCase();
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [runtime?.recent_decisions]);
  return <div className="ats-page overview-page">
    <div className="ats-page-heading"><div><span className="eyebrow">LIVE OPERATIONS</span><h1>Overview</h1><p>System truth, capital, opportunities, and active paper positions at a glance.</p></div><div className="page-provenance"><StatusBadge state={state.sseStatus === "connected" ? "ACTIVE" : state.sseStatus === "connecting" ? "DEGRADED" : "OFFLINE"}>LIVE STREAM</StatusBadge><span>A2_PAPER · no live authority</span></div></div>
    {error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}
    <MetricStrip items={[
      { label: "Session P&L", value: runtime ? pnl(totalPnl) : "—", tone: totalPnl > 0 ? "positive" : totalPnl < 0 ? "negative" : "neutral" },
      { label: "Available", value: amount(runtime?.capital.available) }, { label: "Committed", value: amount(runtime?.capital.used) },
      { label: "Drawdown", value: runtime ? `${(Number(runtime.pnl.drawdown_fraction) * 100).toFixed(2)}%` : "—", tone: Number(runtime?.pnl.drawdown_fraction ?? 0) > 0 ? "negative" : "neutral" },
      { label: "Positions", value: runtime?.open_positions.length ?? 0 }, { label: "Qualified", value: pipeline?.candidates_qualified ?? 0 },
    ]} />
    <div className="overview-grid"><MarketPanel />
      <Panel title="Capital posture" eyebrow="PORTFOLIO AUTHORITY" actions={<StatusBadge state={runtime?.loss_state === "NORMAL" ? "HEALTHY" : runtime?.loss_state === "HALTED" ? "HALTED" : runtime ? "DEGRADED" : "UNKNOWN"}>{runtime?.loss_state ?? "LOSS STATE"}</StatusBadge>} className="capital-panel">{loading && !runtime ? <LoadingState rows={4} /> : <div className="capital-bars"><div><span>Available</span><strong>{amount(runtime?.capital.available)}</strong></div><div><span>Reserved</span><strong>{amount(runtime?.capital.reserved)}</strong></div><div><span>Inflight</span><strong>{amount(runtime?.capital.inflight)}</strong></div><div><span>Committed</span><strong>{amount(runtime?.capital.used)}</strong></div><div className="capital-total"><span>Total paper capital</span><strong>{amount(runtime?.capital.total)}</strong></div></div>}</Panel>
      <Panel title="Live opportunities" eyebrow="R10 / R10-X FUNNEL" actions={<Link className="panel-link" href="/candidates">Open scanner →</Link>} className="opportunity-summary"><div className="funnel-mini"><div><strong>{pipeline?.candidates_considered ?? 0}</strong><span>Evaluated</span></div><i aria-hidden="true" /><div><strong>{Math.max(0, (pipeline?.candidates_considered ?? 0) - (pipeline?.candidates_qualified ?? 0))}</strong><span>Rejected</span></div><i aria-hidden="true" /><div className="qualified"><strong>{pipeline?.candidates_qualified ?? 0}</strong><span>Qualified</span></div></div>{!pipeline?.candidates_qualified ? <EmptyState title="No qualifying live opportunities" detail="The current pipeline has not produced a candidate that clears all governed checks." metrics={<span>{pipeline?.candidates_considered ?? 0} market theses evaluated · reasons remain in recorded evidence</span>} /> : <p className="calm-copy">Qualified candidates are awaiting or progressing through Portfolio Brain and A04 authority.</p>}</Panel>
      <Panel title="Open positions" eyebrow="PAPER BROKER" actions={<Link className="panel-link" href="/positions">View all →</Link>} className="positions-summary">{loading && !runtime ? <LoadingState rows={3} /> : runtime?.open_positions.length ? <div className="compact-table-wrap"><table className="ats-table"><thead><tr><th>Instrument</th><th>Qty</th><th>Entry</th><th>Mark</th><th>P&L</th></tr></thead><tbody>{runtime.open_positions.slice(0, 5).map((position) => <tr key={position.position_id}><th scope="row">{position.instrument_id}</th><td>{position.quantity}</td><td>{position.entry_price}</td><td>{position.mark_price ?? "—"}</td><td className={Number(position.unrealized_pnl) < 0 ? "ats-negative" : "ats-positive"}>{pnl(Number(position.unrealized_pnl))}</td></tr>)}</tbody></table></div> : <EmptyState title="No open paper positions" detail="ATS has no active exposure. New entries remain subject to session, Portfolio Brain, A04, risk, and capital authority." />}</Panel>
      <Panel title="Decision flow" eyebrow="GOVERNED PIPELINE" actions={<Link className="panel-link" href="/governance">Evidence →</Link>} className="decision-panel"><div className="decision-flow"><div><StatusBadge state={runtime?.feed_healthy ? "HEALTHY" : runtime ? "STALE" : "UNKNOWN"}>MARKET</StatusBadge><span>Fresh inputs</span></div><b aria-hidden="true">→</b><div><StatusBadge state={(pipeline?.candidates_considered ?? 0) > 0 ? "ACTIVE" : "READY"}>R10</StatusBadge><span>{pipeline?.candidates_considered ?? 0} evaluated</span></div><b aria-hidden="true">→</b><div><StatusBadge state={runtime?.recent_decisions.length ? "ACTIVE" : "READY"}>PORTFOLIO</StatusBadge><span>{runtime?.recent_decisions.length ?? 0} decisions</span></div><b aria-hidden="true">→</b><div><StatusBadge state={decisionCounts.DENY ? "DEGRADED" : "READY"}>A04</StatusBadge><span>{decisionCounts.DENY ?? 0} denied</span></div><b aria-hidden="true">→</b><div><StatusBadge state={runtime?.broker_healthy ? "HEALTHY" : runtime ? "DEGRADED" : "UNKNOWN"}>PAPER</StatusBadge><span>Execution target</span></div></div></Panel>
      <Panel title="Harness & agent activity" eyebrow="ADVISORY_ONLY" actions={<Link className="panel-link" href="/harness">Open console →</Link>} className="agents-panel"><div className="harness-summary"><StatusBadge state={harness?.harness.state === "HEALTHY" ? "HEALTHY" : harness?.harness.state === "STOPPED" ? "OFFLINE" : harness ? "DEGRADED" : "UNKNOWN"}>HARNESS</StatusBadge><strong>{harness?.llm?.primary_model ?? "Model unavailable"}</strong><span>{harness?.harness.active_sessions ?? 0} sessions · {harness?.agents.length ?? 0} agents</span></div><ol className="activity-mini">{activity.slice(0, 5).map((item) => <li key={item.activity_id}><span aria-hidden="true" /><div><strong>{item.event_kind.replaceAll("_", " ")}</strong><small>{item.summary}</small></div><time dateTime={item.occurred_at}>{formatTimeIST(item.occurred_at)}</time></li>)}</ol>{!activity.length ? <EmptyState title="No recent runtime activity" detail="Material events (regime transitions, fills, risk/loss alerts) appear here as recorded. Routine scanner evaluations are omitted to keep the stream high-signal." /> : null}</Panel>
    </div>
  </div>;
}
