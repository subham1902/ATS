import { describe, it, expect } from "vitest";
import type { CandleSeriesView, CandleView, FeedHealthView } from "@ats/api-client";
import { chartBarsFromCandles, evaluateChartProvenance, type ChartBarsResult } from "../provenance";

function candle(overrides: Partial<CandleView> = {}): CandleView {
  return {
    bar_start: "2026-09-29T09:15:00.000Z",
    bar_close: "2026-09-29T09:20:00.000Z",
    open: "100",
    high: "102",
    low: "99",
    close: "101",
    volume: 1500,
    open_interest: null,
    tick_count: 12,
    is_closed: true,
    ...overrides,
  };
}

function series(overrides: Partial<CandleSeriesView> = {}): CandleSeriesView {
  return {
    instrument_key: "MCX_FO|569003",
    contract: null,
    interval: "5m",
    state: "LIVE",
    bar_alignment_offset_minutes: 0,
    bar_alignment_note: "",
    source: "BROKER",
    authority_class: "LIVE_FEED_ATTACHED",
    candles: [],
    reason_codes: [],
    ...overrides,
  };
}

function health(overrides: Partial<FeedHealthView> = {}): FeedHealthView {
  return {
    state: "LIVE",
    attached: true,
    source: "BROKER",
    authority_class: "LIVE_FEED_ATTACHED",
    instruments: [],
    last_update_at: null,
    last_update_age_ms: null,
    stale_after_ms: 5000,
    accepted_updates: 1,
    dropped_duplicate: 0,
    dropped_out_of_order: 0,
    dropped_stale: 0,
    subscriber_count: 1,
    reason_codes: [],
    ...overrides,
  };
}

const barsOf = (n: number): ChartBarsResult => ({
  bars: Array.from({ length: n }, (_, i) => ({
    time: 1000 + i * 300,
    open: 100,
    high: 101,
    low: 99,
    close: 100.5,
    volume: 10,
  })),
  skippedBars: 0,
  missingVolumeBars: 0,
});

describe("chartBarsFromCandles", () => {
  it("keeps fully-observed bars and sorts by time", () => {
    const result = chartBarsFromCandles([
      candle({ bar_start: "2026-09-29T09:20:00.000Z", close: "102" }),
      candle({ bar_start: "2026-09-29T09:15:00.000Z", close: "101" }),
    ]);
    expect(result.bars).toHaveLength(2);
    expect(result.bars[0].close).toBe(101);
    expect(result.bars[1].close).toBe(102);
    expect(result.skippedBars).toBe(0);
  });

  it("skips bars with any missing OHLC leg instead of interpolating", () => {
    const result = chartBarsFromCandles([
      candle(),
      candle({ high: null }),
      candle({ close: "not-a-number" }),
      candle({ bar_start: "bogus", bar_close: "also-bogus" }),
    ]);
    expect(result.bars).toHaveLength(1);
    expect(result.skippedBars).toBe(3);
  });

  it("keeps bars with unknown volume and counts them, never filling a default", () => {
    const result = chartBarsFromCandles([candle({ volume: null }), candle({ volume: 5 })]);
    expect(result.bars).toHaveLength(2);
    expect(result.bars[0].volume).toBeNull();
    expect(result.bars[1].volume).toBe(5);
    expect(result.missingVolumeBars).toBe(1);
  });
});

describe("evaluateChartProvenance", () => {
  const live = {
    series: series(),
    health: health(),
    quoteState: "LIVE" as const,
    connectionStatus: "connected" as const,
    streamTransport: "WEBSOCKET" as const,
    requestedSource: "BROKER_LIVE" as const,
    bars: barsOf(3),
  };

  it("reports LIVE only with a live series, live health, and a live transport", () => {
    const p = evaluateChartProvenance(live);
    expect(p.status).toBe("LIVE");
    expect(p.actualSource).toBe("BROKER");
    expect(p.observedBars).toBe(3);
    expect(p.label).toContain("LIVE");
  });

  it("reports NO_FEED when nothing was observed and the transport is dead", () => {
    const p = evaluateChartProvenance({
      ...live,
      series: null,
      bars: barsOf(0),
      connectionStatus: "disconnected",
      streamTransport: "DISCONNECTED",
    });
    expect(p.status).toBe("NO_FEED");
    expect(p.observedBars).toBe(0);
  });

  it("reports frozen STALE history when the transport dropped after bars arrived", () => {
    const p = evaluateChartProvenance({
      ...live,
      connectionStatus: "disconnected",
      streamTransport: "DISCONNECTED",
    });
    expect(p.status).toBe("STALE");
    expect(p.observedBars).toBe(3);
    expect(p.detail).toMatch(/frozen/i);
  });

  it("never reports LIVE from a stale series", () => {
    const p = evaluateChartProvenance({ ...live, series: series({ state: "STALE" }) });
    expect(p.status).not.toBe("LIVE");
    expect(p.status).toBe("STALE");
  });

  it("treats unknown health as no veto when the series itself is live", () => {
    const p = evaluateChartProvenance({ ...live, health: health({ state: "UNKNOWN" }) });
    expect(p.status).toBe("LIVE");
    expect(p.actualSource).toBe("BROKER");
  });

  it("carries reason codes and the requested source through", () => {
    const p = evaluateChartProvenance({
      ...live,
      series: series({ reason_codes: ["DATA_STALE"] }),
      requestedSource: "OPEN_TERMINAL",
    });
    expect(p.requestedSource).toBe("OPEN_TERMINAL");
    expect(p.reasonCodes).toContain("DATA_STALE");
  });
});
