import { describe, expect, it } from "vitest";
import type { StreamEvent } from "@ats/api-client";
import { aggregateCandles, candlesFromEvents, chartMarkersFromEvents, eventInstrument, presenceFromEvents } from "../cockpitModel";

const event = (overrides: Partial<StreamEvent> = {}): StreamEvent => ({
  stream_event_id: "event-1",
  event_kind: "MARKET_SNAPSHOT",
  occurred_at: "2026-08-28T04:15:00.000Z",
  correlation_id: "correlation-1",
  payload: {},
  ...overrides,
});

describe("cockpit event projections", () => {
  it("builds candles only from complete authoritative OHLC events", () => {
    const valid = event({ payload: { underlying: "NIFTY", open: "100", high: 104, low: 99, close: 103, volume: 1200 } });
    const incomplete = event({ stream_event_id: "event-2", payload: { underlying: "NIFTY", close: 105 } });
    const wrong = event({ stream_event_id: "event-3", payload: { underlying: "BANKNIFTY", open: 1, high: 2, low: 1, close: 2 } });
    expect(candlesFromEvents([valid, incomplete, wrong], "NIFTY")).toEqual([{ eventId: "event-1", time: valid.occurred_at, open: 100, high: 104, low: 99, close: 103, volume: 1200 }]);
  });

  it("does not infer unsupported instruments", () => {
    expect(eventInstrument(event({ payload: { instrument_id: "RELIANCE" } }))).toBeNull();
    expect(eventInstrument(event({ payload: { instrument_id: "NSE_INDEX|Nifty Bank" } }))).toBe("BANKNIFTY");
    expect(eventInstrument(event({ payload: { instrument_id: "BANKNIFTY24AUG" } }))).toBe("BANKNIFTY");
  });

  it("moves presence only from matching typed/material events and expires to idle", () => {
    const position = event({ event_kind: "POSITION_MONITOR_DECISION", payload: { position_id: "p-1", reason_codes: ["SPREAD_WIDENING"] } });
    const neutral = event({ stream_event_id: "event-2", event_kind: "HEARTBEAT" });
    const active = presenceFromEvents([position, neutral], Date.parse(position.occurred_at) + 10_000);
    expect(active).toMatchObject([{ role: "POSITION", focus: "POSITION", focusId: "p-1", status: "ACTIVE" }]);
    expect(presenceFromEvents([position], Date.parse(position.occurred_at) + 31_000)[0]?.status).toBe("IDLE");
  });

  it("deduplicates candles by event id to make reconnect replay safe", () => {
    const duplicate = event({ payload: { symbol: "NIFTY", open: 1, high: 3, low: 1, close: 2 } });
    expect(candlesFromEvents([duplicate, duplicate], "NIFTY")).toHaveLength(1);
  });

  it("aggregates real one-minute bars without manufacturing missing bars", () => {
    const candles = [
      { eventId: "a", time: "2026-08-28T04:15:00Z", open: 100, high: 103, low: 99, close: 102, volume: 10 },
      { eventId: "b", time: "2026-08-28T04:16:00Z", open: 102, high: 105, low: 101, close: 104, volume: 20 },
    ];
    expect(aggregateCandles(candles, 3)).toEqual([{ eventId: "a+b", time: "2026-08-28T04:15:00.000Z", open: 100, high: 105, low: 99, close: 104, volume: 30 }]);
  });

  it("creates chart markers only from event-backed lifecycle records", () => {
    const fill = event({ event_kind: "POSITION_OPENED", payload: { underlying: "NIFTY", origin: "OPERATOR_MANUAL", fill_price: 101 } });
    const heartbeat = event({ stream_event_id: "event-2", event_kind: "HEARTBEAT", payload: { underlying: "NIFTY" } });
    expect(chartMarkersFromEvents([fill, heartbeat], "NIFTY")).toMatchObject([{ eventId: "event-1", label: "MANUAL ENTRY", price: 101 }]);
  });

  it("bounds high-volume streaming projections", () => {
    const stream = Array.from({ length: 10_000 }, (_, index) => event({
      stream_event_id: `event-${index}`,
      occurred_at: new Date(Date.parse("2026-08-28T04:15:00Z") + index * 60_000).toISOString(),
      event_kind: index % 20 === 0 ? "A04_DENY" : "MARKET_SNAPSHOT",
      payload: { underlying: "NIFTY", open: 100, high: 102, low: 99, close: 101, volume: 100 },
    }));
    expect(candlesFromEvents(stream, "NIFTY")).toHaveLength(120);
    expect(chartMarkersFromEvents(stream, "NIFTY")).toHaveLength(40);
    expect(presenceFromEvents(stream)).toHaveLength(1);
  });
});
