"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { StreamEvent } from "@ats/api-client";
import { parseSseFrame, type SseStatus } from "@ats/api-client";
import { getApiClient } from "../lib/api";

export function useSse() {
  const [status, setStatus] = useState<SseStatus>("disconnected");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const reconnectTimer = useRef<number | null>(null);

  const connect = useCallback(async () => {
    abortRef.current?.abort();
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
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
      setStatus("connected");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!controller.signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // Frames delimited by blank line
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
        // Reconnect after delay, but do not fabricate continuity
        reconnectTimer.current = window.setTimeout(() => connect(), 3000);
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setStatus("error");
      setError(e instanceof Error ? e.message : String(e));
      // reconnect
      reconnectTimer.current = window.setTimeout(() => connect(), 5000);
    }
  }, []);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
    setStatus("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { status, events, error, reconnect: connect, disconnect };
}
