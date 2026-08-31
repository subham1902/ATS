"use client";

import { useMemo, useState } from "react";
import type { StreamEvent } from "@ats/api-client";
import { formatTimeIST } from "../../lib/formatTime";

type Timeframe = 5 | 15 | 30 | 60;

interface PricePoint { time: number; price: number }

function extractPrices(events: StreamEvent[], symbol: string): PricePoint[] {
  const points: PricePoint[] = [];
  for (const event of events) {
    const kind = event.event_kind.toUpperCase();
    if (!kind.includes(symbol) && !kind.includes("PRICE") && !kind.includes("TICK") && !kind.includes("MARKET")) continue;
    const price = Number(event.payload.ltp ?? event.payload.last_price ?? event.payload.close ?? event.payload.price);
    if (!Number.isFinite(price) || price <= 0) continue;
    points.push({ time: new Date(event.occurred_at).getTime(), price });
  }
  return points;
}

export function LiveChart({ symbol, events }: { symbol: string; events: StreamEvent[] }) {
  const [timeframe, setTimeframe] = useState<Timeframe>(15);
  const allPoints = useMemo(() => extractPrices(events, symbol), [events, symbol]);
  const cutoff = Date.now() - timeframe * 60 * 1000;
  const points = useMemo(() => allPoints.filter((p) => p.time >= cutoff), [allPoints, cutoff]);

  if (points.length < 2) {
    return (
      <div className="lc-container">
        <div className="lc-header">
          <strong>{symbol} LIVE</strong>
          <div className="lc-timeframes">
            {([5, 15, 30, 60] as Timeframe[]).map((tf) => (
              <button key={tf} type="button" aria-pressed={timeframe === tf} onClick={() => setTimeframe(tf)}>{tf}m</button>
            ))}
          </div>
        </div>
        <div className="lc-empty">
          <span>Waiting for price data</span>
          <small>{allPoints.length} total events received</small>
        </div>
      </div>
    );
  }

  const min = Math.min(...points.map((p) => p.price));
  const max = Math.max(...points.map((p) => p.price));
  const span = Math.max(max - min, 0.01);
  const last = points[points.length - 1];
  const first = points[0];
  const change = last.price - first.price;
  const changePct = (change / first.price) * 100;

  const pathD = points.map((p, i) => {
    const x = 10 + (i / (points.length - 1)) * 780;
    const y = 10 + ((max - p.price) / span) * 130;
    return `${i === 0 ? "M" : "L"}${x},${y}`;
  }).join(" ");

  const areaD = `${pathD} L${10 + ((points.length - 1) / (points.length - 1)) * 780},150 L10,150 Z`;

  return (
    <div className="lc-container">
      <div className="lc-header">
        <div>
          <strong>{symbol} LIVE</strong>
          <span className="lc-last">₹{last.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
          <span className={change >= 0 ? "ats-positive" : "ats-negative"}>
            {change >= 0 ? "+" : ""}{change.toFixed(2)} ({changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%)
          </span>
        </div>
        <div className="lc-timeframes">
          {([5, 15, 30, 60] as Timeframe[]).map((tf) => (
            <button key={tf} type="button" aria-pressed={timeframe === tf} onClick={() => setTimeframe(tf)}>{tf}m</button>
          ))}
        </div>
      </div>
      <svg viewBox="0 0 800 150" className="lc-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id={`grad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={change >= 0 ? "#067647" : "#b42318"} stopOpacity="0.15" />
            <stop offset="100%" stopColor={change >= 0 ? "#067647" : "#b42318"} stopOpacity="0.01" />
          </linearGradient>
        </defs>
        <path d={areaD} fill={`url(#grad-${symbol})`} />
        <path d={pathD} fill="none" stroke={change >= 0 ? "#067647" : "#b42318"} strokeWidth="1.5" />
        <line x1="10" y1={10 + ((max - last.price) / span) * 130} x2="790" y2={10 + ((max - last.price) / span) * 130} stroke={change >= 0 ? "#067647" : "#b42318"} strokeDasharray="4 3" strokeWidth="0.5" />
        <circle cx={10 + ((points.length - 1) / (points.length - 1)) * 780} cy={10 + ((max - last.price) / span) * 130} r="3" fill={change >= 0 ? "#067647" : "#b42318"} />
      </svg>
      <div className="lc-footer">
        <span>{points.length} ticks</span>
        <span>{formatTimeIST(new Date(first.time).toISOString())} — {formatTimeIST(new Date(last.time).toISOString())}</span>
      </div>
    </div>
  );
}
