import { describe, expect, it } from "vitest";
import type { StreamEvent } from "@ats/api-client";
import { optionsFromEvents } from "../TradeTicket";

const optionEvent: StreamEvent = {
  stream_event_id: "option-event-1",
  event_kind: "OPTION_QUOTE_UPDATED",
  occurred_at: "2026-08-28T06:00:00Z",
  correlation_id: "correlation-1",
  payload: {
    underlying: "NIFTY",
    instrument_key: "NSE_FO|key",
    expiry: "2026-09-03",
    strike: "25000",
    option_type: "CE",
    lot_size: 50,
    tick_size: "0.05",
    ltp: "100",
    bid: "99.5",
    ask: "100.5",
  },
};

describe("provider-derived trade ticket evidence", () => {
  it("projects a complete provider option without guessing fields", () => {
    expect(optionsFromEvents([optionEvent], "NIFTY")).toMatchObject([
      {
        eventId: "option-event-1",
        instrumentKey: "NSE_FO|key",
        expiry: "2026-09-03",
        strike: 25000,
        optionType: "CE",
        lotSize: 50,
        ltp: 100,
      },
    ]);
  });

  it("rejects incomplete and wrong-underlying events", () => {
    const incomplete = { ...optionEvent, payload: { underlying: "NIFTY", ltp: 100 } };
    expect(optionsFromEvents([incomplete, optionEvent], "BANKNIFTY")).toEqual([]);
  });

  it("deduplicates reconnect replay by provider instrument key", () => {
    const newer = { ...optionEvent, stream_event_id: "option-event-2", payload: { ...optionEvent.payload, ltp: 101 } };
    expect(optionsFromEvents([optionEvent, newer], "NIFTY")).toMatchObject([{ eventId: "option-event-2", ltp: 101 }]);
  });
});
