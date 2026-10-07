export interface Candle {
  bar_start: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string | null;
  volume: string | null;
  is_closed: boolean;
}
export function observedBars(candles: Candle[]) {
  return candles
    .flatMap((c) => {
      if ([c.open, c.high, c.low, c.close].some((value) => value === null || !Number.isFinite(Number(value))))
        return [];
      const time = Date.parse(c.bar_start) / 1000;
      if (!Number.isFinite(time)) return [];
      return [{ time, open: Number(c.open), high: Number(c.high), low: Number(c.low), close: Number(c.close) }];
    })
    .sort((a, b) => a.time - b.time);
}
