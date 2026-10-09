"use client";
import { useEffect, useState } from "react";
import type { Candle } from "./candle-store";

export interface Quote {
  canonical_symbol: "XAUUSD";
  broker_symbol: string;
  source: "MT4" | "MT5";
  state: string;
  bid_price: string | null;
  ask_price: string | null;
  last_price: string | null;
  spread: string | null;
  exchange_timestamp: string | null;
  received_at: string | null;
  freshness_ms: number | null;
  tick_volume: string | null;
  real_volume: string | null;
  volume_provenance: string;
  market_session: string;
}
export interface Footprint {
  provenance: "BROKER_TICK_PROXY";
  reason?: string;
  levels: { price: string; tick_count: number; up_ticks: number; down_ticks: number }[];
  inference_method?: string;
}

export function useMetaTraderFeed(interval = "5m", accountId = "") {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [footprint, setFootprint] = useState<Footprint | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const accountQuery = accountId ? `account_id=${encodeURIComponent(accountId)}` : "";
    const refresh = async () => {
      try {
        const responses = await Promise.all([
          fetch(`/v1/market/quote?${accountQuery}`, { signal: controller.signal }),
          fetch(`/v1/market/candles?interval=${interval}&${accountQuery}`, { signal: controller.signal }),
          fetch(`/v1/market/footprint?${accountQuery}`, { signal: controller.signal }),
        ]);
        if (responses.some((response) => !response.ok)) {
          const failed = responses.find((response) => !response.ok)!;
          if (failed.status === 409)
            throw new Error("Connect and select a MetaTrader account to view its market data.");
          throw new Error("Market data service unavailable. Observations have been cleared.");
        }
        const [q, c, f] = await Promise.all(responses.map((response) => response.json()));
        if (!controller.signal.aborted) {
          setQuote(q);
          setCandles(c.candles);
          setFootprint(f);
          setError(null);
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "MARKET_API_UNAVAILABLE");
          setQuote(null);
          setCandles([]);
          setFootprint(null);
        }
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [interval, accountId]);
  return { quote, candles, footprint, error };
}
