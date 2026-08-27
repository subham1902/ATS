"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { OperatorIntelligenceView } from "../../components/operator-intelligence/OperatorIntelligenceView";
import { getApiClient } from "../../lib/api";

const MATERIAL_EVENTS = [
  "CANDIDATE_CREATED",
  "RISK_EVALUATED",
  "SUPERVISOR_EVALUATED",
  "POSITION_OPENED",
  "POSITION_UPDATED",
  "POSITION_CLOSED",
] as const;

export default function OperatorIntelligencePage() {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | undefined>();
  const [connectionState, setConnectionState] = useState<"CONNECTING" | "LIVE" | "UNAVAILABLE">(
    "CONNECTING",
  );
  const client = useMemo(() => getApiClient(), []);

  const refresh = useCallback(async () => {
    try {
      const next = await client.getOperatorIntelligence();
      setSnapshot(next);
      setConnectionState("LIVE");
    } catch {
      setConnectionState("UNAVAILABLE");
    }
  }, [client]);

  useEffect(() => {
    void refresh();
    const events = new EventSource(client.operatorIntelligenceStreamUrl());
    const refreshFromMaterialEvent = () => void refresh();
    for (const eventKind of MATERIAL_EVENTS) {
      events.addEventListener(eventKind, refreshFromMaterialEvent);
    }
    events.onopen = () => setConnectionState("LIVE");
    events.onerror = () => setConnectionState("UNAVAILABLE");
    return () => {
      for (const eventKind of MATERIAL_EVENTS) {
        events.removeEventListener(eventKind, refreshFromMaterialEvent);
      }
      events.close();
    };
  }, [refresh]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div
        role="status"
        style={{
          fontSize: 12,
          color: connectionState === "LIVE" ? "#166534" : "#92400e",
          background: connectionState === "LIVE" ? "#f0fdf4" : "#fffbeb",
          border: `1px solid ${connectionState === "LIVE" ? "#bbf7d0" : "#fde68a"}`,
          borderRadius: 8,
          padding: "7px 12px",
        }}
      >
        Operator read model: {connectionState}. Dashboard connectivity is observability-only and
        never gates ATS decisions.
      </div>
      <OperatorIntelligenceView initialSnapshot={snapshot} isLiveAvailable={snapshot !== undefined} />
    </div>
  );
}
