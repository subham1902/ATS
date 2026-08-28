"use client";

import { useMemo } from "react";
import type { CandlePoint, CockpitInstrument } from "./cockpitModel";

export function TruthChart({ instrument, candles }: { instrument: CockpitInstrument; candles: CandlePoint[] }) {
  const geometry = useMemo(() => {
    if (!candles.length) return [];
    const min = Math.min(...candles.map((item) => item.low));
    const max = Math.max(...candles.map((item) => item.high));
    const span = Math.max(max - min, 0.01);
    return candles.map((item, index) => ({ ...item, x: 18 + index * (764 / Math.max(candles.length - 1, 1)), yo: 282 - ((item.open - min) / span) * 244, yc: 282 - ((item.close - min) / span) * 244, yh: 282 - ((item.high - min) / span) * 244, yl: 282 - ((item.low - min) / span) * 244 }));
  }, [candles]);
  return <section className="cockpit-chart" aria-label={`${instrument} authoritative live chart`} data-anchor="MARKET">
    <header><div><strong>{instrument}</strong><span>1m · EVENT-BACKED</span></div><div className="chart-tools" aria-label="Chart timeframe"><button aria-pressed="true">1m</button><button disabled title="Unavailable from current stream">3m</button><button disabled>5m</button><button disabled>15m</button></div></header>
    {geometry.length ? <svg viewBox="0 0 800 310" role="img" aria-label={`${geometry.length} authoritative candles`} preserveAspectRatio="none">
      <g className="chart-grid"><path d="M0 60H800M0 120H800M0 180H800M0 240H800" /></g>
      {geometry.map((item) => <g key={item.eventId} className={item.close >= item.open ? "candle-up" : "candle-down"}><title>{`${item.time}: O ${item.open} H ${item.high} L ${item.low} C ${item.close} · ${item.eventId}`}</title><line x1={item.x} y1={item.yh} x2={item.x} y2={item.yl} /><rect x={item.x - 3} y={Math.min(item.yo, item.yc)} width="6" height={Math.max(Math.abs(item.yo - item.yc), 1)} /></g>)}
    </svg> : <div className="chart-empty"><span>⌁</span><strong>LIVE CANDLES UNAVAILABLE</strong><p>The current SSE stream has not published authoritative OHLC events for {instrument}. ATS will not manufacture chart movement.</p></div>}
  </section>;
}
