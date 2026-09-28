"use client";
import React, { createContext, useContext, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { StreamEvent, SseStatus } from "@ats/api-client";
import { parseSseFrame } from "@ats/api-client";
import { getApiClient } from "../lib/api";

export interface SseContextValue {
  status: SseStatus;
  events: StreamEvent[];
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

const SseContext = createContext<SseContextValue | null>(null);

function useLocalSse(): SseContextValue {
  const [status, setStatus] = useState<SseStatus>("disconnected");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const attemptRef = useRef<number>(0);

  const connect = useCallback(async () => {
    abortRef.current?.abort();
    if (reconnectTimer.current) {
      window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    setStatus("connecting");
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const url = getApiClient().streamUrl();
      const res = await fetch(url, {
        headers: { Accept: "text/event-stream" },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`SSE ${res.status}`);
      }
      attemptRef.current = 0;
      setStatus("connected");
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
          const parsed = parseSseFrame(frame);
          if (parsed) {
            setEvents((prev) => [...prev.slice(-199), parsed.data]);
          }
        }
      }
      if (!controller.signal.aborted) {
        setStatus("disconnected");
        attemptRef.current += 1;
        // Exponential backoff with full jitter: min(30s, 2^n * 1s + rand(0, 1s))
        const delay = Math.min(30000, Math.pow(2, Math.min(attemptRef.current, 5)) * 1000 + Math.random() * 1000);
        reconnectTimer.current = window.setTimeout(() => connect(), Math.round(delay));
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
      attemptRef.current += 1;
      const delay = Math.min(30000, Math.pow(2, Math.min(attemptRef.current, 5)) * 1000 + Math.random() * 1000);
      reconnectTimer.current = window.setTimeout(() => connect(), Math.round(delay));
    }
  }, []);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    if (reconnectTimer.current) {
      window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    setStatus("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { status, events, error, reconnect: connect, disconnect };
}

export function SseProvider({ children }: { children: ReactNode }) {
  const value = useLocalSse();
  return <SseContext.Provider value={value}>{children}</SseContext.Provider>;
}

export function useSse(): SseContextValue {
  const context = useContext(SseContext);
  // If inside an SseProvider, return the singleton instance. Otherwise fall back to a local hook.
  if (context) {
    return context;
  }
  return useLocalSse();
}
