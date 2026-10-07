"use client";
import { useEffect, useMemo, useRef } from "react";
import { createChart, CandlestickSeries, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";
import { observedBars, type Candle } from "./candle-store";
import { computeAtr, computeRsi } from "./indicators";

export function XauUsdChart({ candles }: { candles: Candle[] }) {
  const container = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const bars = useMemo(() => observedBars(candles), [candles]);
  const hasBars = bars.length > 0;
  useEffect(() => {
    if (!container.current || !hasBars) return;
    const api = createChart(container.current, { height: 430, autoSize: true });
    chart.current = api;
    series.current = api.addSeries(CandlestickSeries);
    return () => {
      api.remove();
      chart.current = null;
      series.current = null;
    };
  }, [hasBars]);
  useEffect(() => {
    series.current?.setData(bars.map((bar) => ({ ...bar, time: bar.time as UTCTimestamp })));
  }, [bars]);
  const atr = computeAtr(bars);
  const rsi = computeRsi(bars);
  return (
    <section>
      <h2>XAUUSD chart</h2>
      <p>
        Observed broker bars. UTC. Wilder ATR: {atr?.toFixed(4) ?? "N/A"} · RSI: {rsi ?? "N/A"}
      </p>
      {!hasBars && <p>No candles observed.</p>}
      <div ref={container} aria-label="XAUUSD observed candlestick chart" />
    </section>
  );
}
