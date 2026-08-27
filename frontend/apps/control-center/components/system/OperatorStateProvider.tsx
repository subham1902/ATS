"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ActivityReadModel, RuntimeCommandRequest, RuntimeStatusReadModel, SystemReadModel } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import { useSse } from "../../hooks/useSse";
import type { CommandStatus, HarnessStatus, OperatorAlert, OperatorContextValue, PipelineStatus } from "./operatorTypes";

const EMPTY: OperatorContextValue = { system: null, runtime: null, pipeline: null, harness: null, activity: [], events: [], sseStatus: "disconnected", loading: true, error: null, lastRefreshAt: null, refresh: async () => {}, command: async () => false, commandStatus: { state: "idle", message: null }, alerts: [], dismissAlert: () => {} };
const OperatorContext = createContext<OperatorContextValue>(EMPTY);
const asPromise = <T,>(value: unknown) => value as Promise<T>;

function eventAlert(event: { stream_event_id: string; event_kind: string; occurred_at: string }): OperatorAlert | null {
  const kind = event.event_kind.toUpperCase();
  const table: Array<[string, OperatorAlert["severity"], string, string]> = [
    ["FEED_STALE", "critical", "Market feed is stale", "/"], ["SESSION", "info", "Session state changed", "/activity"],
    ["DEESCALAT", "warning", "Trading mode auto-de-escalated", "/risk"], ["DENY", "warning", "A04 denied an opportunity", "/governance"],
    ["CAPITAL", "warning", "Capital limit reached", "/risk"], ["STOP", "critical", "Position stop triggered", "/positions"],
    ["FILL", "info", "Paper fill recorded", "/activity"], ["POSITION_CLOSED", "info", "Position exited", "/activity"],
  ];
  const match = table.find(([needle]) => kind.includes(needle));
  return match ? { id: event.stream_event_id, severity: match[1], title: match[2], detail: event.event_kind, href: match[3], dismissible: match[1] !== "critical", occurredAt: event.occurred_at } : null;
}

export function OperatorStateProvider({ children }: { children: React.ReactNode }) {
  const client = useMemo(() => getApiClient(), []);
  const [system, setSystem] = useState<SystemReadModel | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatusReadModel | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [harness, setHarness] = useState<HarnessStatus | null>(null);
  const [activity, setActivity] = useState<ActivityReadModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<string | null>(null);
  const [commandStatus, setCommandStatus] = useState<CommandStatus>({ state: "idle", message: null });
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const { status: sseStatus, events, error: sseError } = useSse();
  const refreshTimer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([client.getSystem(), client.getRuntimeStatus(), asPromise<PipelineStatus>(client.getPipelineCounters()), asPromise<HarnessStatus>(client.getHarnessStatus()), client.getActivity()]);
    const [systemResult, runtimeResult, pipelineResult, harnessResult, activityResult] = results;
    if (systemResult.status === "fulfilled") setSystem(systemResult.value);
    if (runtimeResult.status === "fulfilled") setRuntime(runtimeResult.value);
    if (pipelineResult.status === "fulfilled") setPipeline(pipelineResult.value);
    if (harnessResult.status === "fulfilled") setHarness(harnessResult.value);
    if (activityResult.status === "fulfilled") setActivity(activityResult.value.items.slice(0, 200));
    const failures = results.filter((item) => item.status === "rejected").length;
    setError(failures === results.length ? "Control plane unavailable" : failures ? `${failures} operator data source${failures === 1 ? "" : "s"} unavailable` : null);
    setLastRefreshAt(new Date().toISOString());
    setLoading(false);
  }, [client]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!events.length) return;
    if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(() => void refresh(), 180);
    return () => { if (refreshTimer.current) window.clearTimeout(refreshTimer.current); };
  }, [events.length, refresh]);

  const command = useCallback(async (request: RuntimeCommandRequest) => {
    setCommandStatus({ state: "submitting", message: null });
    try {
      const result = await client.runtimeCommand(request);
      setCommandStatus({ state: result.accepted ? "success" : "error", message: result.accepted ? `${request.command.replaceAll("_", " ")} accepted by runtime` : (result.reason_codes.join(", ") || "Runtime rejected the command") });
      await refresh();
      return result.accepted;
    } catch (reason) {
      setCommandStatus({ state: "error", message: reason instanceof Error ? reason.message : "Runtime command unavailable" });
      return false;
    }
  }, [client, refresh]);

  const alerts = useMemo(() => {
    const derived: OperatorAlert[] = [];
    if (runtime && !runtime.feed_healthy) derived.push({ id: "feed-stale", severity: "critical", title: "Market feed degraded", detail: "New-entry decisions remain governed by runtime freshness rules.", href: "/", dismissible: false });
    if (runtime?.trading_mode.deescalation_reason) derived.push({ id: `mode-${runtime.trading_mode.deescalation_reason}`, severity: "warning", title: "Effective mode reduced", detail: runtime.trading_mode.deescalation_reason, href: "/risk", dismissible: true });
    if (harness && harness.harness.state !== "HEALTHY") derived.push({ id: "harness-offline", severity: harness.harness.state === "STOPPED" ? "warning" : "critical", title: "Harness unavailable", detail: (harness.harness.reason_codes ?? []).join(", ") || harness.harness.state, href: "/harness", dismissible: true });
    for (const event of events.slice(-30).reverse()) { const alert = eventAlert(event); if (alert) derived.push(alert); }
    const unique = new Map<string, OperatorAlert>();
    for (const alert of derived) if (!dismissed.has(alert.id) && !unique.has(`${alert.title}:${alert.detail}`)) unique.set(`${alert.title}:${alert.detail}`, alert);
    const rank = { critical: 0, warning: 1, info: 2 };
    return [...unique.values()].sort((a, b) => rank[a.severity] - rank[b.severity]).slice(0, 4);
  }, [dismissed, events, harness, runtime]);
  const dismissAlert = useCallback((id: string) => setDismissed((current) => new Set(current).add(id)), []);

  const value = useMemo<OperatorContextValue>(() => ({ system, runtime, pipeline, harness, activity, events, sseStatus, loading, error: error ?? sseError, lastRefreshAt, refresh, command, commandStatus, alerts, dismissAlert }), [system, runtime, pipeline, harness, activity, events, sseStatus, loading, error, sseError, lastRefreshAt, refresh, command, commandStatus, alerts, dismissAlert]);
  return <OperatorContext.Provider value={value}>{children}</OperatorContext.Provider>;
}

export function useOperatorState() { return useContext(OperatorContext); }
