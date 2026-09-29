import type { CandleSeriesView, CandleView, FeedHealthView, MarketDataState, SseStatus } from "@ats/api-client";
import type { RequestedSource } from "./dataSource";

/**
 * Chart data provenance: where every rendered bar came from and how fresh it is.
 *
 * The chart renders ONLY bars observed from the API. There is no synthetic
 * fallback series: when nothing was observed the chart shows an explicit empty
 * state instead of plausible-looking invented history.
 */
export type ChartProvenanceStatus = "LIVE" | "STALE" | "NO_FEED" | "UNKNOWN";

export interface ChartProvenance {
  status: ChartProvenanceStatus;
  /** What the operator asked for (a request, not a claim). */
  requestedSource: RequestedSource;
  /** What actually supplied the rendered bars, or null when there are none. */
  actualSource: string | null;
  authorityClass: string | null;
  /** Short human label, e.g. "LIVE · BROKER" or "NO FEED". */
  label: string;
  /** One-line explanation suitable for a tooltip or caption. */
  detail: string;
  observedBars: number;
  skippedBars: number;
  missingVolumeBars: number;
  reasonCodes: string[];
}

export interface ObservedBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface ChartBarsResult {
  bars: ObservedBar[];
  /** Bars dropped because at least one of open/high/low/close was missing or non-numeric. */
  skippedBars: number;
  /** Kept bars that carry no volume. Rendered as gaps, never filled in. */
  missingVolumeBars: number;
}

function toFiniteNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number.parseFloat(String(value));
  return Number.isFinite(n) ? n : null;
}

function toEpochSeconds(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

/**
 * Map API candles to chart bars, keeping only fully-observed OHLC bars.
 * A bar with any missing leg is skipped and counted, never interpolated.
 */
export function chartBarsFromCandles(candles: CandleView[]): ChartBarsResult {
  const bars: ObservedBar[] = [];
  let skippedBars = 0;
  let missingVolumeBars = 0;

  for (const candle of candles ?? []) {
    const time = toEpochSeconds(candle.bar_start ?? candle.bar_close);
    const open = toFiniteNumber(candle.open);
    const high = toFiniteNumber(candle.high);
    const low = toFiniteNumber(candle.low);
    const close = toFiniteNumber(candle.close);
    if (time === null || open === null || high === null || low === null || close === null) {
      skippedBars += 1;
      continue;
    }
    const volume = candle.volume ?? null;
    if (volume === null) missingVolumeBars += 1;
    bars.push({ time, open, high, low, close, volume });
  }

  bars.sort((a, b) => a.time - b.time);
  return { bars, skippedBars, missingVolumeBars };
}

export interface ProvenanceInputs {
  series: CandleSeriesView | null;
  health: FeedHealthView | null;
  quoteState: MarketDataState | null;
  connectionStatus: SseStatus;
  streamTransport: "WEBSOCKET" | "SSE" | "DISCONNECTED";
  requestedSource: RequestedSource;
  bars: ChartBarsResult;
}

function statusFromState(state: MarketDataState | null | undefined): ChartProvenanceStatus {
  if (state === "LIVE") return "LIVE";
  if (state === "STALE") return "STALE";
  if (state === "NO_FEED") return "NO_FEED";
  return "UNKNOWN";
}

/**
 * Decide what the chart may claim. Fail closed: no series, no health signal,
 * or a dead transport means NO_FEED or UNKNOWN, never LIVE.
 */
export function evaluateChartProvenance(inputs: ProvenanceInputs): ChartProvenance {
  const { series, health, connectionStatus, streamTransport, requestedSource, bars } = inputs;

  const transportDead = connectionStatus !== "connected" || streamTransport === "DISCONNECTED";
  const actualSource = series?.source ?? health?.source ?? null;
  const authorityClass = series?.authority_class ?? health?.authority_class ?? null;
  const reasonCodes = [...(series?.reason_codes ?? []), ...(health?.reason_codes ?? [])];

  if (!series || bars.bars.length === 0) {
    const status: ChartProvenanceStatus = transportDead ? "NO_FEED" : "UNKNOWN";
    return {
      status,
      requestedSource,
      actualSource,
      authorityClass,
      label: status === "NO_FEED" ? "NO FEED" : "NO DATA",
      detail:
        status === "NO_FEED"
          ? "No market connection. The chart shows nothing rather than invented history."
          : "The feed answered but supplied no usable bars. Nothing is rendered or interpolated.",
      observedBars: 0,
      skippedBars: bars.skippedBars,
      missingVolumeBars: bars.missingVolumeBars,
      reasonCodes,
    };
  }

  if (transportDead) {
    return {
      status: "STALE",
      requestedSource,
      actualSource,
      authorityClass,
      label: "STALE",
      detail: "The connection dropped. These are the last observed bars, frozen in place — not live prices.",
      observedBars: bars.bars.length,
      skippedBars: bars.skippedBars,
      missingVolumeBars: bars.missingVolumeBars,
      reasonCodes,
    };
  }

  const seriesStatus = statusFromState(series.state);
  const healthStatus = health ? statusFromState(health.state) : "UNKNOWN";
  const status: ChartProvenanceStatus =
    seriesStatus === "LIVE" && (healthStatus === "LIVE" || healthStatus === "UNKNOWN")
      ? "LIVE"
      : seriesStatus === "STALE" || healthStatus === "STALE"
        ? "STALE"
        : seriesStatus === "NO_FEED" || healthStatus === "NO_FEED"
          ? "NO_FEED"
          : "UNKNOWN";

  const sourceLabel = actualSource ?? "unknown feed";
  return {
    status,
    requestedSource,
    actualSource,
    authorityClass,
    label: status === "LIVE" ? `LIVE · ${sourceLabel}` : status,
    detail:
      status === "LIVE"
        ? `${bars.bars.length} observed bars from ${sourceLabel}.`
        : `Feed state is ${status}. Rendered bars are observed history, not live prices.`,
    observedBars: bars.bars.length,
    skippedBars: bars.skippedBars,
    missingVolumeBars: bars.missingVolumeBars,
    reasonCodes,
  };
}
