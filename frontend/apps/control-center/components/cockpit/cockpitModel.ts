import type { StreamEvent } from "@ats/api-client";

export type CockpitInstrument = "NIFTY" | "BANKNIFTY";
export type AgentRole = "MARKET" | "PORTFOLIO" | "POSITION" | "RESEARCH" | "SESSION";
export type AgentFocus = "MARKET" | "INSTRUMENT" | "OPPORTUNITY" | "POSITION" | "PORTFOLIO" | "RESEARCH" | "SESSION";

export interface CandlePoint { eventId: string; time: string; open: number; high: number; low: number; close: number; volume?: number }
export type ChartTimeframe = 1 | 3 | 5 | 15;
export interface ChartMarker { eventId: string; time: string; label: string; price: number | null; tone: "entry" | "exit" | "decision" }
export interface AgentPresence { eventId: string; role: AgentRole; focus: AgentFocus; focusId: string | null; activity: string; status: "ACTIVE" | "IDLE"; occurredAt: string; evidenceRefs: string[] }

const finite = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
const text = (value: unknown): string | null => typeof value === "string" && value.trim() ? value : null;

export function eventInstrument(event: StreamEvent): CockpitInstrument | null {
  const raw = text(event.payload.underlying) ?? text(event.payload.instrument_id) ?? text(event.payload.symbol);
  if (!raw) return null;
  const upper = raw.toUpperCase();
  if (upper.includes("BANKNIFTY") || upper.includes("NIFTY BANK")) return "BANKNIFTY";
  if (upper.includes("NIFTY")) return "NIFTY";
  return null;
}

export function candlesFromEvents(events: StreamEvent[], instrument: CockpitInstrument): CandlePoint[] {
  const unique = new Map<string, CandlePoint>();
  for (const event of events) {
    if (eventInstrument(event) !== instrument) continue;
    const open = finite(event.payload.open), high = finite(event.payload.high), low = finite(event.payload.low), close = finite(event.payload.close);
    if (open === null || high === null || low === null || close === null || high < low) continue;
    unique.set(event.stream_event_id, { eventId: event.stream_event_id, time: event.occurred_at, open, high, low, close, volume: finite(event.payload.volume) ?? undefined });
  }
  return [...unique.values()].sort((a, b) => a.time.localeCompare(b.time)).slice(-120);
}

export function aggregateCandles(candles: CandlePoint[], timeframe: ChartTimeframe): CandlePoint[] {
  if (timeframe === 1) return candles;
  const buckets = new Map<number, CandlePoint[]>();
  for (const candle of candles) {
    const timestamp = Date.parse(candle.time);
    if (!Number.isFinite(timestamp)) continue;
    const bucket = Math.floor(timestamp / (timeframe * 60_000)) * timeframe * 60_000;
    buckets.set(bucket, [...(buckets.get(bucket) ?? []), candle]);
  }
  return [...buckets.entries()].sort(([a], [b]) => a - b).map(([bucket, points]) => ({
    eventId: points.map((point) => point.eventId).join("+"), time: new Date(bucket).toISOString(),
    open: points[0].open, high: Math.max(...points.map((point) => point.high)),
    low: Math.min(...points.map((point) => point.low)), close: points.at(-1)!.close,
    volume: points.every((point) => point.volume === undefined) ? undefined : points.reduce((sum, point) => sum + (point.volume ?? 0), 0),
  }));
}

const MARKER_RULES: Array<[string, string, ChartMarker["tone"]]> = [
  ["SESSION_FLATTEN", "SESSION FLATTEN", "exit"], ["PARTIAL", "PARTIAL REDUCTION", "exit"],
  ["A04_DEN", "A04 DENY", "decision"], ["QUALIFIED", "C0 QUALIFIED", "decision"],
];

export function chartMarkersFromEvents(events: StreamEvent[], instrument: CockpitInstrument): ChartMarker[] {
  return events.flatMap((event) => {
    if (eventInstrument(event) !== instrument) return [];
    const kind = event.event_kind.toUpperCase();
    let rule = MARKER_RULES.find(([needle]) => kind.includes(needle));
    if (!rule && (kind.includes("POSITION_CLOSED") || kind.includes("EXIT_FILL"))) {
      const manual = text(event.payload.reason)?.includes("OPERATOR_MANUAL_EXIT") || text(event.payload.source)?.includes("OPERATOR");
      rule = [kind, manual ? "MANUAL EXIT" : "ATS EXIT", "exit"];
    } else if (!rule && (kind.includes("POSITION_OPEN") || kind.includes("FILL"))) {
      const manual = text(event.payload.origin) === "OPERATOR_MANUAL" || text(event.payload.source)?.includes("OPERATOR");
      rule = [kind, manual ? "MANUAL ENTRY" : "ATS ENTRY", "entry"];
    }
    if (!rule) return [];
    return [{ eventId: event.stream_event_id, time: event.occurred_at, label: rule[1], price: finite(event.payload.price) ?? finite(event.payload.fill_price) ?? finite(event.payload.mark_price), tone: rule[2] }];
  }).slice(-40);
}

const ROLE_BY_KIND: Array<[string, AgentRole, AgentFocus]> = [
  ["POSITION", "POSITION", "POSITION"], ["PORTFOLIO", "PORTFOLIO", "PORTFOLIO"],
  ["RESEARCH", "RESEARCH", "RESEARCH"], ["SHADOW", "RESEARCH", "RESEARCH"],
  ["SESSION", "SESSION", "SESSION"], ["CUTOFF", "SESSION", "SESSION"],
  ["MARKET", "MARKET", "MARKET"], ["REGIME", "MARKET", "MARKET"],
];

export function presenceFromEvents(events: StreamEvent[], nowMs = Date.now()): AgentPresence[] {
  const latest = new Map<AgentRole, AgentPresence>();
  for (const event of events) {
    const explicitRole = text(event.payload.agent_role)?.toUpperCase();
    const explicitFocus = text(event.payload.focus_type)?.toUpperCase();
    const inferred = ROLE_BY_KIND.find(([needle]) => event.event_kind.toUpperCase().includes(needle));
    const role = (["MARKET", "PORTFOLIO", "POSITION", "RESEARCH", "SESSION"].includes(explicitRole ?? "") ? explicitRole : inferred?.[1]) as AgentRole | undefined;
    const focus = (["MARKET", "INSTRUMENT", "OPPORTUNITY", "POSITION", "PORTFOLIO", "RESEARCH", "SESSION"].includes(explicitFocus ?? "") ? explicitFocus : inferred?.[2]) as AgentFocus | undefined;
    if (!role || !focus) continue;
    const age = nowMs - Date.parse(event.occurred_at);
    latest.set(role, { eventId: event.stream_event_id, role, focus, focusId: text(event.payload.focus_id) ?? text(event.payload.position_id) ?? text(event.payload.instrument_id), activity: text(event.payload.activity) ?? event.event_kind.replaceAll("_", " "), status: age >= 0 && age <= 30_000 ? "ACTIVE" : "IDLE", occurredAt: event.occurred_at, evidenceRefs: Array.isArray(event.payload.evidence_refs) ? event.payload.evidence_refs.filter((item): item is string => typeof item === "string") : [event.stream_event_id] });
  }
  return [...latest.values()];
}

export function explainEvent(event: StreamEvent): string {
  const reason = text(event.payload.reason) ?? text(event.payload.explanation);
  if (reason) return reason;
  const reasons = event.payload.reason_codes;
  if (Array.isArray(reasons) && reasons.length) return reasons.map(String).join(" · ").replaceAll("_", " ");
  return event.event_kind.replaceAll("_", " ");
}
