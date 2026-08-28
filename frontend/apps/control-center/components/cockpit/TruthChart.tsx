"use client";

import { useMemo, useState, type MouseEvent } from "react";
import { formatTimeIST } from "../../lib/formatTime";
import { aggregateCandles, type CandlePoint, type ChartMarker, type ChartTimeframe, type CockpitInstrument } from "./cockpitModel";

interface PositionOverlay { instrumentId: string; entry: number; current: number | null; stop: number | null; target: number | null; trailing: number | null; pnl: string; origin: string; exitMode: string }

export function TruthChart({ instrument, candles, markers, position, onEvidence }: { instrument: CockpitInstrument; candles: CandlePoint[]; markers: ChartMarker[]; position?: PositionOverlay; onEvidence: (eventId: string) => void }) {
  const [timeframe, setTimeframe] = useState<ChartTimeframe>(1);
  const [crosshair, setCrosshair] = useState<{ x: number; y: number } | null>(null);
  const visibleCandles = useMemo(() => aggregateCandles(candles, timeframe), [candles, timeframe]);
  const geometry = useMemo(() => {
    if (!visibleCandles.length) return { points: [], min: 0, max: 0, span: 1 };
    const overlayPrices = position ? [position.entry, position.current, position.stop, position.target, position.trailing].filter((item): item is number => item !== null) : [];
    const min = Math.min(...visibleCandles.map((item) => item.low), ...overlayPrices);
    const max = Math.max(...visibleCandles.map((item) => item.high), ...overlayPrices);
    const span = Math.max(max - min, 0.01);
    return { min, max, span, points: visibleCandles.map((item, index) => ({ ...item, x: 18 + index * (764 / Math.max(visibleCandles.length - 1, 1)), yo: 238 - ((item.open - min) / span) * 210, yc: 238 - ((item.close - min) / span) * 210, yh: 238 - ((item.high - min) / span) * 210, yl: 238 - ((item.low - min) / span) * 210 })) };
  }, [visibleCandles, position]);
  const yFor = (price: number) => 238 - ((price - geometry.min) / geometry.span) * 210;
  const maxVolume = Math.max(1, ...visibleCandles.map((item) => item.volume ?? 0));
  const last = visibleCandles.at(-1);
  const moveCrosshair = (event: MouseEvent<SVGSVGElement>) => { const rect = event.currentTarget.getBoundingClientRect(); setCrosshair({ x: ((event.clientX - rect.left) / rect.width) * 800, y: ((event.clientY - rect.top) / rect.height) * 310 }); };
  return <section className="cockpit-chart" aria-label={`${instrument} authoritative live chart`} data-anchor="MARKET">
    <header><div><strong>{instrument}</strong><span>{timeframe}m · EVENT-BACKED{last ? ` · ${last.close.toLocaleString("en-IN")} · ${formatTimeIST(last.time)} IST` : ""}</span></div><div className="chart-tools" aria-label="Chart timeframe">{([1, 3, 5, 15] as ChartTimeframe[]).map((minutes) => <button key={minutes} type="button" aria-pressed={timeframe === minutes} disabled={!candles.length} onClick={() => setTimeframe(minutes)}>{minutes}m</button>)}</div></header>
    {geometry.points.length ? <svg viewBox="0 0 800 310" role="img" aria-label={`${geometry.points.length} authoritative ${timeframe} minute candles`} preserveAspectRatio="none" onMouseMove={moveCrosshair} onMouseLeave={() => setCrosshair(null)}>
      <g className="chart-grid"><path d="M0 60H800M0 120H800M0 180H800M0 240H800" /></g>
      {geometry.points.map((item) => <g key={item.eventId} className={item.close >= item.open ? "candle-up" : "candle-down"}><title>{`${formatTimeIST(item.time)} IST: O ${item.open} H ${item.high} L ${item.low} C ${item.close} · ${item.eventId}`}</title><line x1={item.x} y1={item.yh} x2={item.x} y2={item.yl} /><rect x={item.x - 3} y={Math.min(item.yo, item.yc)} width="6" height={Math.max(Math.abs(item.yo - item.yc), 1)} />{item.volume !== undefined ? <rect className="volume-bar" x={item.x - 3} y={304 - (item.volume / maxVolume) * 45} width="6" height={(item.volume / maxVolume) * 45} /> : null}</g>)}
      {last ? <g className="price-line"><line x1="0" y1={yFor(last.close)} x2="800" y2={yFor(last.close)} /><text x="744" y={yFor(last.close) - 4}>{last.close}</text></g> : null}
      {position ? [["ENTRY", position.entry], ["STOP", position.stop], ["TARGET", position.target], ["TRAIL", position.trailing]].map(([label, price]) => typeof price === "number" ? <g key={String(label)} className={`position-line position-${String(label).toLowerCase()}`}><line x1="0" y1={yFor(price)} x2="800" y2={yFor(price)} /><text x="4" y={yFor(price) - 3}>{label} {price}</text></g> : null) : null}
      {markers.map((marker) => { const idx = geometry.points.findIndex((point) => point.time >= marker.time); const x = geometry.points[Math.max(idx, 0)]?.x ?? 18; const y = marker.price === null ? 18 : yFor(marker.price); return <g key={marker.eventId} className={`chart-marker marker-${marker.tone}`} role="button" tabIndex={0} aria-label={`${marker.label}, open evidence ${marker.eventId}`} onClick={() => onEvidence(marker.eventId)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onEvidence(marker.eventId); }}><circle cx={x} cy={y} r="5" /><title>{`${marker.label} · ${marker.eventId}`}</title></g>; })}
      {crosshair ? <g className="chart-crosshair" aria-hidden="true"><line x1={crosshair.x} y1="0" x2={crosshair.x} y2="310" /><line x1="0" y1={crosshair.y} x2="800" y2={crosshair.y} /></g> : null}
    </svg> : <div className="chart-empty"><span>⌁</span><strong>LIVE CANDLES UNAVAILABLE</strong><p>The current SSE stream has not published authoritative OHLC events for {instrument}. ATS will not manufacture chart movement.</p></div>}
    {position ? <div className="chart-position-summary"><b>{position.origin === "OPERATOR_MANUAL" ? "MANUAL" : "ATS"} POSITION</b><span>{position.instrumentId}</span><span>P&amp;L {position.pnl}</span><span>{position.exitMode.replaceAll("_", " ")}</span></div> : null}
    {geometry.points.length && !visibleCandles.some((item) => item.volume !== undefined) ? <small className="chart-unavailable">VOLUME UNAVAILABLE — no authoritative volume fields received.</small> : null}
  </section>;
}
