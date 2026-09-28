"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CandleView,
  FeedHealthView,
  MarketInterval,
  MarketQuoteView,
  SseStatus,
} from "@ats/api-client";
import { parseMarketSseFrame } from "@ats/api-client/sse";
import { getApiClient } from "../lib/api";

export interface MarketFeedState {
  connectionStatus: SseStatus;
  streamTransport: "WEBSOCKET" | "SSE" | "DISCONNECTED";
  quote: MarketQuoteView | null;
  health: FeedHealthView | null;
  prediction: any | null;
  candles: CandleView[];
  interval: MarketInterval;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
  setInterval: (interval: MarketInterval) => void;
}

export function useMarketFeed(
  instrument?: string,
  initialInterval: MarketInterval = "5m",
): MarketFeedState {
  const [connectionStatus, setConnectionStatus] = useState<SseStatus>("disconnected");
  const [streamTransport, setStreamTransport] = useState<"WEBSOCKET" | "SSE" | "DISCONNECTED">("DISCONNECTED");
  const [quote, setQuote] = useState<MarketQuoteView | null>(null);
  const [health, setHealth] = useState<FeedHealthView | null>(null);
  const [prediction, setPrediction] = useState<any | null>(null);
  const [candles, setCandles] = useState<CandleView[]>([]);
  const [interval, setInterval] = useState<MarketInterval>(initialInterval);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const sseAbortRef = useRef<AbortController | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const pingTimer = useRef<number | null>(null);
  const intervalRef = useRef<MarketInterval>(interval);
  intervalRef.current = interval;

  // 1. Initial historical candle bootstrap
  const loadCandles = useCallback(async (intvl: MarketInterval) => {
    try {
      const client = getApiClient();
      const series = await client.getMarketCandles(intvl, instrument);
      if (series && series.candles) {
        setCandles(series.candles);
      }
    } catch (e) {
      console.error("Failed to load historical candles:", e);
    }
  }, [instrument]);

  useEffect(() => {
    loadCandles(interval);
  }, [interval, loadCandles]);

  // 2. Disconnect everything cleanly
  const disconnect = useCallback(() => {
    if (pingTimer.current) {
      window.clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
    if (reconnectTimer.current) {
      window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    reconnectAttemptRef.current = 0;
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    sseAbortRef.current?.abort();
    sseAbortRef.current = null;
    setConnectionStatus("disconnected");
    setStreamTransport("DISCONNECTED");
  }, []);

  // 3. Fallback to SSE Stream if WebSocket unavailable
  const startSseFallback = useCallback(() => {
    if (sseAbortRef.current) return;
    setConnectionStatus("connecting");
    setStreamTransport("SSE");

    const controller = new AbortController();
    sseAbortRef.current = controller;

    async function runSse() {
      try {
        const url = getApiClient().marketStreamUrl(instrument);
        const res = await fetch(url, {
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`Market SSE HTTP ${res.status}`);
        }

        setConnectionStatus("connected");
        loadCandles(intervalRef.current);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!controller.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const parsed = parseMarketSseFrame(frame);
            if (!parsed) continue;

            const data = parsed.data;
            if (data.frame_kind === "FEED_STATE" && data.health) {
              setHealth(data.health);
            } else if (data.frame_kind === "PREDICTION" && data.prediction) {
              setPrediction(data.prediction);
            } else if (data.frame_kind === "TICK" && data.quote) {
              const newQuote = data.quote;
              if (instrument && newQuote.instrument_key !== instrument) continue;
              setQuote(newQuote);

              if (newQuote.last_price !== null && newQuote.last_price !== undefined) {
                const price = newQuote.last_price;
                const tickTime = newQuote.exchange_timestamp
                  ? new Date(newQuote.exchange_timestamp).getTime()
                  : Date.now();

                setCandles((prev) => {
                  if (prev.length === 0) return prev;
                  const last = prev[prev.length - 1];
                  const closeTime = new Date(last.bar_close).getTime();

                  if (!last.is_closed && tickTime < closeTime) {
                    const updated: CandleView = {
                      ...last,
                      high: last.high === null ? price : parseFloat(price) > parseFloat(last.high) ? price : last.high,
                      low: last.low === null ? price : parseFloat(price) < parseFloat(last.low) ? price : last.low,
                      close: price,
                      volume: newQuote.volume ?? last.volume,
                      open_interest: newQuote.open_interest ?? last.open_interest,
                      tick_count: last.tick_count + 1,
                    };
                    return [...prev.slice(0, -1), updated];
                  } else if (tickTime >= closeTime) {
                    const sealed: CandleView = { ...last, is_closed: true };
                    const intvlSec = intervalRef.current === "5m" ? 300 : intervalRef.current === "15m" ? 900 : 3600;
                    const newStart = new Date(closeTime).toISOString();
                    const newClose = new Date(closeTime + intvlSec * 1000).toISOString();

                    const newCandle: CandleView = {
                      bar_start: newStart,
                      bar_close: newClose,
                      open: price,
                      high: price,
                      low: price,
                      close: price,
                      volume: newQuote.volume,
                      open_interest: newQuote.open_interest,
                      tick_count: 1,
                      is_closed: false,
                    };
                    return [...prev.slice(0, -1), sealed, newCandle];
                  }
                  return prev;
                });
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setConnectionStatus("error");
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    }

    runSse();
  }, [instrument, loadCandles]);

  // 4. Primary WebSocket Connection to ATS Stream Hub
  const connect = useCallback(() => {
    disconnect();
    setConnectionStatus("connecting");
    setError(null);

    // Build WebSocket URL
    const isClient = typeof window !== "undefined";
    const host = isClient ? window.location.hostname : "127.0.0.1";
    const wsUrl = `ws://${host}:8000/v1/stream/market`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        setConnectionStatus("connected");
        setStreamTransport("WEBSOCKET");
        loadCandles(intervalRef.current);

        // Subscribe to desired instrument and interval
        ws.send(
          JSON.stringify({
            action: "subscribe",
            instrument_key: instrument || "MCX_FO|569003",
            interval: intervalRef.current,
            channels: ["candle", "quote", "depth", "oi", "feed_health", "market_status"],
          })
        );

        // Setup ping keepalive
        pingTimer.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "ping" }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        try {
          const envelope = JSON.parse(event.data);
          const type = envelope.type;

          if (type === "candle_update") {
            const bar = envelope.bar;
            if (envelope.interval === intervalRef.current && bar) {
              const p = String(bar.close);
              setCandles((prev) => {
                if (prev.length === 0) {
                  return [
                    {
                      bar_start: bar.time,
                      bar_close: bar.time,
                      open: String(bar.open),
                      high: String(bar.high),
                      low: String(bar.low),
                      close: String(bar.close),
                      volume: bar.volume,
                      open_interest: bar.open_interest,
                      tick_count: bar.tick_count || 1,
                      is_closed: false,
                    },
                  ];
                }
                const last = prev[prev.length - 1];
                const updated: CandleView = {
                  ...last,
                  open: String(bar.open),
                  high: String(bar.high),
                  low: String(bar.low),
                  close: String(bar.close),
                  volume: bar.volume ?? last.volume,
                  open_interest: bar.open_interest ?? last.open_interest,
                  tick_count: bar.tick_count ?? (last.tick_count + 1),
                  is_closed: false,
                };
                return [...prev.slice(0, -1), updated];
              });
            }
          } else if (type === "candle_closed") {
            const bar = envelope.bar;
            if (envelope.interval === intervalRef.current && bar) {
              setCandles((prev) => {
                if (prev.length === 0) return prev;
                const last = prev[prev.length - 1];
                const sealed: CandleView = {
                  ...last,
                  open: String(bar.open),
                  high: String(bar.high),
                  low: String(bar.low),
                  close: String(bar.close),
                  volume: bar.volume ?? last.volume,
                  open_interest: bar.open_interest ?? last.open_interest,
                  is_closed: true,
                };
                return [...prev.slice(0, -1), sealed];
              });
            }
          } else if (type === "quote") {
            const q = envelope.quote;
            if (q) {
              const qView: MarketQuoteView = {
                instrument_key: envelope.instrument_key || "MCX_FO|569003",
                state: "LIVE",
                contract: null,
                last_price: q.ltp != null ? String(q.ltp) : null,
                bid_price: q.bid != null ? String(q.bid) : null,
                ask_price: q.ask != null ? String(q.ask) : null,
                bid_quantity: 1,
                ask_quantity: 1,
                spread: q.ask != null && q.bid != null ? String(q.ask - q.bid) : null,
                volume: q.volume,
                open_interest: q.open_interest,
                open_interest_change: null,
                exchange_timestamp: q.exchange_timestamp,
                received_at: envelope.time || new Date().toISOString(),
                age_ms: 50,
                source: envelope.source || "BROKER",
                authority_class: "LIVE_FEED_ATTACHED",
                reason_codes: [],
              };
              setQuote(qView);

              // Live tick incremental update for active candle
              if (q.ltp != null) {
                const price = String(q.ltp);
                const pNum = q.ltp;
                setCandles((prev) => {
                  if (prev.length === 0) return prev;
                  const last = prev[prev.length - 1];
                  if (!last.is_closed) {
                    const curHigh = last.high != null ? parseFloat(last.high) : pNum;
                    const curLow = last.low != null ? parseFloat(last.low) : pNum;
                    const updated: CandleView = {
                      ...last,
                      high: pNum > curHigh ? price : last.high,
                      low: pNum < curLow ? price : last.low,
                      close: price,
                      volume: q.volume ?? last.volume,
                      open_interest: q.open_interest ?? last.open_interest,
                      tick_count: last.tick_count + 1,
                    };
                    return [...prev.slice(0, -1), updated];
                  }
                  return prev;
                });
              }
            }
          } else if (type === "feed_health") {
            if (envelope.health) {
              setHealth((prev) => ({
                ...(prev || {}),
                ...envelope.health,
              } as FeedHealthView));
            }
          }
        } catch (err) {
          console.debug("Failed to parse WebSocket envelope:", err);
        }
      };

      ws.onerror = (e) => {
        console.warn("WebSocket error, falling back to SSE:", e);
        startSseFallback();
      };

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
          startSseFallback();
          reconnectAttemptRef.current += 1;
          const base = Math.min(30000, 1000 * Math.pow(2, Math.min(reconnectAttemptRef.current, 5)));
          const jitter = Math.random() * 1000;
          const delay = Math.round(base + jitter);
          reconnectTimer.current = window.setTimeout(() => connect(), delay);
        }
      };
    } catch (e) {
      console.warn("Could not initiate WebSocket, using SSE fallback:", e);
      startSseFallback();
    }
  }, [disconnect, instrument, loadCandles, startSseFallback]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Dynamic interval switch
  const handleSetInterval = useCallback((newInterval: MarketInterval) => {
    setInterval(newInterval);
    intervalRef.current = newInterval;
    loadCandles(newInterval);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          action: "subscribe",
          instrument_key: instrument || "MCX_FO|569003",
          interval: newInterval,
          channels: ["candle", "quote", "depth", "oi", "feed_health", "market_status"],
        })
      );
    }
  }, [instrument, loadCandles]);

  return {
    connectionStatus,
    streamTransport,
    quote,
    health,
    prediction,
    candles,
    interval,
    error,
    reconnect: connect,
    disconnect,
    setInterval: handleSetInterval,
  };
}
