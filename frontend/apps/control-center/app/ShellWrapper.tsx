"use client";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Shell } from "../components/Shell";
import type { SystemState, SseStatus } from "@ats/api-client";
import { getApiClient } from "../lib/api";
import { SseProvider, useSse } from "../hooks/useSse";
import { DataSourceProvider } from "../lib/dataSource";

function ShellContent({ children }: { children: ReactNode }) {
  // null = not yet loaded. A failed fetch is UNKNOWN, never a healthy state:
  // reporting READY when the control plane cannot be reached is exactly how an
  // operator gets told a dead system is fine.
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const { status } = useSse();

  const checkState = useCallback(() => {
    getApiClient()
      .getSystem()
      .then((s) => setSystemState(s.system_state))
      .catch(() => setSystemState("UNKNOWN"));
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
      <DataSourceProvider>
        <ShellContent>{children}</ShellContent>
      </DataSourceProvider>
    </SseProvider>
  );
}
