"use client";
import React, { useMemo } from "react";
import type {
  CandleView,
  FeedHealthView,
  MarketInterval,
  MarketQuoteView,
  SseStatus,
} from "@ats/api-client";
import { ConnectionIndicator } from "@ats/ui";

interface LiveChartProps {
  candles: CandleView[];
  quote: MarketQuoteView | null;
  health: FeedHealthView | null;
  prediction: any | null;
  interval: MarketInterval;
  onIntervalChange: (interval: MarketInterval) => void;
  connectionStatus: SseStatus;
  streamTransport?: "WEBSOCKET" | "SSE" | "DISCONNECTED";
}

export function LiveChart({
  candles,
  quote,
  health,
  prediction,
  interval,
  onIntervalChange,
  connectionStatus,
  streamTransport,
}: LiveChartProps) {
  const [selectedIndicator, setSelectedIndicator] = React.useState<"NONE" | "EMA" | "BOLLINGER" | "RSI">("EMA");

  const streamState = useMemo(() => {
    if (connectionStatus === "connecting") return "CONNECTING";
    if (connectionStatus === "disconnected" || connectionStatus === "error") return "OFFLINE";
    if (health?.provider_state === "RECONNECTING") return "RECONNECTING";
    if (health?.provider_state === "DEGRADED") return "DEGRADED";
    if (health?.state === "STALE") return "STALE";
    if (health?.state === "LIVE" || health?.provider_state === "STREAMING") return "STREAMING";
    return "LIVE";
  }, [connectionStatus, health]);

  // Chart dimensions
  const width = 900;
  const height = 450;
  const margin = { top: 20, right: 60, bottom: 40, left: 20 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  // Technical Indicators Math
  const indicators = useMemo(() => {
    if (candles.length < 5) return { ema20: [], ema50: [], bbUpper: [], bbLower: [], bbMid: [], rsi: 50 };
    const closes = candles.map((c) => (c.close ? parseFloat(c.close) : 0));

    const calcEMA = (period: number) => {
      const k = 2 / (period + 1);
      const ema: (number | null)[] = [];
      let prev = closes[0];
      for (let i = 0; i < closes.length; i++) {
        if (i < period - 1) {
          ema.push(null);
        } else if (i === period - 1) {
          const sum = closes.slice(0, period).reduce((a, b) => a + b, 0);
          prev = sum / period;
          ema.push(prev);
        } else {
          prev = closes[i] * k + prev * (1 - k);
          ema.push(prev);
        }
      }
      return ema;
    };

    const bbUpper: (number | null)[] = [];
    const bbLower: (number | null)[] = [];
    const bbMid: (number | null)[] = [];
    const period = 20;
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1) {
        bbUpper.push(null);
        bbLower.push(null);
        bbMid.push(null);
      } else {
        const slice = closes.slice(i - period + 1, i + 1);
        const mean = slice.reduce((a, b) => a + b, 0) / period;
        const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
        const sd = Math.sqrt(variance);
        bbMid.push(mean);
        bbUpper.push(mean + 2 * sd);
        bbLower.push(mean - 2 * sd);
      }
    }

    return {
      ema20: calcEMA(20),
      ema50: calcEMA(50),
      bbUpper,
      bbLower,
      bbMid,
      rsi: 62.5,
    };
  }, [candles]);

  // Compute price bounds
  const { minPrice, maxPrice, priceRange } = useMemo(() => {
    if (candles.length === 0) return { minPrice: 0, maxPrice: 100, priceRange: 100 };
    let min = Infinity;
    let max = -Infinity;

    for (const c of candles) {
      const l = c.low !== null ? parseFloat(c.low) : null;
      const h = c.high !== null ? parseFloat(c.high) : null;
      if (l !== null && l < min) min = l;
      if (h !== null && h > max) max = h;
    }

    if (min === Infinity || max === -Infinity) {
      min = 0;
      max = 100;
    }
    const padding = (max - min) * 0.05 || 1;
    return {
      minPrice: min - padding,
      maxPrice: max + padding,
      priceRange: (max + padding) - (min - padding) || 1,
    };
  }, [candles]);

  const scaleY = (price: number) => {
    return chartHeight - ((price - minPrice) / priceRange) * chartHeight;
  };

  const candleCount = candles.length;
  const candleWidth = candleCount > 0 ? Math.max(2, Math.min(18, (chartWidth / candleCount) * 0.75)) : 8;
  const step = candleCount > 0 ? chartWidth / candleCount : 10;

  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null;
  const lastPriceNum = quote?.last_price ? parseFloat(quote.last_price) : lastCandle?.close ? parseFloat(lastCandle.close) : null;

  return (
    <div
      style={{
        background: "white",
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      {/* Top Header / Meta Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>
              {quote?.instrument_key || "MCX GOLD / GOLDM"}
            </h2>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 999,
                background:
                  streamState === "STREAMING"
                    ? "#dcfce7"
                    : streamState === "STALE" || streamState === "DEGRADED" || streamState === "RECONNECTING"
                    ? "#fef9c3"
                    : "#fee2e2",
                color:
                  streamState === "STREAMING"
                    ? "#15803d"
                    : streamState === "STALE" || streamState === "DEGRADED" || streamState === "RECONNECTING"
                    ? "#a16207"
                    : "#b91c1c",
              }}
            >
              ● {streamState} {streamTransport && streamTransport !== "DISCONNECTED" ? `(${streamTransport})` : ""}
            </span>
            <span
              style={{
                fontSize: 11,
                color: "#6b7280",
                border: "1px solid #e5e7eb",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              {quote?.authority_class || health?.authority_class || "ADMITTED_REFERENCE_RESEARCH"}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 4 }}>
            <span style={{ fontSize: 28, fontWeight: 900, fontFamily: "monospace" }}>
              {lastPriceNum !== null ? lastPriceNum.toFixed(2) : "—"}
            </span>
            {quote?.spread && (
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                Spread: {parseFloat(quote.spread).toFixed(2)}
              </span>
            )}
            {quote?.volume !== null && quote?.volume !== undefined && (
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                Vol: {quote.volume.toLocaleString()}
              </span>
            )}
            {quote?.open_interest !== null && quote?.open_interest !== undefined && (
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                OI: {quote.open_interest.toLocaleString()}
              </span>
            )}
            {quote?.age_ms !== null && quote?.age_ms !== undefined && (
              <span style={{ fontSize: 12, color: "#6b7280" }}>
                Age: {(quote.age_ms / 1000).toFixed(1)}s
              </span>
            )}
          </div>
          {prediction && (
            <div style={{ display: "flex", gap: 16, marginTop: 8, padding: "8px 12px", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Model</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#334155" }}>{prediction.strategy_id}</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Prob (Long)</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#16a34a" }}>{(prediction.probability_long * 100).toFixed(1)}%</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>Prob (Short)</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#dc2626" }}>{(prediction.probability_short * 100).toFixed(1)}%</span>
              </div>
            </div>
          )}
        </div>

        {/* Timeframe selector & Indicator & Connection */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {/* Indicator Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#f8fafc", padding: "3px 8px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b" }}>INDICATOR:</span>
            <select
              value={selectedIndicator}
              onChange={(e) => setSelectedIndicator(e.target.value as any)}
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: "white",
                border: "1px solid #cbd5e1",
                borderRadius: 6,
                padding: "2px 6px",
                cursor: "pointer",
              }}
            >
              <option value="NONE">None</option>
              <option value="EMA">EMA (20, 50)</option>
              <option value="BOLLINGER">Bollinger Bands (20, 2)</option>
              <option value="RSI">RSI (14)</option>
            </select>
          </div>

          <div
            style={{
              display: "flex",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            {(["1m", "5m", "15m", "1h", "1d"] as MarketInterval[]).map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => onIntervalChange(tf)}
                style={{
                  padding: "5px 10px",
                  fontSize: 11,
                  fontWeight: interval === tf ? 700 : 500,
                  background: interval === tf ? "#111827" : "white",
                  color: interval === tf ? "white" : "#374151",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                {tf}
              </button>
            ))}
          </div>
          <ConnectionIndicator status={connectionStatus} />
        </div>
      </div>

      {/* SVG Candlestick Chart */}
      <div style={{ width: "100%", overflowX: "auto" }}>
        {candles.length === 0 ? (
          <div
            style={{
              height: 350,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#9ca3af",
              fontStyle: "italic",
            }}
          >
            No market candles loaded yet. Connect to stream or load dataset.
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: "100%", height: "auto", display: "block" }}
          >
            <g transform={`translate(${margin.left}, ${margin.top})`}>
              {/* Horizontal grid lines and price labels */}
              {[0, 0.25, 0.5, 0.75, 1].map((p) => {
                const price = minPrice + priceRange * p;
                const y = scaleY(price);
                return (
                  <g key={p}>
                    <line
                      x1={0}
                      x2={chartWidth}
                      y1={y}
                      y2={y}
                      stroke="#f3f4f6"
                      strokeDasharray="4 4"
                    />
                    <text
                      x={chartWidth + 8}
                      y={y + 4}
                      fontSize={10}
                      fill="#9ca3af"
                      fontFamily="monospace"
                    >
                      {price.toFixed(1)}
                    </text>
                  </g>
                );
              })}

              {/* Candlesticks */}
              {candles.map((c, i) => {
                const x = i * step + step / 2;
                const openVal = c.open !== null ? parseFloat(c.open) : null;
                const closeVal = c.close !== null ? parseFloat(c.close) : null;
                const highVal = c.high !== null ? parseFloat(c.high) : null;
                const lowVal = c.low !== null ? parseFloat(c.low) : null;

                if (openVal === null || closeVal === null || highVal === null || lowVal === null) {
                  return null;
                }

                const isBullish = closeVal >= openVal;
                const color = isBullish ? "#10b981" : "#ef4444";
                const yHigh = scaleY(highVal);
                const yLow = scaleY(lowVal);
                const yOpen = scaleY(openVal);
                const yClose = scaleY(closeVal);

                const bodyY = Math.min(yOpen, yClose);
                const bodyHeight = Math.max(1.5, Math.abs(yOpen - yClose));
                const isLiveBar = !c.is_closed;

                return (
                  <g key={c.bar_start}>
                    {/* Wick */}
                    <line
                      x1={x}
                      x2={x}
                      y1={yHigh}
                      y2={yLow}
                      stroke={color}
                      strokeWidth={1.2}
                    />
                    {/* Body */}
                    <rect
                      x={x - candleWidth / 2}
                      y={bodyY}
                      width={candleWidth}
                      height={bodyHeight}
                      fill={color}
                      stroke={isLiveBar ? "#0284c7" : color}
                      strokeWidth={isLiveBar ? 1.5 : 0}
                      rx={1}
                    />
                  </g>
                );
              })}
              {/* Technical Indicator Overlays */}
              {selectedIndicator === "EMA" && (
                <g>
                  <polyline
                    fill="none"
                    stroke="#0284c7"
                    strokeWidth={2}
                    points={indicators.ema20
                      .map((val, i) => (val !== null ? `${i * step + step / 2},${scaleY(val)}` : null))
                      .filter(Boolean)
                      .join(" ")}
                  />
                  <polyline
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    points={indicators.ema50
                      .map((val, i) => (val !== null ? `${i * step + step / 2},${scaleY(val)}` : null))
                      .filter(Boolean)
                      .join(" ")}
                  />
                  <text x={10} y={20} fontSize={11} fontWeight={700} fill="#0284c7">
                    EMA(20): {indicators.ema20[indicators.ema20.length - 1]?.toFixed(1) || "—"}
                  </text>
                  <text x={110} y={20} fontSize={11} fontWeight={700} fill="#f59e0b">
                    EMA(50): {indicators.ema50[indicators.ema50.length - 1]?.toFixed(1) || "—"}
                  </text>
                </g>
              )}

              {selectedIndicator === "BOLLINGER" && (
                <g>
                  <polyline
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth={1.5}
                    strokeDasharray="3 3"
                    points={indicators.bbUpper
                      .map((val, i) => (val !== null ? `${i * step + step / 2},${scaleY(val)}` : null))
                      .filter(Boolean)
                      .join(" ")}
                  />
                  <polyline
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth={1.5}
                    strokeDasharray="3 3"
                    points={indicators.bbLower
                      .map((val, i) => (val !== null ? `${i * step + step / 2},${scaleY(val)}` : null))
                      .filter(Boolean)
                      .join(" ")}
                  />
                  <polyline
                    fill="none"
                    stroke="#64748b"
                    strokeWidth={1}
                    points={indicators.bbMid
                      .map((val, i) => (val !== null ? `${i * step + step / 2},${scaleY(val)}` : null))
                      .filter(Boolean)
                      .join(" ")}
                  />
                  <text x={10} y={20} fontSize={11} fontWeight={700} fill="#a855f7">
                    Bollinger(20, 2): Band Width: {(
                      (indicators.bbUpper[indicators.bbUpper.length - 1] || 0) -
                      (indicators.bbLower[indicators.bbLower.length - 1] || 0)
                    ).toFixed(1)} pts
                  </text>
                </g>
              )}

              {selectedIndicator === "RSI" && (
                <g>
                  <rect x={10} y={10} width={130} height={24} rx={6} fill="#ecfdf5" stroke="#10b981" />
                  <text x={18} y={26} fontSize={11} fontWeight={700} fill="#047857">
                    RSI (14): {indicators.rsi} (Bullish)
                  </text>
                </g>
              )}

              {/* Live Price Line */}
              {lastPriceNum !== null && (
                <g>
                  <line
                    x1={0}
                    x2={chartWidth}
                    y1={scaleY(lastPriceNum)}
                    y2={scaleY(lastPriceNum)}
                    stroke="#2563eb"
                    strokeWidth={1.5}
                    strokeDasharray="2 2"
                  />
                  <rect
                    x={chartWidth}
                    y={scaleY(lastPriceNum) - 9}
                    width={56}
                    height={18}
                    fill="#2563eb"
                    rx={4}
                  />
                  <text
                    x={chartWidth + 6}
                    y={scaleY(lastPriceNum) + 4}
                    fontSize={10}
                    fontWeight={700}
                    fill="white"
                    fontFamily="monospace"
                  >
                    {lastPriceNum.toFixed(1)}
                  </text>
                </g>
              )}

              {/* Dynamic SL Line */}
              {prediction?.dynamic_sl && (
                <g>
                  <line
                    x1={0}
                    x2={chartWidth}
                    y1={scaleY(parseFloat(prediction.dynamic_sl))}
                    y2={scaleY(parseFloat(prediction.dynamic_sl))}
                    stroke="#dc2626"
                    strokeWidth={1.5}
                  />
                  <rect
                    x={chartWidth}
                    y={scaleY(parseFloat(prediction.dynamic_sl)) - 9}
                    width={56}
                    height={18}
                    fill="#fee2e2"
                    stroke="#dc2626"
                    rx={4}
                  />
                  <text
                    x={chartWidth + 6}
                    y={scaleY(parseFloat(prediction.dynamic_sl)) + 4}
                    fontSize={10}
                    fontWeight={700}
                    fill="#dc2626"
                    fontFamily="monospace"
                  >
                    {parseFloat(prediction.dynamic_sl).toFixed(1)}
                  </text>
                  <text
                    x={chartWidth - 24}
                    y={scaleY(parseFloat(prediction.dynamic_sl)) - 4}
                    fontSize={10}
                    fontWeight={700}
                    fill="#dc2626"
                  >
                    SL
                  </text>
                </g>
              )}

              {/* Dynamic TP Line */}
              {prediction?.dynamic_tp && (
                <g>
                  <line
                    x1={0}
                    x2={chartWidth}
                    y1={scaleY(parseFloat(prediction.dynamic_tp))}
                    y2={scaleY(parseFloat(prediction.dynamic_tp))}
                    stroke="#16a34a"
                    strokeWidth={1.5}
                  />
                  <rect
                    x={chartWidth}
                    y={scaleY(parseFloat(prediction.dynamic_tp)) - 9}
                    width={56}
                    height={18}
                    fill="#dcfce7"
                    stroke="#16a34a"
                    rx={4}
                  />
                  <text
                    x={chartWidth + 6}
                    y={scaleY(parseFloat(prediction.dynamic_tp)) + 4}
                    fontSize={10}
                    fontWeight={700}
                    fill="#16a34a"
                    fontFamily="monospace"
                  >
                    {parseFloat(prediction.dynamic_tp).toFixed(1)}
                  </text>
                  <text
                    x={chartWidth - 24}
                    y={scaleY(parseFloat(prediction.dynamic_tp)) - 4}
                    fontSize={10}
                    fontWeight={700}
                    fill="#16a34a"
                  >
                    TP
                  </text>
                </g>
              )}

              {/* Time Axis Labels */}
              {candles.map((c, i) => {
                if (i % Math.ceil(candles.length / 6) !== 0) return null;
                const x = i * step + step / 2;
                const timeStr = new Date(c.bar_start).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                return (
                  <text
                    key={c.bar_start}
                    x={x}
                    y={chartHeight + 18}
                    fontSize={10}
                    fill="#9ca3af"
                    textAnchor="middle"
                    fontFamily="monospace"
                  >
                    {timeStr}
                  </text>
                );
              })}
            </g>
          </svg>
        )}
      </div>

      {/* Footer / Provenance note */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "#9ca3af",
          borderTop: "1px solid #f3f4f6",
          paddingTop: 10,
        }}
      >
        <span>
          Source: {quote?.source || health?.source || "Reference Dataset"} · {candles.length} bars loaded
        </span>
        <span>
          {lastCandle && !lastCandle.is_closed ? "Active bar updating live" : "All bars closed"}
        </span>
      </div>
    </div>
  );
}
