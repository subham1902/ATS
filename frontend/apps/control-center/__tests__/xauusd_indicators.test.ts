import { describe, it, expect } from "vitest";
import { wilderAtr, computeAtr, computeVwap } from "../components/xauusd-chart/indicators";
import type { UTCTimestamp } from "lightweight-charts";

describe("XAUUSD indicator truth", () => {
  it("uses Wilder seed, gaps and recursive smoothing", () => {
    const bars = [
      { high: 11, low: 9, close: 10 },
      { high: 14, low: 11, close: 13 },
      { high: 14, low: 12, close: 13 },
      { high: 18, low: 15, close: 17 },
    ];
    const atr = wilderAtr(bars, 3);
    expect(atr.slice(0, 2)).toEqual([null, null]);
    expect(atr[2]).toBeCloseTo(8 / 3);
    expect(atr[3]).toBeCloseTo(((8 / 3) * 2 + 5) / 3);
    expect(computeAtr(bars, 3)).toBe(atr[3]);
  });
  it("keeps warmup and unobserved volume unknown", () => {
    expect(computeAtr([{ high: 11, low: 9, close: 10 }])).toBeNull();
    expect(
      computeVwap([{ time: 1 as UTCTimestamp, high: 11, low: 9, close: 10 }], [{ value: null }])[0].value,
    ).toBeNull();
    expect(() => wilderAtr([], 0)).toThrow("INVALID_ATR_PERIOD");
  });
});
