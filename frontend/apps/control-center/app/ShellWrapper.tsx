"use client";
import { useEffect, useState } from "react";
import { Shell } from "../components/Shell";
import type { SystemState, SseStatus } from "@ats/api-client";
import { getApiClient } from "../lib/api";
import { useSse } from "../hooks/useSse";

export function ShellWrapper({ children }: { children: React.ReactNode }) {
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const { status } = useSse();
  useEffect(() => {
    getApiClient()
      .getSystem()
      .then((s) => setSystemState(s.system_state))
      .catch(() => setSystemState("UNKNOWN"));
  }, []);
  return <Shell systemState={systemState} sseStatus={status as SseStatus}>{children}</Shell>;
}
