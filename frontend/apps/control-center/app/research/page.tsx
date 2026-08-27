"use client";

import { useCallback, useEffect, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "../../components/system/SurfaceStates";
import { StatusBadge } from "../../components/system/SystemHealthIndicator";

export default function ResearchPage() {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | null>(null); const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { try { setSnapshot(await getApiClient().getOperatorIntelligence()); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Research evidence unavailable"); } }, []); useEffect(() => { void refresh(); }, [refresh]);
  const researchAgents = snapshot?.agents.filter((agent) => agent.role.toUpperCase().includes("RESEARCH")) ?? []; const researchEvents = snapshot?.timeline.filter((event) => /RESEARCH|EXPERIMENT|STRATEGY|PROMOTION|DEGRAD/.test(event.material_event.toUpperCase())) ?? [];
  return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">RESEARCH & DEVELOPMENT</span><h1>R&D</h1><p>Champion, challenger, experiment, scorecard, promotion, and degradation state.</p></div>{snapshot ? <StatusBadge state={snapshot.provenance === "LIVE" ? "ACTIVE" : "READY"}>{snapshot.provenance}</StatusBadge> : null}</div>{error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}{!snapshot && !error ? <LoadingState rows={5} /> : null}
    <div className="rnd-state-grid">{["Champion", "Challengers", "Experiments", "Scorecards", "Promotion", "Degradation"].map((label) => <Panel key={label} title={label} eyebrow="RECORDED STATE"><div className="rnd-state"><StatusBadge state="UNKNOWN">UNKNOWN</StatusBadge><p>No canonical {label.toLowerCase()} state is exposed by the current read model.</p></div></Panel>)}</div>
    <Panel title="Research agents" eyebrow="ADVISORY_ONLY">{researchAgents.length ? <div className="agent-card-grid">{researchAgents.map((agent) => <article key={agent.agent_id}><header><strong>{agent.role}</strong><StatusBadge state={agent.status === "ACTIVE" ? "ACTIVE" : agent.status === "OFFLINE" ? "OFFLINE" : "READY"}>{agent.status}</StatusBadge></header><p>{agent.recommendation ?? "No current recommendation"}</p><footer>{agent.evidence_refs.length} evidence refs · {agent.authority}</footer></article>)}</div> : <EmptyState title="No active research agent" detail="The current operator-intelligence snapshot contains no research advisory agent." />}</Panel>
    <Panel title="Research history" eyebrow="PROMOTION & DEGRADATION EVIDENCE">{researchEvents.length ? <ol className="unified-feed">{researchEvents.map((event) => <li key={event.event_id}><time dateTime={event.timestamp}>{event.timestamp}</time><span className="feed-node" /><div><strong>{event.material_event}</strong><p>{event.recommendation}</p></div></li>)}</ol> : <EmptyState title="No research lifecycle events" detail="No experiments, promotions, or degradation events are present in the current bounded timeline." />}</Panel>
  </div>;
}
