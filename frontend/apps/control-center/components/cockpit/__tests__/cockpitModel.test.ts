import { describe, expect, it } from "vitest";
import type { StreamEvent } from "@ats/api-client";
import { candlesFromEvents, eventInstrument, presenceFromEvents } from "../cockpitModel";

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
});
