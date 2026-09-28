"use client";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Shell } from "../components/Shell";
import type { SystemState, SseStatus } from "@ats/api-client";
import { getApiClient } from "../lib/api";
import { SseProvider, useSse } from "../hooks/useSse";

function ShellContent({ children }: { children: ReactNode }) {
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const { status } = useSse();

  const checkState = useCallback(() => {
    getApiClient()
      .getSystem()
      .then((s) => setSystemState(s.system_state))
      .catch(() => setSystemState("READY"));
  }, []);

  useEffect(() => {
    checkState();
    const interval = window.setInterval(checkState, 5000);
    return () => window.clearInterval(interval);
  }, [checkState]);

  return (
    <Shell systemState={systemState} sseStatus={status as SseStatus}>
      {children}
    </Shell>
  );
}

export function ShellWrapper({ children }: { children: ReactNode }) {
  return (
    <SseProvider>
      <ShellContent>{children}</ShellContent>
    </SseProvider>
  );
}
