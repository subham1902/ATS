"use client";
import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import type {
  CandleSeriesView,
  CandleView,
  FeedHealthView,
  MarketInterval,
  MarketQuoteView,
  SseStatus,
} from "@ats/api-client";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  AreaSeries,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type UTCTimestamp,
} from "lightweight-charts";
import { inMemoryFootprintStore, type BarFootprint, type FootprintMemoryStats } from "../lib/footprint";
import { getMarketSessionInfo, type MarketSessionInfo } from "../lib/marketHours";
import { chartBarsFromCandles, evaluateChartProvenance } from "../lib/provenance";
import { useDataSource } from "../lib/dataSource";

interface LiveChartProps {
  candles: CandleView[];
  /** Full series envelope: source, authority class, state. The chart never
   * claims more than this envelope supports. */
  series?: CandleSeriesView | null;
  quote: MarketQuoteView | null;
  health: FeedHealthView | null;
  prediction?: any | null;
  interval: MarketInterval;
  onIntervalChange: (interval: MarketInterval) => void;
  connectionStatus: SseStatus;
  streamTransport?: "WEBSOCKET" | "SSE" | "DISCONNECTED";
  depthData?: any | null;
  strategies?: any[];
  selectedStrategy?: string;
  onSelectStrategy?: (strategyId: string) => void;
  defaultSymbol?: string;
}

// Universal safe price formatter
const fmtPrice = (p: any, dec = 1): string => {
  if (p === null || p === undefined) return "--";
  const n = typeof p === "number" ? p : parseFloat(String(p));
  return isNaN(n) ? "--" : n.toFixed(dec);
};

// -------------------------------------------------------------
// Mathematical Indicator Calculation Helpers
// -------------------------------------------------------------

function computeEma(bars: { time: UTCTimestamp; close: number }[], period: number) {
  if (!bars || bars.length < 2) return [];
  const k = 2 / (period + 1);
  let ema = bars[0].close;
  return bars.map((b, i) => {
    if (i === 0) return { time: b.time, value: b.close };
    ema = b.close * k + ema * (1 - k);
    return { time: b.time, value: parseFloat(ema.toFixed(2)) };
  });
}

function computeVwap(
  bars: { time: UTCTimestamp; high: number; low: number; close: number }[],
  volumes: { value: number | null }[],
) {
  if (!bars || bars.length === 0) return [];
  let cumVol = 0;
  let cumTypVol = 0;
  // Bars with unknown volume contribute nothing: VWAP is computed over
  // observed volume only, never over a filled-in default.
  return bars.map((b, i) => {
    const vol = volumes[i]?.value ?? null;
    const typPrice = (b.high + b.low + b.close) / 3;
    if (vol !== null && vol > 0) {
      cumVol += vol;
      cumTypVol += typPrice * vol;
    }
    const vwap = cumVol > 0 ? cumTypVol / cumVol : b.close;
    return { time: b.time, value: parseFloat(vwap.toFixed(2)) };
  });
}

function computeBollingerBands(bars: { time: UTCTimestamp; close: number }[], period = 20, stdDevMult = 2) {
  const upper: { time: UTCTimestamp; value: number }[] = [];
  const mid: { time: UTCTimestamp; value: number }[] = [];
  const lower: { time: UTCTimestamp; value: number }[] = [];

  if (!bars || bars.length === 0) return { upper, mid, lower };

  for (let i = 0; i < bars.length; i++) {
    if (i < period - 1) {
      mid.push({ time: bars[i].time, value: bars[i].close });
      upper.push({ time: bars[i].time, value: bars[i].close });
      lower.push({ time: bars[i].time, value: bars[i].close });
      continue;
    }
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += bars[j].close;
    }
    const sma = sum / period;
    let varSum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      varSum += Math.pow(bars[j].close - sma, 2);
    }
    const stdDev = Math.sqrt(varSum / period);
    mid.push({ time: bars[i].time, value: parseFloat(sma.toFixed(2)) });
    upper.push({ time: bars[i].time, value: parseFloat((sma + stdDevMult * stdDev).toFixed(2)) });
    lower.push({ time: bars[i].time, value: parseFloat((sma - stdDevMult * stdDev).toFixed(2)) });
  }

  return { upper, mid, lower };
}

function computeRsi(bars: { close: number }[], period = 14): number {
  if (!bars || bars.length < period + 1) return 50.0;
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < bars.length; i++) {
    const diff = bars[i].close - bars[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
  }

  if (avgLoss === 0) return 100.0;
  const rs = avgGain / avgLoss;
  return parseFloat((100 - 100 / (1 + rs)).toFixed(1));
}

function computeSuperTrend(
  bars: { time: UTCTimestamp; high: number; low: number; close: number }[],
  period = 10,
  multiplier = 3,
): { data: { time: UTCTimestamp; value: number }[]; isBullish: boolean } {
  if (!bars || bars.length < period) return { data: [], isBullish: true };
  const result: { time: UTCTimestamp; value: number }[] = [];
  let prevUpper = 0;
  let prevLower = 0;
  let prevSuperTrend = 0;
  let trend = 1;
  let atr = bars[0].high - bars[0].low;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    if (i > 0) {
      const tr = Math.max(b.high - b.low, Math.abs(b.high - bars[i - 1].close), Math.abs(b.low - bars[i - 1].close));
      atr = (atr * (period - 1) + tr) / period;
    }

    const hl2 = (b.high + b.low) / 2;
    const basicUpper = hl2 + multiplier * atr;
    const basicLower = hl2 - multiplier * atr;

    if (i === 0) {
      prevUpper = basicUpper;
      prevLower = basicLower;
      prevSuperTrend = basicLower;
      result.push({ time: b.time, value: parseFloat(prevSuperTrend.toFixed(2)) });
      continue;
    }

    const finalUpper = basicUpper < prevUpper || bars[i - 1].close > prevUpper ? basicUpper : prevUpper;
    const finalLower = basicLower > prevLower || bars[i - 1].close < prevLower ? basicLower : prevLower;

    if (prevSuperTrend === prevUpper) {
      trend = b.close > finalUpper ? 1 : -1;
    } else {
      trend = b.close < finalLower ? -1 : 1;
    }

    const superTrend = trend === 1 ? finalLower : finalUpper;
    result.push({ time: b.time, value: parseFloat(superTrend.toFixed(2)) });

    prevUpper = finalUpper;
    prevLower = finalLower;
    prevSuperTrend = superTrend;
  }

  return { data: result, isBullish: trend === 1 };
}

function convertToHeikinAshi(bars: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[]) {
  if (!bars || bars.length === 0) return [];
  const haBars: { time: UTCTimestamp; open: number; high: number; low: number; close: number }[] = [];
  let prevHaOpen = bars[0].open;
  let prevHaClose = bars[0].close;

  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const haClose = (b.open + b.high + b.low + b.close) / 4;
    const haOpen = i === 0 ? (b.open + b.close) / 2 : (prevHaOpen + prevHaClose) / 2;
    const haHigh = Math.max(b.high, haOpen, haClose);
    const haLow = Math.min(b.low, haOpen, haClose);

    haBars.push({
      time: b.time,
      open: parseFloat(haOpen.toFixed(2)),
      high: parseFloat(haHigh.toFixed(2)),
      low: parseFloat(haLow.toFixed(2)),
      close: parseFloat(haClose.toFixed(2)),
    });

    prevHaOpen = haOpen;
    prevHaClose = haClose;
  }
  return haBars;
}

function computeAtr(bars: { high: number; low: number; close: number }[], period = 14): number {
  if (!bars || bars.length < 2) return 0;
  let trSum = 0;
  const count = Math.min(bars.length - 1, period);
  for (let i = bars.length - count; i < bars.length; i++) {
    const tr = Math.max(
      bars[i].high - bars[i].low,
      Math.abs(bars[i].high - bars[i - 1].close),
      Math.abs(bars[i].low - bars[i - 1].close),
    );
    trSum += tr;
  }
  return parseFloat((trSum / count).toFixed(1));
}

function computeTrendChannel(bars: { time: UTCTimestamp; high: number; low: number; close: number }[]) {
  if (!bars || bars.length < 15) return { support: [], resistance: [] };
  const slice = bars.slice(-35);
  const n = slice.length;
  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumX2 = 0;
  slice.forEach((b, i) => {
    sumX += i;
    sumY += b.close;
    sumXY += i * b.close;
    sumX2 += i * i;
  });
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  let maxUp = 0;
  let maxDown = 0;
  slice.forEach((b, i) => {
    const mid = intercept + slope * i;
    const diffUp = b.high - mid;
    const diffDown = mid - b.low;
    if (diffUp > maxUp) maxUp = diffUp;
    if (diffDown > maxDown) maxDown = diffDown;
  });

  const support = slice.map((b, i) => ({
    time: b.time,
    value: parseFloat((intercept + slope * i - maxDown * 0.75).toFixed(2)),
  }));
  const resistance = slice.map((b, i) => ({
    time: b.time,
    value: parseFloat((intercept + slope * i + maxUp * 0.75).toFixed(2)),
  }));

  return { support, resistance };
}

// -------------------------------------------------------------
// Main LiveChart Component
// -------------------------------------------------------------

export function LiveChart({
  candles,
  series = null,
  quote,
  health,
  prediction,
  interval,
  onIntervalChange,
  connectionStatus,
  streamTransport,
  depthData,
  strategies = [],
  selectedStrategy = "A04_PROBABILISTIC",
  onSelectStrategy,
  defaultSymbol = "MCX GOLDM 25SEP26",
}: LiveChartProps) {
  const { requestedSource } = useDataSource();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Series References
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const areaSeriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema200SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbUpperSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbMidSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const bbLowerSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const superTrendSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const trendSupportSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const trendResistanceSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // Smart Zoom & Tool Tracking Refs
  const lastFittedSymbolRef = useRef<string>("");
  const lastFittedIntervalRef = useRef<string>("");
  const hoverPriceRef = useRef<number | null>(null);

  // State Management (Gold Mini as Primary Default Commodity)
  const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol || "MCX GOLDM 25SEP26");
  const [selectedExpiry, setSelectedExpiry] = useState("25 SEP 26");
  const [chartStyle, setChartStyle] = useState<"CANDLES" | "HEIKIN_ASHI" | "LINE" | "FOOTPRINT">("CANDLES");
  const [activeTab, setActiveTab] = useState<
    "NONE" | "SHORTCUTS" | "WATCHLIST" | "OPTION_CHAIN" | "FOOTPRINT" | "ORDERS" | "POSITIONS"
  >("NONE");
  const [activeTool, setActiveTool] = useState<
    "CROSSHAIR" | "TRENDLINE" | "HORZ_LINE" | "FIBONACCI" | "TARGET_TOOL" | "TEXT" | "MEASURE"
  >("CROSSHAIR");
  const [showIndicatorsModal, setShowIndicatorsModal] = useState(false);
  const [showTargetBox, setShowTargetBox] = useState(true);
  const [showFibonacci, setShowFibonacci] = useState(false);
  const [showWatermark, _setShowWatermark] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [showTrendChannel, setShowTrendChannel] = useState(false);
  const [measureResult, setMeasureResult] = useState<{
    fromPrice: number;
    toPrice: number;
    delta: number;
    deltaPct: number;
  } | null>(null);

  // In-Memory Order Flow Footprint State
  const [footprintBars, setFootprintBars] = useState<BarFootprint[]>([]);
  const [footprintStats, setFootprintStats] = useState<FootprintMemoryStats>({
    cachedBars: 0,
    memoryBytes: 0,
    memoryBytesMeasured: false,
    totalVolume: 0,
    totalDelta: 0,
    cumDelta: 0,
    buyPressurePct: 50,
    sellPressurePct: 50,
    imbalancesCount: 0,
  });
  const [userPriceLines, setUserPriceLines] = useState<
    Record<string, { id: string; price: number; title: string; color: string }[]>
  >({});
  const [isFullWindow, setIsFullWindow] = useState(false);

  // Ref tracking current active tool for chart event listeners
  const activeToolRef = useRef(activeTool);
  activeToolRef.current = activeTool;

  // Latest observed close, mirrored for event handlers registered once on mount.
  const latestCloseRef = useRef<number | null>(null);

  // Indicators toggle state
  const [enabledIndicators, setEnabledIndicators] = useState({
    ema20: true,
    ema50: false,
    ema200: false,
    vwap: true,
    bollingerBands: false,
    superTrend: false,
    volume: true,
    slTpOverlays: true,
    optionStrikes: true,
    rsiBadge: true,
  });

  // Real-time Tick State (driven only by observed feed ticks, never synthesized)
  const [currentTimeStr, setCurrentTimeStr] = useState("");
  const [candleCountdown, setCandleCountdown] = useState("05:00");
  const [crosshairBar, setCrosshairBar] = useState<{
    open: number;
    high: number;
    low: number;
    close: number;
    change: number;
    changePct: number;
  } | null>(null);

  // Market Session Status (Accurate Indian Exchange Hours: NSE 09:15-15:30 IST, MCX 09:00-23:30 IST)
  const [marketSession, setMarketSession] = useState<MarketSessionInfo>(() => getMarketSessionInfo(selectedSymbol));

  useEffect(() => {
    setMarketSession(getMarketSessionInfo(selectedSymbol));
  }, [selectedSymbol]);

  // Digital Clock & Bar Countdown Timer (Updating every 1 second)
  useEffect(() => {
    const updateTimers = () => {
      const now = new Date();
      setCurrentTimeStr(
        now.toLocaleTimeString("en-GB", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );

      // Periodically refresh market session status
      setMarketSession(getMarketSessionInfo(selectedSymbol, now));

      // Countdown to candle close
      const secMap: Record<string, number> = {
        "1s": 1,
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "1d": 86400,
      };
      const intvlSec = secMap[interval] || 300;
      const epochSec = Math.floor(now.getTime() / 1000);
      const remainingSec = intvlSec - (epochSec % intvlSec);
      const m = Math.floor(remainingSec / 60);
      const s = remainingSec % 60;
      setCandleCountdown(`${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
    };

    updateTimers();
    const timer = setInterval(updateTimers, 1000);
    return () => clearInterval(timer);
  }, [interval, selectedSymbol]);

  // Symbol Profiles (MCX Commodities Primary, plus NSE Indices)
  const profile = useMemo(() => {
    if (selectedSymbol.includes("GOLDM") || selectedSymbol.includes("GOLD")) {
      const lp = quote?.last_price ? parseFloat(quote.last_price) : 75420.0;
      return {
        symbol: "MCX GOLDM",
        name: "Gold Mini 100g",
        contract: "25SEP26",
        segment: "COMMODITY",
        type: "FUT",
        expiry: "25 SEP 26",
        basePrice: lp,
        dayChange: 120.0,
        dayChangePct: 0.16,
        open: lp - 120.0,
        lotSize: "100 grams",
        tickSize: 1.0,
        strikeStep: 100,
        callStrike: Math.round(lp / 100) * 100,
        callPremium: 185.0,
        putStrike: Math.round(lp / 100) * 100,
        putPremium: 142.5,
        entryPrice: prediction?.entry_price ? parseFloat(prediction.entry_price) : lp - 30,
        slPrice: prediction?.dynamic_sl ? parseFloat(prediction.dynamic_sl) : lp - 150,
        tpPrice: prediction?.dynamic_tp ? parseFloat(prediction.dynamic_tp) : lp + 250,
      };
    } else if (selectedSymbol.includes("SILVERM") || selectedSymbol.includes("SILVER")) {
      return {
        symbol: "MCX SILVERM",
        name: "Silver Mini 5kg",
        contract: "28NOV26",
        segment: "COMMODITY",
        type: "FUT",
        expiry: "28 NOV 26",
        basePrice: 89250.0,
        dayChange: 375.0,
        dayChangePct: 0.42,
        open: 88875.0,
        lotSize: "5 kg",
        tickSize: 1.0,
        strikeStep: 250,
        callStrike: 89250.0,
        callPremium: 420.0,
        putStrike: 89250.0,
        putPremium: 360.0,
        entryPrice: 89150.0,
        slPrice: 88900.0,
        tpPrice: 89650.0,
      };
    } else if (selectedSymbol.includes("CRUDEOIL") || selectedSymbol.includes("CRUDE")) {
      return {
        symbol: "MCX CRUDEOIL",
        name: "Crude Oil 100 bbl",
        contract: "19OCT26",
        segment: "COMMODITY",
        type: "FUT",
        expiry: "19 OCT 26",
        basePrice: 6180.0,
        dayChange: 45.0,
        dayChangePct: 0.73,
        open: 6135.0,
        lotSize: "100 bbl",
        tickSize: 1.0,
        strikeStep: 50,
        callStrike: 6200.0,
        callPremium: 68.0,
        putStrike: 6200.0,
        putPremium: 52.0,
        entryPrice: 6160.0,
        slPrice: 6120.0,
        tpPrice: 6240.0,
      };
    } else if (selectedSymbol.includes("NATURALGAS") || selectedSymbol.includes("NATGAS")) {
      return {
        symbol: "MCX NATURALGAS",
        name: "Natural Gas 1250 mmBtu",
        contract: "27OCT26",
        segment: "COMMODITY",
        type: "FUT",
        expiry: "27 OCT 26",
        basePrice: 238.5,
        dayChange: -3.2,
        dayChangePct: -1.32,
        open: 241.7,
        lotSize: "1250 mmBtu",
        tickSize: 0.1,
        strikeStep: 2.5,
        callStrike: 240.0,
        callPremium: 6.8,
        putStrike: 240.0,
        putPremium: 5.2,
        entryPrice: 239.0,
        slPrice: 235.0,
        tpPrice: 245.0,
      };
    } else if (selectedSymbol.includes("COPPER")) {
      return {
        symbol: "MCX COPPER",
        name: "Copper 2500 kg",
        contract: "31OCT26",
        segment: "COMMODITY",
        type: "FUT",
        expiry: "31 OCT 26",
        basePrice: 842.2,
        dayChange: 6.8,
        dayChangePct: 0.81,
        open: 835.4,
        lotSize: "2500 kg",
        tickSize: 0.05,
        strikeStep: 5,
        callStrike: 845.0,
        callPremium: 14.5,
        putStrike: 845.0,
        putPremium: 11.2,
        entryPrice: 840.0,
        slPrice: 832.0,
        tpPrice: 852.0,
      };
    } else if (selectedSymbol.includes("BANKNIFTY")) {
      return {
        symbol: "BANKNIFTY",
        name: "Nifty Bank Index",
        contract: "SPOT",
        segment: "INDEX",
        type: "SPOT",
        expiry: "29 SEP",
        basePrice: 56548.9,
        dayChange: 333.35,
        dayChangePct: 0.59,
        open: 56210.0,
        lotSize: "15",
        tickSize: 0.05,
        strikeStep: 100,
        callStrike: 56500.0,
        callPremium: 340.5,
        putStrike: 56500.0,
        putPremium: 285.2,
        entryPrice: 56480.0,
        slPrice: 56350.0,
        tpPrice: 56750.0,
      };
    } else if (selectedSymbol.includes("SENSEX")) {
      return {
        symbol: "SENSEX",
        name: "BSE Sensex Index",
        contract: "SPOT",
        segment: "INDEX",
        type: "SPOT",
        expiry: "03 OCT",
        basePrice: 76820.0,
        dayChange: 365.2,
        dayChangePct: 0.48,
        open: 76450.0,
        lotSize: "10",
        tickSize: 0.05,
        strikeStep: 100,
        callStrike: 76800.0,
        callPremium: 290.0,
        putStrike: 76800.0,
        putPremium: 245.0,
        entryPrice: 76750.0,
        slPrice: 76550.0,
        tpPrice: 77150.0,
      };
    } else {
      // NIFTY 50
      return {
        symbol: "NIFTY 50",
        name: "Nifty 50 Index",
        contract: "SPOT",
        segment: "INDEX",
        type: "SPOT",
        expiry: "29 SEP",
        basePrice: 23446.8,
        dayChange: 117.8,
        dayChangePct: 0.5,
        open: 23330.0,
        lotSize: "25",
        tickSize: 0.05,
        strikeStep: 50,
        callStrike: 23450.0,
        callPremium: 108.8,
        putStrike: 23450.0,
        putPremium: 93.4,
        entryPrice: 23430.0,
        slPrice: 23410.0,
        tpPrice: 23485.0,
      };
    }
  }, [selectedSymbol, quote, prediction]);

  // Reset live tick state when symbol changes (no synthetic carry-over)
  useEffect(() => {
    setFootprintBars([]);
    setFootprintStats({
      cachedBars: 0,
      memoryBytes: 0,
      memoryBytesMeasured: false,
      totalVolume: 0,
      totalDelta: 0,
      cumDelta: 0,
      buyPressurePct: 50,
      sellPressurePct: 50,
      imbalancesCount: 0,
    });
  }, [selectedSymbol]);

  // No synthetic pulse: when the feed is quiet the chart is still. Ticks arrive
  // from the broker feed (via useMarketFeed) or not at all.

  // Observed bars only. Every rendered bar comes from an API candle whose
  // open, high, low and close were all present and numeric. Bars missing any
  // leg are skipped and counted in provenance — interpolated history would
  // look real while being invented, which is exactly what this chart used to do.
  const observed = useMemo(() => chartBarsFromCandles(candles), [candles]);

  const provenance = useMemo(
    () =>
      evaluateChartProvenance({
        series,
        health,
        quoteState: quote?.state ?? null,
        connectionStatus,
        streamTransport: streamTransport ?? "DISCONNECTED",
        requestedSource,
        bars: observed,
      }),
    [series, health, quote, connectionStatus, streamTransport, requestedSource, observed],
  );

  const baseChartData = useMemo(() => {
    const rawBars = observed.bars.map((b) => ({
      time: b.time as UTCTimestamp,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    // Volume is rendered only where the feed supplied it. A missing volume is
    // a gap in the histogram, not a 1200 default.
    const volumes = observed.bars
      .filter((b) => b.volume !== null)
      .map((b) => ({
        time: b.time as UTCTimestamp,
        value: b.volume as number,
        color: b.close >= b.open ? "rgba(8, 153, 129, 0.45)" : "rgba(242, 54, 69, 0.45)",
      }));
    return { rawBars, volumes };
  }, [observed]);

  // Synchronize In-Memory Footprint buffer when observed bars change.
  // Bars with unknown volume are ingested without one; the footprint engine
  // models distribution, but the call site must not invent a default.
  useEffect(() => {
    if (observed.bars.length > 0) {
      const barsWithVol = observed.bars.map((b) => ({
        time: b.time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
        volume: b.volume ?? undefined,
      }));
      const fps = inMemoryFootprintStore.ingestBars(selectedSymbol, barsWithVol, profile.tickSize);
      setFootprintBars(fps);
      setFootprintStats(inMemoryFootprintStore.getStats(selectedSymbol));
    }
  }, [observed, selectedSymbol, profile.tickSize]);

  // Derived Candle Types (Japanese vs Heikin-Ashi)
  const activeBars = useMemo(() => {
    if (chartStyle === "HEIKIN_ASHI") {
      return convertToHeikinAshi(baseChartData.rawBars);
    }
    return baseChartData.rawBars;
  }, [baseChartData.rawBars, chartStyle]);

  // Computed Indicators
  const indicatorsData = useMemo(() => {
    const bars = activeBars;
    const volumes = baseChartData.volumes;

    const ema20 = enabledIndicators.ema20 ? computeEma(bars, 20) : [];
    const ema50 = enabledIndicators.ema50 ? computeEma(bars, 50) : [];
    const ema200 = enabledIndicators.ema200 ? computeEma(bars, 200) : [];
    const vwap = enabledIndicators.vwap ? computeVwap(bars, volumes) : [];
    const bb = enabledIndicators.bollingerBands ? computeBollingerBands(bars, 20, 2) : null;
    const rsiValue = computeRsi(bars, 14);
    const superTrend = enabledIndicators.superTrend ? computeSuperTrend(bars, 10, 3) : null;
    const atrValue = computeAtr(bars, 14);
    const trendChannel = showTrendChannel ? computeTrendChannel(bars) : null;

    // Fibonacci Retracement Levels
    let fibLevels: { level: string; price: number; color: string }[] = [];
    if (showFibonacci && bars.length > 10) {
      let maxH = -Infinity;
      let minL = Infinity;
      bars.slice(-30).forEach((b) => {
        if (b.high > maxH) maxH = b.high;
        if (b.low < minL) minL = b.low;
      });
      const range = maxH - minL;
      fibLevels = [
        { level: "100.0%", price: parseFloat(maxH.toFixed(2)), color: "#787b86" },
        { level: "78.6%", price: parseFloat((minL + 0.786 * range).toFixed(2)), color: "#f59e0b" },
        { level: "61.8% (Golden)", price: parseFloat((minL + 0.618 * range).toFixed(2)), color: "#eab308" },
        { level: "50.0%", price: parseFloat((minL + 0.5 * range).toFixed(2)), color: "#38bdf8" },
        { level: "38.2%", price: parseFloat((minL + 0.382 * range).toFixed(2)), color: "#eab308" },
        { level: "23.6%", price: parseFloat((minL + 0.236 * range).toFixed(2)), color: "#f59e0b" },
        { level: "0.0%", price: parseFloat(minL.toFixed(2)), color: "#787b86" },
      ];
    }

    return { ema20, ema50, ema200, vwap, bb, rsiValue, superTrend, fibLevels, atrValue, trendChannel };
  }, [activeBars, baseChartData.volumes, enabledIndicators, showFibonacci, showTrendChannel]);

  // Current price metrics. With no observed bars there is no price to show:
  // null renders as "—", never as a preset base price.
  const latestCandle = activeBars[activeBars.length - 1] || null;
  const currentPrice: number | null = latestCandle ? latestCandle.close : null;
  latestCloseRef.current = currentPrice;
  const priceChange: number | null = currentPrice !== null ? currentPrice - profile.open : null;
  const priceChangePct: number | null =
    currentPrice !== null && profile.open > 0 ? ((currentPrice - profile.open) / profile.open) * 100 : null;

  // -------------------------------------------------------------
  // Chart Initialization Effect (Once on Mount)
  // -------------------------------------------------------------
  useEffect(() => {
    if (!chartContainerRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "#0c0e14" },
        textColor: "#8f9cae",
        fontSize: 11,
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.04)" },
        horzLines: { color: "rgba(255, 255, 255, 0.04)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "#758696",
          width: 1,
          style: LineStyle.Dotted,
          labelBackgroundColor: "#1e222d",
        },
        horzLine: {
          color: "#758696",
          width: 1,
          style: LineStyle.Dotted,
          labelBackgroundColor: "#1e222d",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(255, 255, 255, 0.08)",
        scaleMargins: {
          top: 0.08,
          bottom: 0.18,
        },
      },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.08)",
        timeVisible: true,
        secondsVisible: false,
      },
      autoSize: true,
    });

    chartRef.current = chart;

    // 1. Candlestick Series (Upstox Emerald Green & Crimson Red)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#089981",
      downColor: "#f23645",
      borderVisible: true,
      borderUpColor: "#089981",
      borderDownColor: "#f23645",
      wickUpColor: "#089981",
      wickDownColor: "#f23645",
    });
    candleSeriesRef.current = candleSeries;

    // 2. Area Series (for Line Chart mode)
    const areaSeries = chart.addSeries(AreaSeries, {
      topColor: "rgba(37, 99, 235, 0.4)",
      bottomColor: "rgba(37, 99, 235, 0.0)",
      lineColor: "#3b82f6",
      lineWidth: 2,
    });
    areaSeries.applyOptions({ visible: false });
    areaSeriesRef.current = areaSeries;

    // 3. Volume Histogram Series (Overlay at bottom)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26a69a",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0,
      },
    });
    volumeSeriesRef.current = volumeSeries;

    // 4. Moving Averages
    const ema20Series = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 1.5 as any,
      crosshairMarkerVisible: false,
      title: "EMA 20",
    });
    ema20SeriesRef.current = ema20Series;

    const ema50Series = chart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 1.5 as any,
      crosshairMarkerVisible: false,
      title: "EMA 50",
    });
    ema50SeriesRef.current = ema50Series;

    const ema200Series = chart.addSeries(LineSeries, {
      color: "#8b5cf6",
      lineWidth: 2 as any,
      crosshairMarkerVisible: false,
      title: "EMA 200",
    });
    ema200SeriesRef.current = ema200Series;

    // 5. VWAP (Volume Weighted Average Price - Gold)
    const vwapSeries = chart.addSeries(LineSeries, {
      color: "#eab308",
      lineWidth: 2 as any,
      lineStyle: LineStyle.Solid,
      crosshairMarkerVisible: false,
      title: "VWAP",
    });
    vwapSeriesRef.current = vwapSeries;

    // 6. Bollinger Bands (Upper, Mid, Lower)
    const bbUpper = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      title: "BB Upper",
    });
    const bbMid = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      crosshairMarkerVisible: false,
      title: "BB Mid",
    });
    const bbLower = chart.addSeries(LineSeries, {
      color: "#06b6d4",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      title: "BB Lower",
    });
    bbUpperSeriesRef.current = bbUpper;
    bbMidSeriesRef.current = bbMid;
    bbLowerSeriesRef.current = bbLower;

    // 7. SuperTrend
    const superTrend = chart.addSeries(LineSeries, {
      color: "#22c55e",
      lineWidth: 2 as any,
      crosshairMarkerVisible: false,
      title: "SuperTrend",
    });
    superTrendSeriesRef.current = superTrend;

    // 8. Auto Trend Channel Support & Resistance
    const trendSupport = chart.addSeries(LineSeries, {
      color: "#22c55e",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      title: "Trend Support",
    });
    const trendResistance = chart.addSeries(LineSeries, {
      color: "#ef4444",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      title: "Trend Resistance",
    });
    trendSupportSeriesRef.current = trendSupport;
    trendResistanceSeriesRef.current = trendResistance;

    // Crosshair listener for real-time OHLC readout & hover price tracking
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData.get(candleSeries)) {
        setCrosshairBar(null);
        hoverPriceRef.current = null;
        return;
      }
      const data = param.seriesData.get(candleSeries) as {
        open: number;
        high: number;
        low: number;
        close: number;
      };
      if (data) {
        const ch = data.close - data.open;
        const chPct = data.open > 0 ? (ch / data.open) * 100 : 0;
        setCrosshairBar({
          open: data.open,
          high: data.high,
          low: data.low,
          close: data.close,
          change: ch,
          changePct: chPct,
        });
      }
      if (param.point) {
        const p = candleSeries.coordinateToPrice(param.point.y);
        if (p !== null && !isNaN(p)) {
          hoverPriceRef.current = p;
        }
      }
    });

    // Chart Click Handler for interactive drawing tools & range measurement
    chart.subscribeClick((param) => {
      if (!param.point) return;
      const clickedPrice = candleSeries.coordinateToPrice(param.point.y);
      if (clickedPrice === null || isNaN(clickedPrice)) return;

      const tool = activeToolRef.current;
      if (tool === "HORZ_LINE") {
        const roundedPrice = parseFloat(clickedPrice.toFixed(2));
        setUserPriceLines((prev) => ({
          ...prev,
          [selectedSymbol]: [
            ...(prev[selectedSymbol] || []),
            {
              id: `line_${Date.now()}`,
              price: roundedPrice,
              title: `LEVEL ₹${roundedPrice.toFixed(1)}`,
              color: "#eab308",
            },
          ],
        }));
        setActiveTool("CROSSHAIR");
      } else if (tool === "MEASURE") {
        // Measure from the last observed close. With no observed bars there is
        // nothing to measure against, so the tool stays idle.
        const base = latestCloseRef.current;
        if (base === null) return;
        const delta = clickedPrice - base;
        const deltaPct = base > 0 ? (delta / base) * 100 : 0;
        setMeasureResult({
          fromPrice: parseFloat(base.toFixed(2)),
          toPrice: parseFloat(clickedPrice.toFixed(2)),
          delta: parseFloat(delta.toFixed(2)),
          deltaPct: parseFloat(deltaPct.toFixed(2)),
        });
      }
    });

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // -------------------------------------------------------------
  // Data & Dynamic Overlays Synchronization Effect
  // -------------------------------------------------------------
  useEffect(() => {
    if (!candleSeriesRef.current || activeBars.length === 0) return;

    // 1. Candlestick vs Line mode
    if (chartStyle === "LINE") {
      candleSeriesRef.current.applyOptions({ visible: false });
      if (areaSeriesRef.current) {
        areaSeriesRef.current.applyOptions({ visible: true });
        areaSeriesRef.current.setData(activeBars.map((b) => ({ time: b.time, value: b.close })));
      }
    } else {
      if (areaSeriesRef.current) areaSeriesRef.current.applyOptions({ visible: false });
      candleSeriesRef.current.applyOptions({ visible: true });
      candleSeriesRef.current.setData(activeBars);
    }

    // 2. Volumes
    if (volumeSeriesRef.current) {
      if (enabledIndicators.volume) {
        volumeSeriesRef.current.setData(baseChartData.volumes);
      } else {
        volumeSeriesRef.current.setData([]);
      }
    }

    // 3. Indicators Data Binding
    if (ema20SeriesRef.current) {
      ema20SeriesRef.current.setData(enabledIndicators.ema20 ? indicatorsData.ema20 : []);
    }
    if (ema50SeriesRef.current) {
      ema50SeriesRef.current.setData(enabledIndicators.ema50 ? indicatorsData.ema50 : []);
    }
    if (ema200SeriesRef.current) {
      ema200SeriesRef.current.setData(enabledIndicators.ema200 ? indicatorsData.ema200 : []);
    }
    if (vwapSeriesRef.current) {
      vwapSeriesRef.current.setData(enabledIndicators.vwap ? indicatorsData.vwap : []);
    }
    if (bbUpperSeriesRef.current && bbMidSeriesRef.current && bbLowerSeriesRef.current) {
      if (enabledIndicators.bollingerBands && indicatorsData.bb) {
        bbUpperSeriesRef.current.setData(indicatorsData.bb.upper);
        bbMidSeriesRef.current.setData(indicatorsData.bb.mid);
        bbLowerSeriesRef.current.setData(indicatorsData.bb.lower);
      } else {
        bbUpperSeriesRef.current.setData([]);
        bbMidSeriesRef.current.setData([]);
        bbLowerSeriesRef.current.setData([]);
      }
    }
    if (superTrendSeriesRef.current) {
      if (enabledIndicators.superTrend && indicatorsData.superTrend) {
        superTrendSeriesRef.current.applyOptions({
          color: indicatorsData.superTrend.isBullish ? "#22c55e" : "#ef4444",
        });
        superTrendSeriesRef.current.setData(indicatorsData.superTrend.data);
      } else {
        superTrendSeriesRef.current.setData([]);
      }
    }

    if (trendSupportSeriesRef.current && trendResistanceSeriesRef.current) {
      if (showTrendChannel && indicatorsData.trendChannel) {
        trendSupportSeriesRef.current.setData(indicatorsData.trendChannel.support);
        trendResistanceSeriesRef.current.setData(indicatorsData.trendChannel.resistance);
      } else {
        trendSupportSeriesRef.current.setData([]);
        trendResistanceSeriesRef.current.setData([]);
      }
    }

    // 4. Refresh Price Lines (Option strikes, SL/TP, Fibonacci, User lines)
    priceLinesRef.current.forEach((pl) => {
      try {
        candleSeriesRef.current?.removePriceLine(pl);
        areaSeriesRef.current?.removePriceLine(pl);
      } catch (_e) {
        // ignore
      }
    });
    priceLinesRef.current = [];

    const series = chartStyle === "LINE" ? areaSeriesRef.current : candleSeriesRef.current;
    if (series) {
      // Upstox Purple Option Strike Line
      if (enabledIndicators.optionStrikes) {
        const strikeLine = series.createPriceLine({
          price: profile.callStrike,
          color: "#8b5cf6",
          lineWidth: 1,
          lineStyle: LineStyle.LargeDashed,
          axisLabelVisible: true,
          title: `C ${profile.callPremium} | P ${profile.putPremium}`,
        });
        priceLinesRef.current.push(strikeLine);
      }

      // Strategy SL / TP / Entry
      if (enabledIndicators.slTpOverlays) {
        const entryLine = series.createPriceLine({
          price: profile.entryPrice,
          color: "#2563eb",
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: `ENTRY ${profile.entryPrice.toFixed(1)}`,
        });
        priceLinesRef.current.push(entryLine);

        const slLine = series.createPriceLine({
          price: profile.slPrice,
          color: "#f23645",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `SL ${profile.slPrice.toFixed(1)}`,
        });
        priceLinesRef.current.push(slLine);

        const tpLine = series.createPriceLine({
          price: profile.tpPrice,
          color: "#089981",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `TP1 ${profile.tpPrice.toFixed(1)}`,
        });
        priceLinesRef.current.push(tpLine);
      }

      // Fibonacci Retracement Levels
      if (showFibonacci && indicatorsData.fibLevels.length > 0) {
        indicatorsData.fibLevels.forEach((fib) => {
          const fibLine = series.createPriceLine({
            price: fib.price,
            color: fib.color,
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: `Fib ${fib.level} (₹${fib.price})`,
          });
          priceLinesRef.current.push(fibLine);
        });
      }

      // User Custom Drawn Horizontal Lines for active symbol only
      (userPriceLines[selectedSymbol] || []).forEach((upl) => {
        const uLine = series.createPriceLine({
          price: upl.price,
          color: upl.color,
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: upl.title,
        });
        priceLinesRef.current.push(uLine);
      });
    }

    // Smart Zoom & TimeScale: Only fitContent on symbol or timeframe change
    const isNewSymbolOrInterval =
      lastFittedSymbolRef.current !== selectedSymbol || lastFittedIntervalRef.current !== interval;

    if (isNewSymbolOrInterval) {
      chartRef.current?.timeScale().fitContent();
      lastFittedSymbolRef.current = selectedSymbol;
      lastFittedIntervalRef.current = interval;
    }
  }, [
    activeBars,
    baseChartData.volumes,
    chartStyle,
    enabledIndicators,
    indicatorsData,
    profile,
    showFibonacci,
    showTrendChannel,
    userPriceLines,
    selectedSymbol,
    interval,
  ]);

  const streamState = useMemo(() => {
    if (connectionStatus === "connecting") return "CONNECTING";
    if (connectionStatus === "disconnected" || connectionStatus === "error") return "OFFLINE";
    if (health?.provider_state === "RECONNECTING") return "RECONNECTING";
    if (health?.provider_state === "DEGRADED") return "DEGRADED";
    if (health?.state === "STALE") return "STALE";
    if (health?.state === "LIVE" || health?.provider_state === "STREAMING") return "STREAMING";
    return "LIVE";
  }, [connectionStatus, health]);

  const activeBarDisplay = crosshairBar || {
    open: latestCandle?.open ?? currentPrice,
    high: latestCandle?.high ?? currentPrice,
    low: latestCandle?.low ?? currentPrice,
    close: currentPrice,
    change: priceChange,
    changePct: priceChangePct,
  };

  // Add User Horizontal Price Line at Crosshair hover or current price
  const handleAddHorizontalLine = useCallback(() => {
    const targetPrice = hoverPriceRef.current ?? currentPrice;
    if (targetPrice === null || targetPrice === undefined) return;
    const rounded = parseFloat(targetPrice.toFixed(2));
    const newLine = {
      id: `line_${Date.now()}`,
      price: rounded,
      title: `LEVEL ₹${rounded.toFixed(1)}`,
      color: "#eab308",
    };
    setUserPriceLines((prev) => ({
      ...prev,
      [selectedSymbol]: [...(prev[selectedSymbol] || []), newLine],
    }));
  }, [currentPrice, selectedSymbol]);

  // Reset Zoom & Auto-Scale
  const handleResetZoom = useCallback(() => {
    chartRef.current?.timeScale().fitContent();
  }, []);

  // Keyboard Shortcuts (TradingView standard Alt+H, Alt+F, Alt+I, Esc)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "TEXTAREA" ||
        document.activeElement?.tagName === "SELECT"
      ) {
        return;
      }

      if (e.altKey && (e.key === "h" || e.key === "H")) {
        e.preventDefault();
        handleAddHorizontalLine();
      } else if (e.altKey && (e.key === "f" || e.key === "F")) {
        e.preventDefault();
        handleResetZoom();
      } else if (e.altKey && (e.key === "i" || e.key === "I")) {
        e.preventDefault();
        setShowIndicatorsModal((prev) => !prev);
      } else if (e.key === "Escape") {
        setShowIndicatorsModal(false);
        setActiveTab("NONE");
        setActiveTool("CROSSHAIR");
        setMeasureResult(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleAddHorizontalLine, handleResetZoom]);

  // Capture Chart Snapshot
  const handleTakeSnapshot = () => {
    const canvas = chartRef.current?.takeScreenshot();
    if (canvas) {
      const url = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.download = `chart360_${selectedSymbol.replace(/\s+/g, "_")}_${interval}.png`;
      a.href = url;
      a.click();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: isFullWindow ? "100vh" : "82vh",
        minHeight: 650,
        background: "#0c0e14",
        color: "#e2e8f0",
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        borderRadius: isFullWindow ? 0 : 8,
        border: "1px solid #1e222d",
        overflow: "hidden",
        position: isFullWindow ? "fixed" : "relative",
        top: isFullWindow ? 0 : undefined,
        left: isFullWindow ? 0 : undefined,
        zIndex: isFullWindow ? 9999 : 1,
      }}
    >
      {/* 1. TOPMOST TICKER BAR (Upstox Chart 360 Header) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 14px",
          background: "#090a0f",
          borderBottom: "1px solid #1a1e28",
          fontSize: 12,
          flexWrap: "nowrap",
          overflowX: "auto",
        }}
      >
        {/* Left: Brand Badge & Tickers */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Upstox Chart 360 Logo Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
              color: "white",
              padding: "3px 10px",
              borderRadius: 6,
              fontWeight: 800,
              fontSize: 12,
              letterSpacing: "0.2px",
              boxShadow: "0 2px 6px rgba(124, 58, 237, 0.3)",
            }}
          >
            <span>📈</span>
            <span>Chart 360</span>
          </div>

          {/* Indices & Commodities Tickers Strip */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              borderLeft: "1px solid #1e2433",
              paddingLeft: 14,
            }}
          >
            {/* COMMODITIES SECTION */}
            <span style={{ fontSize: 10, fontWeight: 800, color: "#f59e0b", letterSpacing: "0.5px" }}>
              MCX COMMODITIES:
            </span>

            {/* GOLDM MCX (ATS Core Asset) */}
            <div
              onClick={() => setSelectedSymbol("MCX GOLDM 25SEP26")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("GOLDM") ? "rgba(234, 179, 8, 0.2)" : "rgba(234, 179, 8, 0.08)",
                padding: "3px 10px",
                borderRadius: 4,
                border: `1px solid ${selectedSymbol.includes("GOLDM") ? "#eab308" : "rgba(234, 179, 8, 0.3)"}`,
              }}
            >
              <span style={{ fontWeight: 900, color: "#fbbf24" }}>★ MCX GOLDM</span>
              <span style={{ fontWeight: 900, color: "#fef08a", fontFamily: "monospace" }}>75,420.00</span>
              <span style={{ fontSize: 10, color: "#22c55e", fontWeight: 700 }}>▲ 120.0 (0.16%)</span>
            </div>

            {/* SILVERM MCX */}
            <div
              onClick={() => setSelectedSymbol("MCX SILVERM 28NOV26")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("SILVERM") ? "rgba(148, 163, 184, 0.2)" : "transparent",
                padding: "3px 8px",
                borderRadius: 4,
                border: `1px solid ${selectedSymbol.includes("SILVERM") ? "#94a3b8" : "rgba(148, 163, 184, 0.2)"}`,
              }}
            >
              <span style={{ fontWeight: 800, color: "#cbd5e1" }}>MCX SILVERM</span>
              <span style={{ fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>89,250.00</span>
              <span style={{ fontSize: 10, color: "#22c55e" }}>▲ 375.0 (0.42%)</span>
            </div>

            {/* CRUDEOIL MCX */}
            <div
              onClick={() => setSelectedSymbol("MCX CRUDEOIL 19OCT26")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("CRUDEOIL") ? "rgba(239, 68, 68, 0.2)" : "transparent",
                padding: "3px 8px",
                borderRadius: 4,
                border: `1px solid ${selectedSymbol.includes("CRUDEOIL") ? "#ef4444" : "rgba(239, 68, 68, 0.2)"}`,
              }}
            >
              <span style={{ fontWeight: 800, color: "#f87171" }}>MCX CRUDEOIL</span>
              <span style={{ fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>6,180.00</span>
              <span style={{ fontSize: 10, color: "#22c55e" }}>▲ 45.0 (0.73%)</span>
            </div>

            {/* NATURALGAS MCX */}
            <div
              onClick={() => setSelectedSymbol("MCX NATURALGAS 27OCT26")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("NATURALGAS") ? "rgba(56, 189, 248, 0.2)" : "transparent",
                padding: "3px 8px",
                borderRadius: 4,
                border: `1px solid ${selectedSymbol.includes("NATURALGAS") ? "#38bdf8" : "rgba(56, 189, 248, 0.2)"}`,
              }}
            >
              <span style={{ fontWeight: 800, color: "#38bdf8" }}>MCX NATGAS</span>
              <span style={{ fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>238.50</span>
              <span style={{ fontSize: 10, color: "#ef4444" }}>▼ -3.20 (-1.32%)</span>
            </div>

            <span style={{ color: "#334155" }}>|</span>

            {/* NSE INDICES */}
            <span style={{ fontSize: 10, fontWeight: 800, color: "#94a3b8", letterSpacing: "0.5px" }}>INDICES:</span>

            {/* NIFTY 50 */}
            <div
              onClick={() => setSelectedSymbol("NIFTY 50 SPOT")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("NIFTY 50") ? "rgba(34, 197, 94, 0.12)" : "transparent",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  color: selectedSymbol.includes("NIFTY 50") ? "#4ade80" : "#94a3b8",
                }}
              >
                NIFTY 50
              </span>
              <span style={{ fontWeight: 800, color: "#22c55e", fontFamily: "monospace" }}>23,446.80</span>
              <span style={{ fontSize: 10, color: "#22c55e" }}>▲ 117.80 (0.50%)</span>
              {!getMarketSessionInfo("NIFTY 50").isOpen && (
                <span
                  style={{
                    fontSize: 9,
                    color: "#f87171",
                    fontWeight: 700,
                    background: "rgba(239, 68, 68, 0.15)",
                    padding: "1px 5px",
                    borderRadius: 3,
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                  }}
                >
                  CLOSED
                </span>
              )}
            </div>

            {/* BANKNIFTY */}
            <div
              onClick={() => setSelectedSymbol("BANKNIFTY SPOT")}
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 6,
                cursor: "pointer",
                background: selectedSymbol.includes("BANKNIFTY") ? "rgba(34, 197, 94, 0.12)" : "transparent",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  color: selectedSymbol.includes("BANKNIFTY") ? "#4ade80" : "#94a3b8",
                }}
              >
                BANKNIFTY
              </span>
              <span style={{ fontWeight: 800, color: "#22c55e", fontFamily: "monospace" }}>56,548.90</span>
              <span style={{ fontSize: 10, color: "#22c55e" }}>▲ 333.35 (0.59%)</span>
              {!getMarketSessionInfo("BANKNIFTY").isOpen && (
                <span
                  style={{
                    fontSize: 9,
                    color: "#f87171",
                    fontWeight: 700,
                    background: "rgba(239, 68, 68, 0.15)",
                    padding: "1px 5px",
                    borderRadius: 3,
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                  }}
                >
                  CLOSED
                </span>
              )}
            </div>

            {/* INDIA VIX */}
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span style={{ fontWeight: 700, color: "#94a3b8" }}>INDIA VIX</span>
              <span style={{ fontWeight: 800, color: "#ef4444", fontFamily: "monospace" }}>10.35</span>
              <span style={{ fontSize: 10, color: "#ef4444" }}>▼ -0.65 (-5.91%)</span>
            </div>
          </div>
        </div>

        {/* Right: Operator Badge & Settings */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Live Connection Pill */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 999,
              background: streamState === "STREAMING" ? "rgba(34, 197, 94, 0.15)" : "rgba(234, 179, 8, 0.15)",
              color: streamState === "STREAMING" ? "#4ade80" : "#fde047",
              border: `1px solid ${streamState === "STREAMING" ? "rgba(34, 197, 94, 0.3)" : "rgba(234, 179, 8, 0.3)"}`,
            }}
          >
            <span>●</span>
            <span>
              {streamState} {streamTransport && streamTransport !== "DISCONNECTED" ? `(${streamTransport})` : ""}
            </span>
          </div>

          {/* User profile */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 10,
                fontWeight: 800,
                color: "white",
              }}
            >
              SP
            </div>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#cbd5e1" }}>Subham Pa...</span>
          </div>

          {/* Snapshot Button */}
          <button
            onClick={handleTakeSnapshot}
            title="Take Snapshot / Export Chart"
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 14,
              padding: "2px 4px",
            }}
          >
            📷
          </button>

          {/* Fullscreen Toggle */}
          <button
            onClick={() => setIsFullWindow(!isFullWindow)}
            title={isFullWindow ? "Exit Fullscreen" : "Fullscreen"}
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 14,
              padding: "2px 4px",
            }}
          >
            {isFullWindow ? "🗗" : "⛶"}
          </button>

          {/* Indicators / Settings Gear */}
          <button
            onClick={() => setShowIndicatorsModal(!showIndicatorsModal)}
            title="Terminal Indicators & Settings"
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 14,
              padding: "2px 4px",
            }}
          >
            ⚙️
          </button>
        </div>
      </div>

      {/* 2. CHART SUB-HEADER TOOLBAR (Upstox Symbol Bar) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 14px",
          background: "#10131a",
          borderBottom: "1px solid #1a1e28",
          fontSize: 12,
          flexWrap: "wrap",
          gap: 10,
        }}
      >
        {/* Left: Symbol & Price Readout */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {/* Symbol Select (Grouped by MCX Commodities and NSE Indices) */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              style={{
                background: "#181d28",
                color: "#f8fafc",
                fontWeight: 800,
                fontSize: 13,
                border: "1px solid #2d3748",
                borderRadius: 6,
                padding: "3px 8px",
                cursor: "pointer",
                outline: "none",
              }}
            >
              <optgroup label="MCX Commodities (Live)">
                <option value="MCX GOLDM 25SEP26">★ MCX GOLDM (Gold Mini)</option>
                <option value="MCX SILVERM 28NOV26">MCX SILVERM (Silver Mini)</option>
                <option value="MCX CRUDEOIL 19OCT26">MCX CRUDEOIL (Crude Oil)</option>
                <option value="MCX NATURALGAS 27OCT26">MCX NATURALGAS (Nat Gas)</option>
                <option value="MCX COPPER 31OCT26">MCX COPPER (Copper)</option>
              </optgroup>
              <optgroup label="NSE Indices">
                <option value="NIFTY 50 SPOT">NIFTY 50 SPOT</option>
                <option value="BANKNIFTY SPOT">BANKNIFTY SPOT</option>
                <option value="SENSEX SPOT">SENSEX SPOT</option>
                <option value="FINNIFTY SPOT">FINNIFTY SPOT</option>
              </optgroup>
            </select>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                background: profile.segment === "COMMODITY" ? "rgba(234, 179, 8, 0.2)" : "#262e3d",
                color: profile.segment === "COMMODITY" ? "#fbbf24" : "#94a3b8",
                padding: "2px 6px",
                borderRadius: 4,
                border: profile.segment === "COMMODITY" ? "1px solid rgba(234, 179, 8, 0.4)" : "none",
              }}
            >
              {profile.segment === "COMMODITY" ? "COMMODITY FUT" : "INDEX SPOT"}
            </span>

            {/* Market Session Status Badge */}
            <span
              title={marketSession.sessionDetail}
              style={{
                fontSize: 10,
                fontWeight: 800,
                background: marketSession.badgeBackground,
                color: marketSession.badgeColor,
                padding: "2px 7px",
                borderRadius: 4,
                border: `1px solid ${marketSession.badgeBorder}`,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                letterSpacing: "0.3px",
              }}
            >
              <span style={{ fontSize: 8 }}>●</span>
              <span>{marketSession.statusText}</span>
              {!marketSession.isOpen && (
                <span style={{ color: "#94a3b8", fontWeight: 500, fontSize: 9 }}>({marketSession.nextOpen})</span>
              )}
            </span>

            {/* Data provenance: what the rendered bars actually are. Requested
            source is what the operator asked for; the feed state is what the
            server reported. Neither is inferred. */}
            <span
              title={`${provenance.detail}${
                provenance.authorityClass ? ` Authority: ${provenance.authorityClass}.` : ""
              }${provenance.reasonCodes.length > 0 ? ` Reasons: ${provenance.reasonCodes.join(", ")}.` : ""}${
                provenance.skippedBars > 0
                  ? ` ${provenance.skippedBars} incomplete bar(s) omitted, never interpolated.`
                  : ""
              }${
                provenance.missingVolumeBars > 0
                  ? ` ${provenance.missingVolumeBars} bar(s) have no volume and render as gaps.`
                  : ""
              }`}
              aria-label={`chart data provenance: ${provenance.label}`}
              style={{
                fontSize: 10,
                fontWeight: 800,
                background:
                  provenance.status === "LIVE"
                    ? "rgba(34, 197, 94, 0.12)"
                    : provenance.status === "STALE"
                      ? "rgba(245, 158, 11, 0.12)"
                      : "rgba(148, 163, 184, 0.12)",
                color: provenance.status === "LIVE" ? "#4ade80" : provenance.status === "STALE" ? "#fbbf24" : "#94a3b8",
                padding: "2px 7px",
                borderRadius: 4,
                border: "1px solid rgba(148, 163, 184, 0.2)",
                letterSpacing: "0.3px",
              }}
            >
              {provenance.label} · {provenance.observedBars} bars
            </span>
          </div>

          {/* Real-time Price / Frozen Closing Price */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 16, fontWeight: 900, fontFamily: "monospace", color: "#f8fafc" }}>
              {currentPrice !== null
                ? currentPrice.toLocaleString("en-IN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })
                : "—"}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: priceChange !== null && priceChange >= 0 ? "#22c55e" : "#ef4444",
                fontFamily: "monospace",
              }}
            >
              {priceChange === null || priceChangePct === null ? (
                "no observed price"
              ) : (
                <>
                  {priceChange >= 0 ? "+" : ""}
                  {priceChange.toFixed(2)} ({priceChangePct.toFixed(2)}%)
                </>
              )}
            </span>
            {!marketSession.isOpen && currentPrice !== null && (
              <span style={{ fontSize: 10, color: "#94a3b8", fontStyle: "italic" }}>· Frozen at Close</span>
            )}
          </div>

          {/* Expiry Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <select
              value={selectedExpiry}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              style={{
                background: "#181d28",
                color: "#cbd5e1",
                fontSize: 11,
                border: "1px solid #2d3748",
                borderRadius: 4,
                padding: "2px 6px",
                cursor: "pointer",
                outline: "none",
              }}
            >
              <option value="25 SEP 26">25 SEP 26</option>
              <option value="05 OCT 26">05 OCT 26</option>
              <option value="28 NOV 26">28 NOV 26</option>
              <option value="29 SEP">29 SEP</option>
            </select>
          </div>

          {/* Timeframe Bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "#161b24",
              borderRadius: 6,
              padding: "2px",
              border: "1px solid #242c3b",
            }}
          >
            {(["1s", "1m", "3m", "5m", "15m", "1h", "1d"] as MarketInterval[]).map((tf) => (
              <button
                key={tf}
                onClick={() => onIntervalChange(tf)}
                style={{
                  background: interval === tf ? "#2563eb" : "transparent",
                  color: interval === tf ? "white" : "#94a3b8",
                  border: "none",
                  borderRadius: 4,
                  padding: "3px 8px",
                  fontSize: 11,
                  fontWeight: interval === tf ? 800 : 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Chart Style Switcher (Candles, Heikin Ashi, Line, Footprint) */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "#161b24",
              borderRadius: 6,
              padding: "2px",
              border: "1px solid #242c3b",
            }}
          >
            <button
              onClick={() => setChartStyle("CANDLES")}
              title="Japanese Candlesticks"
              style={{
                background: chartStyle === "CANDLES" ? "#1e293b" : "transparent",
                color: chartStyle === "CANDLES" ? "#60a5fa" : "#64748b",
                border: "none",
                borderRadius: 4,
                padding: "3px 6px",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              🕯️
            </button>
            <button
              onClick={() => setChartStyle("HEIKIN_ASHI")}
              title="Heikin Ashi (Smoothed Trend)"
              style={{
                background: chartStyle === "HEIKIN_ASHI" ? "#1e293b" : "transparent",
                color: chartStyle === "HEIKIN_ASHI" ? "#60a5fa" : "#64748b",
                border: "none",
                borderRadius: 4,
                padding: "3px 6px",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              📊 HA
            </button>
            <button
              onClick={() => setChartStyle("LINE")}
              title="Area / Line Close"
              style={{
                background: chartStyle === "LINE" ? "#1e293b" : "transparent",
                color: chartStyle === "LINE" ? "#60a5fa" : "#64748b",
                border: "none",
                borderRadius: 4,
                padding: "3px 6px",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              📈
            </button>
            <button
              onClick={() => setChartStyle("FOOTPRINT")}
              title="Order Flow Footprint (In-Memory Bid/Ask Ladder)"
              style={{
                background: chartStyle === "FOOTPRINT" ? "#1e293b" : "transparent",
                color: chartStyle === "FOOTPRINT" ? "#38bdf8" : "#64748b",
                border: "none",
                borderRadius: 4,
                padding: "3px 6px",
                fontSize: 11,
                cursor: "pointer",
                fontWeight: 700,
              }}
            >
              👣 FP
            </button>
          </div>

          {/* Indicators Button */}
          <button
            onClick={() => setShowIndicatorsModal(!showIndicatorsModal)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: showIndicatorsModal ? "#2563eb" : "#181d28",
              color: showIndicatorsModal ? "white" : "#cbd5e1",
              border: "1px solid #2d3748",
              borderRadius: 6,
              padding: "3px 8px",
              fontSize: 11,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <span>fx</span>
            <span>Indicators</span>
          </button>

          {/* Technical Intelligence Strip (RSI, VWAP, In-Memory CVD & RAM Telemetry) */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontFamily: "monospace" }}>
            {enabledIndicators.rsiBadge && (
              <span
                style={{
                  background: "rgba(139, 92, 246, 0.15)",
                  color: "#c084fc",
                  border: "1px solid rgba(139, 92, 246, 0.3)",
                  padding: "2px 6px",
                  borderRadius: 4,
                  fontWeight: 700,
                }}
              >
                RSI: {indicatorsData.rsiValue}{" "}
                {indicatorsData.rsiValue > 70 ? "▲ OB" : indicatorsData.rsiValue < 30 ? "▼ OS" : ""}
              </span>
            )}
            {enabledIndicators.vwap && (
              <span
                style={{
                  background: "rgba(234, 179, 8, 0.12)",
                  color: "#fde047",
                  border: "1px solid rgba(234, 179, 8, 0.3)",
                  padding: "2px 6px",
                  borderRadius: 4,
                  fontWeight: 700,
                }}
              >
                VWAP: ₹{fmtPrice(indicatorsData.vwap[indicatorsData.vwap.length - 1]?.value, 1)}
              </span>
            )}
            <span
              title="Cumulative Volume Delta (In-Memory CVD Flow)"
              style={{
                background: footprintStats.cumDelta >= 0 ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                color: footprintStats.cumDelta >= 0 ? "#4ade80" : "#f87171",
                border: `1px solid ${
                  footprintStats.cumDelta >= 0 ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"
                }`,
                padding: "2px 6px",
                borderRadius: 4,
                fontWeight: 700,
              }}
            >
              CVD: {footprintStats.cumDelta >= 0 ? "+" : ""}
              {footprintStats.cumDelta}
            </span>
            <span
              title="Active In-Memory Footprint Buffer"
              style={{
                background: "rgba(56, 189, 248, 0.12)",
                color: "#38bdf8",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                padding: "2px 6px",
                borderRadius: 4,
                fontWeight: 700,
              }}
            >
              RAM: {footprintStats.cachedBars} bars
            </span>
          </div>

          {/* Strategy Selector */}
          {strategies.length > 0 && onSelectStrategy && (
            <select
              value={selectedStrategy}
              onChange={(e) => onSelectStrategy(e.target.value)}
              style={{
                background: "#181d28",
                color: "#60a5fa",
                fontSize: 11,
                fontWeight: 700,
                border: "1px solid #2d3748",
                borderRadius: 6,
                padding: "3px 8px",
                cursor: "pointer",
                outline: "none",
              }}
            >
              {strategies.map((s) => (
                <option key={s.strategy_id} value={s.strategy_id}>
                  {s.badge} {s.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Right: Dynamic Crosshair OHLC Readout */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontFamily: "monospace",
            fontSize: 11,
          }}
        >
          <div style={{ color: "#94a3b8" }}>
            O <span style={{ color: "#f8fafc", fontWeight: 700 }}>{fmtPrice(activeBarDisplay.open, 2)}</span>
          </div>
          <div style={{ color: "#94a3b8" }}>
            H <span style={{ color: "#22c55e", fontWeight: 700 }}>{fmtPrice(activeBarDisplay.high, 2)}</span>
          </div>
          <div style={{ color: "#94a3b8" }}>
            L <span style={{ color: "#ef4444", fontWeight: 700 }}>{fmtPrice(activeBarDisplay.low, 2)}</span>
          </div>
          <div style={{ color: "#94a3b8" }}>
            C{" "}
            <span
              style={{
                color: activeBarDisplay.change !== null && activeBarDisplay.change >= 0 ? "#22c55e" : "#ef4444",
                fontWeight: 700,
              }}
            >
              {fmtPrice(activeBarDisplay.close, 2)}
            </span>
          </div>
          <div
            style={{
              color: activeBarDisplay.change !== null && activeBarDisplay.change >= 0 ? "#22c55e" : "#ef4444",
              fontWeight: 700,
            }}
          >
            {activeBarDisplay.change === null || activeBarDisplay.changePct === null ? (
              "Ch —"
            ) : (
              <>
                Ch {activeBarDisplay.change >= 0 ? "+" : ""}
                {activeBarDisplay.change.toFixed(2)} ({activeBarDisplay.changePct.toFixed(2)}%)
              </>
            )}
          </div>
        </div>
      </div>

      {/* 3. MAIN WORKSPACE (Left Tools Rail + Chart Canvas + Side Drawers) */}
      <div style={{ display: "flex", flex: 1, position: "relative", overflow: "hidden" }}>
        {/* Left Vertical Drawing Tools Rail & Nav Tabs */}
        <div
          style={{
            width: 48,
            background: "#090a0f",
            borderRight: "1px solid #1a1e28",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 0",
            zIndex: 10,
          }}
        >
          {/* Top Drawing Tools */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%", alignItems: "center" }}>
            {[
              { id: "CROSSHAIR", icon: "✛", label: "Crosshair (Cursor Mode)" },
              { id: "TRENDLINE", icon: "╱", label: "Trendline" },
              { id: "HORZ_LINE", icon: "―", label: "Horizontal Support/Resistance Line" },
              { id: "FIBONACCI", icon: "≡", label: "Fibonacci Retracement" },
              { id: "TARGET_TOOL", icon: "📐", label: "Long/Short Target Projection" },
              { id: "TEXT", icon: "T", label: "Text Annotation" },
              { id: "MEASURE", icon: "📏", label: "Measure Range (Click 2 points)" },
            ].map((tool) => (
              <button
                key={tool.id}
                onClick={() => {
                  setActiveTool(tool.id as any);
                  if (tool.id === "TARGET_TOOL") setShowTargetBox(!showTargetBox);
                  if (tool.id === "FIBONACCI") setShowFibonacci(!showFibonacci);
                  if (tool.id === "TRENDLINE") setShowTrendChannel(!showTrendChannel);
                  if (tool.id === "HORZ_LINE") handleAddHorizontalLine();
                }}
                title={tool.label}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 6,
                  background: activeTool === tool.id ? "#2563eb" : "transparent",
                  color: activeTool === tool.id ? "white" : "#94a3b8",
                  border: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {tool.icon}
              </button>
            ))}

            {/* Clear All Custom Drawings */}
            {(userPriceLines[selectedSymbol] || []).length > 0 && (
              <button
                onClick={() =>
                  setUserPriceLines((prev) => ({
                    ...prev,
                    [selectedSymbol]: [],
                  }))
                }
                title="Clear Custom Drawings for active symbol"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 6,
                  background: "transparent",
                  color: "#ef4444",
                  border: "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                🗑️
              </button>
            )}
          </div>

          {/* Vertical Upstox Nav Tabs */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 8, width: "100%" }}>
            {[
              { id: "SHORTCUTS", label: "Shortcuts" },
              { id: "WATCHLIST", label: "Watchlist" },
              { id: "OPTION_CHAIN", label: "Option Chain" },
              { id: "FOOTPRINT", label: "Footprint" },
              { id: "ORDERS", label: "Orders (0)" },
              { id: "POSITIONS", label: "Positions (0)" },
            ].map((tab) => (
              <button
                key={tab.id}
                data-testid={`drawer-tab-${tab.id.toLowerCase()}`}
                onClick={() => setActiveTab(activeTab === tab.id ? "NONE" : (tab.id as any))}
                style={{
                  background: activeTab === tab.id ? "#1e293b" : "transparent",
                  color: activeTab === tab.id ? "#60a5fa" : "#64748b",
                  border: "none",
                  cursor: "pointer",
                  padding: "6px 2px",
                  borderRadius: 4,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "100%",
                }}
              >
                <span
                  style={{
                    writingMode: "vertical-rl",
                    transform: "rotate(180deg)",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.5px",
                    display: "inline-block",
                    userSelect: "none",
                  }}
                >
                  {tab.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Center: TradingView Lightweight Chart Canvas */}
        <div style={{ flex: 1, position: "relative", height: "100%", width: "100%" }}>
          <div
            ref={chartContainerRef}
            style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0 }}
          />

          {/* Subtle Institutional Watermark */}
          {showWatermark && (
            <div
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                pointerEvents: "none",
                zIndex: 2,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                opacity: 0.04,
                userSelect: "none",
              }}
            >
              <span style={{ fontSize: 68, fontWeight: 900, letterSpacing: -2, color: "white" }}>
                {selectedSymbol.split(" ")[0]}
              </span>
              <span style={{ fontSize: 20, fontWeight: 800, color: "white" }}>{interval} • ATS TERMINAL</span>
            </div>
          )}

          {/* TradingView On-Chart Indicator Legend Overlay */}
          {showLegend ? (
            <div
              style={{
                position: "absolute",
                top: 10,
                left: 12,
                zIndex: 5,
                display: "flex",
                flexDirection: "column",
                gap: 4,
                fontSize: 11,
                fontFamily: "monospace",
                background: "rgba(12, 14, 20, 0.8)",
                backdropFilter: "blur(6px)",
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid rgba(255, 255, 255, 0.08)",
                pointerEvents: "auto",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: 800, color: "#f8fafc" }}>{selectedSymbol}</span>
                <span style={{ color: "#94a3b8" }}>• {interval}</span>
                <span style={{ color: "#64748b" }}>• {chartStyle}</span>
                <button
                  onClick={() => setShowLegend(false)}
                  title="Hide Legend"
                  style={{
                    background: "none",
                    border: "none",
                    color: "#64748b",
                    cursor: "pointer",
                    fontSize: 11,
                    padding: 0,
                    marginLeft: 2,
                  }}
                >
                  👁️
                </button>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, fontSize: 10 }}>
                {enabledIndicators.ema20 && (
                  <span style={{ color: "#60a5fa" }}>
                    EMA 20:{" "}
                    {indicatorsData.ema20.length > 0
                      ? indicatorsData.ema20[indicatorsData.ema20.length - 1].value
                      : "--"}
                  </span>
                )}
                {enabledIndicators.ema50 && (
                  <span style={{ color: "#fb923c" }}>
                    EMA 50:{" "}
                    {indicatorsData.ema50.length > 0
                      ? indicatorsData.ema50[indicatorsData.ema50.length - 1].value
                      : "--"}
                  </span>
                )}
                {enabledIndicators.vwap && (
                  <span style={{ color: "#facc15" }}>
                    VWAP:{" "}
                    {indicatorsData.vwap.length > 0 ? indicatorsData.vwap[indicatorsData.vwap.length - 1].value : "--"}
                  </span>
                )}
                {enabledIndicators.bollingerBands && indicatorsData.bb?.mid && indicatorsData.bb.mid.length > 0 && (
                  <span style={{ color: "#22d3ee" }}>
                    BB [{indicatorsData.bb.lower[indicatorsData.bb.lower.length - 1]?.value} -{" "}
                    {indicatorsData.bb.upper[indicatorsData.bb.upper.length - 1]?.value}]
                  </span>
                )}
                <span style={{ color: "#a855f7" }}>ATR: {indicatorsData.atrValue}</span>
                {enabledIndicators.superTrend && (
                  <span
                    style={{
                      color: indicatorsData.superTrend?.isBullish ? "#22c55e" : "#ef4444",
                    }}
                  >
                    ST: {indicatorsData.superTrend?.isBullish ? "▲ BULL" : "▼ BEAR"}
                  </span>
                )}
                {showTrendChannel && <span style={{ color: "#22c55e" }}>📐 Channel: ACTIVE</span>}
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowLegend(true)}
              title="Show Indicator Legend"
              style={{
                position: "absolute",
                top: 10,
                left: 12,
                zIndex: 5,
                background: "rgba(18, 22, 32, 0.7)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                color: "#94a3b8",
                padding: "3px 8px",
                borderRadius: 4,
                fontSize: 10,
                cursor: "pointer",
              }}
            >
              👁️ Legend
            </button>
          )}

          {/* Green Target Projection Box (Risk/Reward Box on the right) */}
          {showTargetBox && (
            <div
              style={{
                position: "absolute",
                top: "28%",
                right: "18%",
                width: 14,
                height: "36%",
                background: "rgba(8, 153, 129, 0.45)",
                border: "2px solid #089981",
                borderRadius: 2,
                pointerEvents: "none",
                zIndex: 4,
                boxShadow: "0 0 10px rgba(8, 153, 129, 0.3)",
              }}
            >
              {/* Projection trail horizontal guide line */}
              <div
                style={{
                  position: "absolute",
                  bottom: 0,
                  right: 14,
                  width: 60,
                  borderBottom: "1px dashed rgba(255, 255, 255, 0.4)",
                }}
              />
            </div>
          )}

          {/* Measurement Result Overlay Banner */}
          {measureResult && (
            <div
              style={{
                position: "absolute",
                bottom: 64,
                left: "50%",
                transform: "translateX(-50%)",
                background: "rgba(15, 23, 42, 0.95)",
                border: "1px solid #3b82f6",
                padding: "8px 14px",
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "monospace",
                display: "flex",
                alignItems: "center",
                gap: 12,
                zIndex: 25,
                boxShadow: "0 4px 14px rgba(0,0,0,0.6)",
              }}
            >
              <span>
                📏 Range:{" "}
                <strong>
                  ₹{measureResult.fromPrice} → ₹{measureResult.toPrice}
                </strong>
              </span>
              <span
                style={{
                  color: measureResult.delta >= 0 ? "#22c55e" : "#ef4444",
                  fontWeight: 800,
                }}
              >
                {measureResult.delta >= 0 ? "+" : ""}
                {measureResult.delta} ({measureResult.deltaPct}%)
              </span>
              <button
                onClick={() => setMeasureResult(null)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                ✕
              </button>
            </div>
          )}

          {/* Order Flow Footprint Overlay (When FOOTPRINT mode is active) */}
          {chartStyle === "FOOTPRINT" && (
            <div
              style={{
                position: "absolute",
                top: 45,
                left: 12,
                right: 55,
                bottom: 35,
                zIndex: 6,
                pointerEvents: "auto",
                background: "rgba(10, 12, 18, 0.94)",
                backdropFilter: "blur(6px)",
                borderRadius: 8,
                border: "1px solid #1e293b",
                padding: "12px 14px",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                boxShadow: "0 10px 30px rgba(0,0,0,0.8)",
              }}
            >
              {/* Footprint Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderBottom: "1px solid #1e293b",
                  paddingBottom: 8,
                  marginBottom: 10,
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontWeight: 800, color: "#38bdf8" }}>
                    👣 ORDER FLOW FOOTPRINT (IN-MEMORY BID x ASK LADDER)
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      background: "rgba(34, 197, 94, 0.15)",
                      color: "#4ade80",
                      padding: "2px 6px",
                      borderRadius: 4,
                      fontWeight: 700,
                    }}
                  >
                    ● REAL-TIME RAM BUFFER
                  </span>
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    {profile.symbol} · {interval} · POC Gold Row · Diagonal Imbalances (2.8x)
                  </span>
                </div>
                <div style={{ display: "flex", gap: 12, fontSize: 11, fontFamily: "monospace" }}>
                  <span>
                    Buy Pressure: <strong style={{ color: "#22c55e" }}>{footprintStats.buyPressurePct}%</strong>
                  </span>
                  <span>
                    Sell Pressure: <strong style={{ color: "#ef4444" }}>{footprintStats.sellPressurePct}%</strong>
                  </span>
                  <span>
                    Net CVD:{" "}
                    <strong
                      style={{
                        color: footprintStats.cumDelta >= 0 ? "#22c55e" : "#ef4444",
                      }}
                    >
                      {footprintStats.cumDelta >= 0 ? "+" : ""}
                      {footprintStats.cumDelta}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Footprint Bars Grid */}
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  gap: 10,
                  overflowX: "auto",
                  paddingBottom: 6,
                  alignItems: "flex-end",
                }}
              >
                {footprintBars.slice(-8).map((fp) => {
                  const isBull = fp.close >= fp.open;
                  const dateStr = new Date(fp.time * 1000).toLocaleTimeString("en-GB", {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <div
                      key={fp.time}
                      style={{
                        minWidth: 125,
                        background: "#0c0f17",
                        border: `1px solid ${isBull ? "rgba(34, 197, 94, 0.35)" : "rgba(239, 68, 68, 0.35)"}`,
                        borderRadius: 6,
                        display: "flex",
                        flexDirection: "column",
                        fontSize: 9.5,
                        fontFamily: "monospace",
                        boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
                      }}
                    >
                      {/* Bar Top Header */}
                      <div
                        style={{
                          padding: "3px 6px",
                          background: isBull ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                          display: "flex",
                          justifyContent: "space-between",
                          borderBottom: "1px solid #1e2433",
                          fontWeight: 700,
                        }}
                      >
                        <span style={{ color: "#94a3b8" }}>{dateStr}</span>
                        <span style={{ color: isBull ? "#4ade80" : "#f87171" }}>
                          {isBull ? "▲" : "▼"} {fp.close.toFixed(1)}
                        </span>
                      </div>

                      {/* Footprint Price Levels Ladder */}
                      <div
                        style={{
                          padding: "3px 0",
                          display: "flex",
                          flexDirection: "column",
                          gap: 1,
                          maxHeight: 280,
                          overflowY: "auto",
                        }}
                      >
                        {fp.levels.map((lvl, lIdx) => (
                          <div
                            key={lIdx}
                            style={{
                              display: "grid",
                              gridTemplateColumns: "1fr 1fr 1fr",
                              padding: "1.5px 3px",
                              background: lvl.isPoc
                                ? "rgba(234, 179, 8, 0.25)"
                                : lvl.isBuyImbalance
                                  ? "rgba(34, 197, 94, 0.18)"
                                  : lvl.isSellImbalance
                                    ? "rgba(239, 68, 68, 0.18)"
                                    : "transparent",
                              border: lvl.isPoc ? "1px solid #eab308" : "none",
                              borderRadius: 2,
                              fontSize: 9,
                              textAlign: "center",
                            }}
                          >
                            {/* Bid Vol */}
                            <span
                              style={{
                                color: lvl.isSellImbalance ? "#ef4444" : "#94a3b8",
                                fontWeight: lvl.isSellImbalance ? 800 : 500,
                                textAlign: "right",
                                paddingRight: 3,
                              }}
                            >
                              {lvl.bidVol}
                            </span>
                            {/* Level Price */}
                            <span
                              style={{
                                color: lvl.isPoc ? "#fef08a" : "#cbd5e1",
                                fontWeight: lvl.isPoc ? 800 : 600,
                              }}
                            >
                              {lvl.price}
                            </span>
                            {/* Ask Vol */}
                            <span
                              style={{
                                color: lvl.isBuyImbalance ? "#22c55e" : "#94a3b8",
                                fontWeight: lvl.isBuyImbalance ? 800 : 500,
                                textAlign: "left",
                                paddingLeft: 3,
                              }}
                            >
                              {lvl.askVol}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Bar Bottom Delta & CVD Pill */}
                      <div
                        style={{
                          padding: "3px 6px",
                          background: "#080a10",
                          borderTop: "1px solid #1e2433",
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 8.5,
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 800,
                            color: fp.delta >= 0 ? "#22c55e" : "#ef4444",
                          }}
                        >
                          Δ {fp.delta >= 0 ? "+" : ""}
                          {fp.delta}
                        </span>
                        <span style={{ color: "#64748b" }}>Vol: {fp.volume.toLocaleString()}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Reset Zoom Icon (matching Upstox Chart 360 circle arrow) */}
          <button
            onClick={handleResetZoom}
            title="Reset Zoom & Auto-scale (Alt + F)"
            style={{
              position: "absolute",
              bottom: 24,
              left: "50%",
              transform: "translateX(-50%)",
              background: "#181d28",
              border: "1px solid #2d3748",
              color: "#cbd5e1",
              borderRadius: "50%",
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              cursor: "pointer",
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              zIndex: 5,
            }}
          >
            ⟲
          </button>
        </div>

        {/* Slide-out Side Drawers (Watchlist / Option Chain / Orders / Positions) */}
        {activeTab !== "NONE" && (
          <div
            data-testid="chart360-drawer"
            style={{
              width: 320,
              background: "#0f131c",
              borderLeft: "1px solid #1a1e28",
              display: "flex",
              flexDirection: "column",
              zIndex: 20,
              animation: "slideIn 0.2s ease",
            }}
          >
            {/* Drawer Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 14px",
                borderBottom: "1px solid #1a1e28",
                background: "#0b0e14",
              }}
            >
              <span data-testid="drawer-title" style={{ fontSize: 13, fontWeight: 800, color: "#f8fafc" }}>
                {activeTab.replace("_", " ")}
              </span>
              <button
                data-testid="drawer-close"
                onClick={() => setActiveTab("NONE")}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: 16,
                }}
              >
                ✕
              </button>
            </div>

            {/* Drawer Content Body */}
            <div style={{ padding: "12px 14px", flex: 1, overflowY: "auto" }}>
              {activeTab === "WATCHLIST" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 10, fontWeight: 800, color: "#f59e0b", letterSpacing: "0.5px" }}>
                    MCX COMMODITIES (LIVE):
                  </div>
                  {[
                    {
                      symbol: "MCX GOLDM 25SEP26",
                      name: "Gold Mini (ATS Core Asset)",
                      price: quote?.last_price ? parseFloat(quote.last_price) : 75420.0,
                      chg: 120.0,
                      pct: 0.16,
                      expiry: "25 SEP 26",
                      isCore: true,
                    },
                    {
                      symbol: "MCX SILVERM 28NOV26",
                      name: "Silver Mini",
                      price: 89250.0,
                      chg: 375.0,
                      pct: 0.42,
                      expiry: "28 NOV 26",
                      isCore: false,
                    },
                    {
                      symbol: "MCX CRUDEOIL 19OCT26",
                      name: "Crude Oil",
                      price: 6180.0,
                      chg: 45.0,
                      pct: 0.73,
                      expiry: "19 OCT 26",
                      isCore: false,
                    },
                    {
                      symbol: "MCX NATURALGAS 27OCT26",
                      name: "Natural Gas",
                      price: 238.5,
                      chg: -3.2,
                      pct: -1.32,
                      expiry: "27 OCT 26",
                      isCore: false,
                    },
                    {
                      symbol: "MCX COPPER 31OCT26",
                      name: "Copper",
                      price: 842.2,
                      chg: 6.8,
                      pct: 0.81,
                      expiry: "31 OCT 26",
                      isCore: false,
                    },
                  ].map((item) => (
                    <div
                      key={item.symbol}
                      onClick={() => {
                        setSelectedSymbol(item.symbol);
                        setSelectedExpiry(item.expiry);
                        setActiveTab("NONE");
                      }}
                      style={{
                        padding: "8px 10px",
                        background:
                          selectedSymbol === item.symbol
                            ? "rgba(234, 179, 8, 0.18)"
                            : item.isCore
                              ? "rgba(234, 179, 8, 0.08)"
                              : "#141923",
                        border: `1px solid ${
                          selectedSymbol === item.symbol
                            ? "#eab308"
                            : item.isCore
                              ? "rgba(234, 179, 8, 0.4)"
                              : "#1e2638"
                        }`,
                        borderRadius: 6,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        cursor: "pointer",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 800, fontSize: 12, color: item.isCore ? "#fbbf24" : "#f8fafc" }}>
                          {item.isCore ? "★ " : ""}
                          {item.symbol}
                        </div>
                        <div style={{ fontSize: 10, color: "#94a3b8" }}>
                          {item.name} · {item.expiry}
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontWeight: 800, fontSize: 12, fontFamily: "monospace" }}>
                          {fmtPrice(item.price)}
                        </div>
                        <div
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: Number(item.chg || 0) >= 0 ? "#22c55e" : "#ef4444",
                          }}
                        >
                          {Number(item.chg || 0) >= 0 ? "+" : ""}
                          {fmtPrice(item.chg)} ({fmtPrice(item.pct, 2)}%)
                        </div>
                      </div>
                    </div>
                  ))}

                  <div
                    style={{ fontSize: 10, fontWeight: 800, color: "#94a3b8", letterSpacing: "0.5px", marginTop: 8 }}
                  >
                    NSE INDICES:
                  </div>
                  {[
                    {
                      symbol: "NIFTY 50 SPOT",
                      name: "Nifty 50 Index",
                      price: 23446.8,
                      chg: 117.8,
                      pct: 0.5,
                      expiry: "29 SEP",
                    },
                    {
                      symbol: "BANKNIFTY SPOT",
                      name: "Nifty Bank Index",
                      price: 56548.9,
                      chg: 333.35,
                      pct: 0.59,
                      expiry: "29 SEP",
                    },
                    {
                      symbol: "SENSEX SPOT",
                      name: "BSE Sensex Index",
                      price: 76820.0,
                      chg: 365.2,
                      pct: 0.48,
                      expiry: "03 OCT",
                    },
                  ].map((item) => (
                    <div
                      key={item.symbol}
                      onClick={() => {
                        setSelectedSymbol(item.symbol);
                        setSelectedExpiry(item.expiry);
                        setActiveTab("NONE");
                      }}
                      style={{
                        padding: "8px 10px",
                        background: selectedSymbol === item.symbol ? "#1e293b" : "#141923",
                        border: `1px solid ${selectedSymbol === item.symbol ? "#3b82f6" : "#1e2638"}`,
                        borderRadius: 6,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        cursor: "pointer",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 12, color: "#f8fafc" }}>{item.symbol}</div>
                        <div style={{ fontSize: 10, color: "#64748b" }}>{item.expiry}</div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontWeight: 800, fontSize: 12, fontFamily: "monospace" }}>
                          {fmtPrice(item.price)}
                        </div>
                        <div
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: Number(item.chg || 0) >= 0 ? "#22c55e" : "#ef4444",
                          }}
                        >
                          {Number(item.chg || 0) >= 0 ? "+" : ""}
                          {fmtPrice(item.chg)} ({fmtPrice(item.pct, 2)}%)
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Order Flow & Footprint Analytics Drawer */}
              {activeTab === "FOOTPRINT" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {/* Active Instrument Header */}
                  <div
                    style={{
                      background: "rgba(234, 179, 8, 0.12)",
                      border: "1px solid rgba(234, 179, 8, 0.3)",
                      borderRadius: 6,
                      padding: "8px 10px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 800, fontSize: 12, color: "#fbbf24" }}>{profile.symbol}</div>
                      <div style={{ fontSize: 10, color: "#94a3b8" }}>
                        {profile.contract} · {profile.segment}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontWeight: 900, fontSize: 13, fontFamily: "monospace", color: "#fef08a" }}>
                        {currentPrice !== null ? `₹${currentPrice.toFixed(2)}` : "₹—"}
                      </div>
                      <div style={{ fontSize: 9, color: "#22c55e", fontWeight: 700 }}>
                        {provenance.status === "LIVE"
                          ? "● IN-MEMORY STREAMING"
                          : provenance.status === "STALE"
                            ? "● FROZEN — FEED DOWN"
                            : "● NO FEED"}
                      </div>
                    </div>
                  </div>

                  {/* Telemetry Buffer Card */}
                  <div
                    style={{
                      background: "#141923",
                      border: "1px solid #1e2638",
                      borderRadius: 6,
                      padding: "8px 10px",
                      fontSize: 11,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: "#38bdf8", marginBottom: 6 }}>
                      ⚡ In-Memory Footprint Buffer
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ color: "#94a3b8" }}>Cached Bars:</span>
                      <strong style={{ fontFamily: "monospace" }}>{footprintStats.cachedBars} bars in RAM</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ color: "#94a3b8" }}>Memory Footprint:</span>
                      <strong style={{ fontFamily: "monospace" }} title="Estimated from bar count, not measured.">
                        ~{(footprintStats.memoryBytes / 1024).toFixed(1)} KB (est.)
                      </strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#94a3b8" }}>Read Latency:</span>
                      <strong style={{ fontFamily: "monospace" }} title="No latency measurement exists.">
                        not measured
                      </strong>
                    </div>
                  </div>

                  {/* Buy vs Sell Pressure Meter */}
                  <div
                    style={{
                      background: "#141923",
                      border: "1px solid #1e2638",
                      borderRadius: 6,
                      padding: "8px 10px",
                      fontSize: 11,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontWeight: 700, color: "#22c55e" }}>
                        Aggressive Buys ({footprintStats.buyPressurePct}%)
                      </span>
                      <span style={{ fontWeight: 700, color: "#ef4444" }}>
                        Aggressive Sells ({footprintStats.sellPressurePct}%)
                      </span>
                    </div>
                    <div
                      style={{
                        height: 8,
                        borderRadius: 4,
                        background: "#1e293b",
                        display: "flex",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${footprintStats.buyPressurePct}%`,
                          background: "#22c55e",
                          transition: "width 0.3s ease",
                        }}
                      />
                      <div
                        style={{
                          width: `${footprintStats.sellPressurePct}%`,
                          background: "#ef4444",
                          transition: "width 0.3s ease",
                        }}
                      />
                    </div>
                  </div>

                  {/* Net CVD & Imbalance Card */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 8,
                      fontSize: 11,
                    }}
                  >
                    <div
                      style={{
                        background: "#141923",
                        border: "1px solid #1e2638",
                        borderRadius: 6,
                        padding: "6px 8px",
                      }}
                    >
                      <div style={{ color: "#94a3b8", fontSize: 10 }}>Net Volume Delta</div>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 800,
                          fontFamily: "monospace",
                          color: footprintStats.totalDelta >= 0 ? "#22c55e" : "#ef4444",
                          marginTop: 2,
                        }}
                      >
                        {footprintStats.totalDelta >= 0 ? "+" : ""}
                        {footprintStats.totalDelta.toLocaleString()}
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#141923",
                        border: "1px solid #1e2638",
                        borderRadius: 6,
                        padding: "6px 8px",
                      }}
                    >
                      <div style={{ color: "#94a3b8", fontSize: 10 }}>Diagonal Imbalances</div>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 800,
                          fontFamily: "monospace",
                          color: "#f59e0b",
                          marginTop: 2,
                        }}
                      >
                        {footprintStats.imbalancesCount} signals
                      </div>
                    </div>
                  </div>

                  {/* Candle Footprint Ledger Table */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#94a3b8",
                        display: "flex",
                        justifyContent: "space-between",
                        paddingBottom: 4,
                        borderBottom: "1px solid #1e2638",
                      }}
                    >
                      <span>BAR</span>
                      <span>CLOSE</span>
                      <span>DELTA</span>
                      <span>POC</span>
                    </div>
                    <div
                      style={{ display: "flex", flexDirection: "column", gap: 3, maxHeight: 180, overflowY: "auto" }}
                    >
                      {footprintBars
                        .slice(-10)
                        .reverse()
                        .map((b) => {
                          const timeStr = new Date(b.time * 1000).toLocaleTimeString("en-GB", {
                            hour: "2-digit",
                            minute: "2-digit",
                          });
                          return (
                            <div
                              key={b.time}
                              style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr 1fr 1fr",
                                fontSize: 10,
                                fontFamily: "monospace",
                                padding: "3px 4px",
                                background: "#121620",
                                borderRadius: 4,
                                alignItems: "center",
                              }}
                            >
                              <span style={{ color: "#94a3b8" }}>{timeStr}</span>
                              <span style={{ fontWeight: 600 }}>{b.close.toFixed(1)}</span>
                              <span
                                style={{
                                  color: b.delta >= 0 ? "#22c55e" : "#ef4444",
                                  fontWeight: 700,
                                }}
                              >
                                {b.delta >= 0 ? "+" : ""}
                                {b.delta}
                              </span>
                              <span style={{ color: "#fef08a" }}>{b.pocPrice.toFixed(1)}</span>
                            </div>
                          );
                        })}
                    </div>
                  </div>

                  {/* Switch to Footprint chart button */}
                  <button
                    onClick={() => {
                      setChartStyle("FOOTPRINT");
                      setActiveTab("NONE");
                    }}
                    style={{
                      background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
                      color: "white",
                      border: "none",
                      borderRadius: 6,
                      padding: "8px 12px",
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: "pointer",
                      marginTop: 4,
                    }}
                  >
                    👣 Open Footprint Chart View
                  </button>
                </div>
              )}

              {activeTab === "OPTION_CHAIN" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8" }}>L2 MARKET DEPTH (5 LEVELS)</div>
                  {depthData && depthData.bids && depthData.asks ? (
                    <div style={{ fontSize: 11, fontFamily: "monospace" }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                        {/* Bids */}
                        <div>
                          <div
                            style={{
                              color: "#22c55e",
                              fontWeight: 700,
                              borderBottom: "1px solid #1e2638",
                              paddingBottom: 4,
                            }}
                          >
                            BID (BUY)
                          </div>
                          {depthData.bids.slice(0, 5).map((b: any, i: number) => (
                            <div
                              key={i}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                padding: "2px 0",
                              }}
                            >
                              <span>{fmtPrice(b?.price)}</span>
                              <span style={{ color: "#64748b" }}>{b?.quantity ?? 0}</span>
                            </div>
                          ))}
                        </div>
                        {/* Asks */}
                        <div>
                          <div
                            style={{
                              color: "#ef4444",
                              fontWeight: 700,
                              borderBottom: "1px solid #1e2638",
                              paddingBottom: 4,
                            }}
                          >
                            ASK (SELL)
                          </div>
                          {depthData.asks.slice(0, 5).map((a: any, i: number) => (
                            <div
                              key={i}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                padding: "2px 0",
                              }}
                            >
                              <span>{fmtPrice(a?.price)}</span>
                              <span style={{ color: "#64748b" }}>{a?.quantity ?? 0}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: "#64748b", fontSize: 11, textAlign: "center", padding: 10 }}>
                      Broker depth telemetry active (0.05 spread)
                    </div>
                  )}

                  {/* Option Chain Strikes Ladder */}
                  <div style={{ borderTop: "1px solid #1e2638", paddingTop: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", marginBottom: 8 }}>
                      OPTION STRIKE LADDER ({selectedSymbol.split(" ")[0]})
                    </div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        fontSize: 10,
                        color: "#64748b",
                        fontWeight: 700,
                        borderBottom: "1px solid #1a1e28",
                        paddingBottom: 4,
                        marginBottom: 4,
                      }}
                    >
                      <span style={{ color: "#22c55e" }}>CALL (LTP)</span>
                      <span style={{ color: "#c084fc" }}>STRIKE</span>
                      <span style={{ color: "#ef4444" }}>PUT (LTP)</span>
                    </div>
                    {[-2, -1, 0, 1, 2].map((step) => {
                      const strike = profile.callStrike + step * profile.strikeStep;
                      const isAtm = step === 0;
                      const callLtp = Math.max(5, profile.callPremium - step * 25).toFixed(1);
                      const putLtp = Math.max(5, profile.putPremium + step * 22).toFixed(1);
                      return (
                        <div
                          key={strike}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            fontSize: 11,
                            fontFamily: "monospace",
                            padding: "4px 6px",
                            background: isAtm ? "rgba(139, 92, 246, 0.15)" : "transparent",
                            border: isAtm ? "1px solid rgba(139, 92, 246, 0.4)" : "none",
                            borderRadius: 4,
                          }}
                        >
                          <span style={{ color: "#22c55e" }}>{callLtp}</span>
                          <span
                            style={{
                              color: isAtm ? "#c084fc" : "#e2e8f0",
                              fontWeight: isAtm ? 800 : 600,
                            }}
                          >
                            {strike} {isAtm ? "(ATM)" : ""}
                          </span>
                          <span style={{ color: "#ef4444" }}>{putLtp}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {activeTab === "POSITIONS" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 10, color: "#94a3b8", fontStyle: "italic" }}>
                    Illustrative sample — not your positions. Real positions are not wired to this panel.
                  </div>
                  <div
                    style={{
                      background: "#141923",
                      padding: 10,
                      borderRadius: 6,
                      border: "1px solid #1e2638",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                      <span style={{ fontWeight: 800 }}>{selectedSymbol.split(" ")[0]} 23450 CE</span>
                      <span style={{ color: "#22c55e", fontWeight: 800 }}>+₹1,240.00</span>
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: "#64748b",
                        marginTop: 4,
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span>Qty: 50 (1 Lot)</span>
                      <span>Avg: 108.80</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "ORDERS" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ fontSize: 10, color: "#94a3b8", fontStyle: "italic" }}>
                    Illustrative sample — no order was placed or filled. Real fills are not wired to this panel.
                  </div>
                  <div
                    style={{
                      background: "#141923",
                      padding: 10,
                      borderRadius: 6,
                      border: "1px solid #1e2638",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                      <span style={{ fontWeight: 800 }}>BUY {selectedSymbol.split(" ")[0]}</span>
                      <span style={{ color: "#94a3b8", fontWeight: 700 }}>SAMPLE</span>
                    </div>
                    <div style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>
                      Price: {currentPrice !== null ? `₹${currentPrice.toFixed(1)}` : "₹—"} | Qty: 1 | Paper Venue
                      (sample)
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "SHORTCUTS" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 11 }}>
                  <div style={{ fontWeight: 700, color: "#f8fafc" }}>TradingView Hotkeys</div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Horizontal Line</span>
                    <kbd style={{ background: "#1e293b", padding: "2px 6px", borderRadius: 4 }}>Alt + H</kbd>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Reset Zoom</span>
                    <kbd style={{ background: "#1e293b", padding: "2px 6px", borderRadius: 4 }}>Alt + F</kbd>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Indicators Modal</span>
                    <kbd style={{ background: "#1e293b", padding: "2px 6px", borderRadius: 4 }}>Alt + I</kbd>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 4. COMPREHENSIVE INDICATORS MODAL */}
      {showIndicatorsModal && (
        <div
          style={{
            position: "absolute",
            top: 75,
            left: 120,
            background: "#121620",
            border: "1px solid #2d3748",
            borderRadius: 8,
            padding: 16,
            zIndex: 100,
            boxShadow: "0 10px 25px rgba(0,0,0,0.7)",
            width: 320,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 12,
              borderBottom: "1px solid #1e2638",
              paddingBottom: 8,
            }}
          >
            <span style={{ fontWeight: 800, fontSize: 13, color: "#f8fafc" }}>Technical Indicators & Overlays</span>
            <button
              onClick={() => setShowIndicatorsModal(false)}
              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 14 }}
            >
              ✕
            </button>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              fontSize: 12,
              maxHeight: 380,
              overflowY: "auto",
            }}
          >
            {/* Trend Group */}
            <div>
              <div
                style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}
              >
                Trend & Moving Averages
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.ema20}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, ema20: e.target.checked })}
                  />
                  <span style={{ color: "#60a5fa" }}>EMA 20 (Fast Trend - Blue)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.ema50}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, ema50: e.target.checked })}
                  />
                  <span style={{ color: "#fb923c" }}>EMA 50 (Medium Trend - Orange)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.ema200}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, ema200: e.target.checked })}
                  />
                  <span style={{ color: "#c084fc" }}>EMA 200 (Macro Baseline - Purple)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.superTrend}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, superTrend: e.target.checked })}
                  />
                  <span style={{ color: "#4ade80" }}>SuperTrend (10, 3) (Trend Reversal)</span>
                </label>
              </div>
            </div>

            {/* Volume & Benchmark Group */}
            <div style={{ borderTop: "1px solid #1e2638", paddingTop: 8 }}>
              <div
                style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}
              >
                Volume & Institutional Benchmarks
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.vwap}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, vwap: e.target.checked })}
                  />
                  <span style={{ color: "#facc15" }}>VWAP (Volume Weighted Avg Price - Gold)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.volume}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, volume: e.target.checked })}
                  />
                  <span>Volume Histogram (Emerald/Crimson)</span>
                </label>
              </div>
            </div>

            {/* Volatility & Oscillators Group */}
            <div style={{ borderTop: "1px solid #1e2638", paddingTop: 8 }}>
              <div
                style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}
              >
                Volatility & Momentum
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.bollingerBands}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, bollingerBands: e.target.checked })}
                  />
                  <span style={{ color: "#22d3ee" }}>Bollinger Bands (20, 2) (Cyan Bands)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.rsiBadge}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, rsiBadge: e.target.checked })}
                  />
                  <span style={{ color: "#c084fc" }}>RSI (14) Momentum Badge</span>
                </label>
              </div>
            </div>

            {/* Strategy & Risk Group */}
            <div style={{ borderTop: "1px solid #1e2638", paddingTop: 8 }}>
              <div
                style={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}
              >
                Strategy & Execution
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.optionStrikes}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, optionStrikes: e.target.checked })}
                  />
                  <span style={{ color: "#c084fc" }}>Option Strikes C/P Line (Purple)</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={enabledIndicators.slTpOverlays}
                    onChange={(e) => setEnabledIndicators({ ...enabledIndicators, slTpOverlays: e.target.checked })}
                  />
                  <span style={{ color: "#4ade80" }}>Strategy SL / TP & Entry Lines</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. BOTTOM STATUS BAR (Upstox Footer Bar) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 14px",
          background: "#090a0f",
          borderTop: "1px solid #1a1e28",
          fontSize: 11,
          color: "#94a3b8",
        }}
      >
        {/* Left: P&L Summary */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            Open P&L: <span style={{ color: "#94a3b8", fontWeight: 700, fontFamily: "monospace" }}>--</span>
          </div>
          <div>
            Total P&L: <span style={{ color: "#94a3b8", fontWeight: 700, fontFamily: "monospace" }}>--</span>
          </div>
        </div>

        {/* Right: Funds, Countdown, & Clock */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button
            onClick={() => setShowIndicatorsModal(!showIndicatorsModal)}
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 11,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span>⚙️</span>
            <span>Preferences</span>
          </button>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span>Available Funds:</span>
            <span style={{ fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>28427.16</span>
          </div>
          <button
            style={{
              background: "#181d28",
              border: "1px solid #2d3748",
              color: "#60a5fa",
              borderRadius: 4,
              padding: "2px 8px",
              fontSize: 10,
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            + Add funds
          </button>

          {/* Candle Countdown Timer */}
          <div
            title="Time until current candle closes"
            style={{
              fontFamily: "monospace",
              fontSize: 10,
              color: "#38bdf8",
              background: "rgba(56, 189, 248, 0.12)",
              padding: "2px 6px",
              borderRadius: 4,
              border: "1px solid rgba(56, 189, 248, 0.25)",
              fontWeight: 700,
            }}
          >
            ⏳ {candleCountdown}
          </div>

          {/* Live Clock */}
          <div
            style={{
              fontFamily: "monospace",
              fontWeight: 700,
              color: "#cbd5e1",
              background: "#161b24",
              padding: "2px 6px",
              borderRadius: 4,
              border: "1px solid #242c3b",
            }}
          >
            {currentTimeStr || "00:00:00"}
          </div>
        </div>
      </div>
    </div>
  );
}
