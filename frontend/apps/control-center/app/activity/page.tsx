"use client";

import { useMemo, useState } from "react";
import { useOperatorState } from "../../components/system/OperatorStateProvider";
import { EmptyState, Panel } from "../../components/system/SurfaceStates";
import { StatusBadge } from "../../components/system/SystemHealthIndicator";
import { formatTimeIST } from "../../lib/formatTime";

type Filter = "all" | "trading" | "risk" | "market" | "agent" | "research";
const category = (kind: string): Exclude<Filter, "all"> => { const value = kind.toUpperCase(); if (/RISK|A04|GOVERN|CAPITAL|HALT|STOP/.test(value)) return "risk"; if (/MARKET|SESSION|FEED|TICK/.test(value)) return "market"; if (/AGENT|HARNESS|ADVIS/.test(value)) return "agent"; if (/RESEARCH|EXPERIMENT|STRATEGY|PROMOTION/.test(value)) return "research"; return "trading"; };
export default function ActivityPage() {
  const { activity, events, sseStatus } = useOperatorState(); const [filter, setFilter] = useState<Filter>("all");
  const items = useMemo(() => { const merged = [...activity.map((item) => ({ id: item.activity_id, kind: item.event_kind, at: item.occurred_at, summary: item.summary, correlation: item.correlation_id, source: "RECORDED" })), ...events.map((item) => ({ id: item.stream_event_id, kind: item.event_kind, at: item.occurred_at, summary: String(item.payload.summary ?? item.event_kind), correlation: item.correlation_id, source: "STREAM" }))]; const unique = new Map(merged.map((item) => [item.id, item])); return [...unique.values()].filter((item) => filter === "all" || category(item.kind) === filter).sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 200); }, [activity, events, filter]);
  return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">CHRONOLOGICAL EVIDENCE</span><h1>Activity</h1><p>Market, candidate, Portfolio Brain, A04, paper execution, Harness, and research events.</p></div><StatusBadge state={sseStatus === "connected" ? "ACTIVE" : sseStatus === "connecting" ? "DEGRADED" : "OFFLINE"}>STREAM</StatusBadge></div>
    <Panel title="Unified event feed" eyebrow="BOUNDED TO 200 EVENTS" actions={<div className="activity-filters" role="group" aria-label="Activity filters">{(["all", "trading", "risk", "market", "agent", "research"] as Filter[]).map((item) => <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}>{item}</button>)}</div>}>{items.length ? <ol className="unified-feed">{items.map((item) => <li key={item.id} data-category={category(item.kind)}><time dateTime={item.at}>{formatTimeIST(item.at)}</time><span className="feed-node" aria-hidden="true" /><div><header><StatusBadge state={item.source === "STREAM" ? "ACTIVE" : "READY"}>{category(item.kind).toUpperCase()}</StatusBadge><strong>{item.kind.replaceAll("_", " ")}</strong><small>{item.source}</small></header><p>{item.summary}</p><code>{item.correlation}</code></div></li>)}</ol> : <EmptyState title={`No ${filter === "all" ? "runtime" : filter} activity`} detail="No matching canonical events are present in the current bounded history." />}</Panel>
  </div>;
}
