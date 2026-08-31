"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { getApiClient } from "../lib/api";

export function useOperatorIntelligence(pollMs = 4000) {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getApiClient().getOperatorIntelligence();
      setSnapshot(data);
      setError(null);
    } catch {
      setError("Operator intelligence unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    timer.current = window.setInterval(() => void refresh(), pollMs);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [refresh, pollMs]);

  return { snapshot, loading, error, refresh };
}
