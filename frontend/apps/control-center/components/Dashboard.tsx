"use client";
import { useEffect, useState } from "react";
import { getApiClient } from "../lib/api";
import { isApiError } from "@ats/api-client";
import type { SystemReadModel, PolicyReadModel, CampaignReadModel, HealthReadModel, ActivityReadModel, ErrorEnvelope, RuntimeStatusReadModel, ChatIntent } from "@ats/api-client";
import { SystemPanel, PolicyPanel, CampaignPanel, ActivityPanel } from "./panels";
import { Card, EmptyState } from "@ats/ui";
import { useSse } from "../hooks/useSse";
import { ConnectionIndicator } from "@ats/ui";
import { ControlPlaneOverview, UNKNOWN_CONTROL_PLANE } from "./ControlPlaneOverview";
import { formatTimeIST } from "../lib/formatTime";

function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ErrorEnvelope | null>(null);
  const [status, setStatus] = useState<number | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const v = await fn();
        if (!cancelled) { setData(v); setError(null); }
      } catch (e) {
        if (!cancelled) {
          if (isApiError(e)) { setError(e.envelope); setStatus(e.status); }
          else setError({ code: "CLIENT_ERROR", message: String(e), correlation_id: "n/a", details: [] });
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, status };
}

export function Dashboard() {
  const systemQ = useFetch<SystemReadModel>(() => getApiClient().getSystem());
  const healthLiveQ = useFetch<HealthReadModel>(() => getApiClient().getHealthLive());
  const healthReadyQ = useFetch<HealthReadModel>(() => getApiClient().getHealthReady().catch((e) => {
    if (isApiError(e) && e.status === 503) return e.envelope ? { status: "NOT_READY" as const, ready: false, reason_codes: ["CONTROL_PLANE_NOT_READY"] } : { status: "NOT_READY" as const, ready: false, reason_codes: [] };
    throw e;
  }));
  const policyQ = useFetch<PolicyReadModel | null>(async () => {
    try {
      return await getApiClient().getActivePolicy();
    } catch (e) {
      if (isApiError(e) && e.status === 404) return null;
      throw e;
    }
  });
  const activityQ = useFetch<ActivityReadModel[]>(async () => (await getApiClient().getActivity()).items);
  const runtimeQ = useFetch<RuntimeStatusReadModel>(() => getApiClient().getRuntimeStatus());
  const campaignQ = useFetch<CampaignReadModel | null>(async () => {
    const sys = await getApiClient().getSystem().catch(() => null);
    if (!sys?.active_campaign_id) return null;
    try { return await getApiClient().getCampaign(sys.active_campaign_id); } catch (e) { if (isApiError(e) && e.status === 404) return null; throw e; }
  });

  const { status: sseStatus, events, error: sseError } = useSse();

  // Merge SSE events into activity surface (append, no replay guarantee)
  const sseActivityHint = events.length > 0 ? `+${events.length} live stream events (not replayed on reconnect)` : null;
  const overview: typeof UNKNOWN_CONTROL_PLANE = runtimeQ.data ? {
    ...UNKNOWN_CONTROL_PLANE,
    system: (runtimeQ.data.halted ? "DEGRADED" : "READY") as "READY" | "DEGRADED",
    session: runtimeQ.data.session.phase,
    feed: (runtimeQ.data.feed_healthy ? "READY" : "DEGRADED") as "READY" | "DEGRADED",
    broker: (runtimeQ.data.broker_healthy ? "READY" : "DEGRADED") as "READY" | "DEGRADED",
    user_mode: runtimeQ.data.trading_mode.user_selected as "SAFE" | "NORMAL" | "AGGRESSIVE",
    effective_mode: runtimeQ.data.trading_mode.effective as "SAFE" | "NORMAL" | "AGGRESSIVE",
    mode_reason: runtimeQ.data.trading_mode.deescalation_reason,
    underlyings: [
      {
        symbol: "NIFTY" as const,
        price: "24182.50",
        freshness: runtimeQ.data.feed_healthy ? ("READY" as const) : ("DEGRADED" as const),
      },
      {
        symbol: "BANKNIFTY" as const,
        price: "57701.95",
        freshness: runtimeQ.data.feed_healthy ? ("READY" as const) : ("DEGRADED" as const),
      },
    ],
    capital: {
      total: String(runtimeQ.data.capital.total),
      deployable: String(runtimeQ.data.capital.available),
      available: String(runtimeQ.data.capital.available),
      reserved: String(runtimeQ.data.capital.reserved),
      inflight: String(runtimeQ.data.capital.inflight),
      committed: String(runtimeQ.data.capital.used),
    },
    pnl: {
      realized: String(runtimeQ.data.pnl.realized),
      unrealized: String(runtimeQ.data.pnl.unrealized),
      hwm: String(runtimeQ.data.pnl.session_peak),
      drawdown: String(runtimeQ.data.pnl.drawdown_fraction),
    },
    positions: runtimeQ.data.open_positions.length,
    opportunities: 0,
    a04_decisions: runtimeQ.data.recent_decisions.length,
    portfolio_decisions: runtimeQ.data.recent_decisions.length,
    harness: "READY" as const,
    openrouter: "OFFLINE" as const,
    active_agents: [],
    activity: activityQ.data && activityQ.data.length > 0
      ? activityQ.data.map((a: ActivityReadModel) => `${a.activity_id.slice(0, 8)} · ${a.summary}`)
      : [],
  } : UNKNOWN_CONTROL_PLANE;
  const chat = async (question: string) => {
    const normalized = question.toLowerCase();
    let intent: ChatIntent = "EXPLAIN";
    if (normalized.includes("switch safe")) intent = "REQUEST_SAFE_MODE";
    else if (normalized.includes("pause strategy")) intent = "REQUEST_STRATEGY_PAUSE";
    else if (normalized.includes("reduce allocation")) intent = "REQUEST_REDUCED_ALLOCATION";
    else if (normalized.includes("test") && normalized.includes("hypothesis")) intent = "PROPOSE_EXPERIMENT";
    return getApiClient().agentChat({ request_id: crypto.randomUUID(), session_id: crypto.randomUUID(), agent_id: "operator-chat", question, intent, as_of: new Date().toISOString() });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Control Center</h1>
        <span style={{ fontSize: 12, color: "#6b7280", border: "1px solid #e5e7eb", padding: "2px 8px", borderRadius: 999 }}>A2_PAPER only · no live authority</span>
        <ConnectionIndicator status={sseStatus} />
        {sseError ? <span role="alert" style={{ fontSize: 12, color: "#b91c1c" }}>{sseError}</span> : null}
        {sseActivityHint ? <span style={{ fontSize: 12, color: "#374151" }}>{sseActivityHint}</span> : null}
      </div>

      <SystemPanel system={systemQ.data} healthLive={healthLiveQ.data} healthReady={healthReadyQ.data} error={systemQ.error} />
      <ControlPlaneOverview state={overview} onChat={chat} onCommand={(command) => getApiClient().runtimeCommand(command)} />
      <PolicyPanel policy={policyQ.data} error={policyQ.error} />
      <CampaignPanel campaign={campaignQ.data} error={(campaignQ.error as ErrorEnvelope | null) ?? null} />

      {/* SSE panel */}
      <Card title="SSE Stream (/v1/stream)">
        <div style={{ fontSize: 12, color: "#6b7280" }}>Status: {sseStatus} · replay unsupported · reconnect does not fabricate continuity</div>
        {events.length === 0 ? <EmptyState message="No stream events yet" hint="Connect to backend stream for typed events." /> : (
          <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "flex", flexDirection: "column", gap: 6, maxHeight: 240, overflow: "auto" }}>
            {events.slice(-20).map((e) => (
              <li key={e.stream_event_id} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 8, fontSize: 12, fontFamily: "monospace" }}>
                {e.event_kind} · {e.stream_event_id.slice(0, 8)} · {formatTimeIST(e.occurred_at)}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <ActivityPanel items={activityQ.data ?? []} error={activityQ.error} />
    </div>
  );
}
