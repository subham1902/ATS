"use client";

import { useMemo } from "react";
import { useOperatorState } from "../system/OperatorStateProvider";
import { StatusBadge, type HealthState } from "../system/SystemHealthIndicator";
import { ConnectionIndicator } from "@ats/ui";
import type { SseStatus } from "@ats/api-client";

function truth(value: string | null | undefined): HealthState {
  if (value === "HEALTHY" || value === "READY") return "HEALTHY";
  if (value === "HALTED") return "HALTED";
  if (value === "DEGRADED" || value === "RECONCILING") return "DEGRADED";
  if (value === "STOPPED" || value === "OFFLINE") return "OFFLINE";
  return "UNKNOWN";
}

function Datum({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" | "warn" }) {
  return (
    <div className="ss-datum">
      <span>{label}</span>
      <strong className={tone === "good" ? "ats-positive" : tone === "bad" ? "ats-negative" : tone === "warn" ? "ss-warn" : undefined}>{value}</strong>
    </div>
  );
}

export function StatusStrip() {
  const { system, runtime, pipeline, harness, sseStatus, loading } = useOperatorState();
  const pnl = useMemo(() => Number(runtime?.pnl.realized ?? 0) + Number(runtime?.pnl.unrealized ?? 0), [runtime?.pnl.realized, runtime?.pnl.unrealized]);
  const session = runtime?.session.phase ?? "UNKNOWN";
  const market = session === "ENTRY_ALLOWED" ? "OPEN" : session === "CLOSED" ? "CLOSED" : session;
  const feedState: HealthState = runtime ? (runtime.feed_healthy ? "HEALTHY" : "STALE") : "UNKNOWN";
  const harnessState = truth(harness?.harness.state);
  const target = harness?.harness.execution_target ?? "PAPER";
  const liveMoney = harness?.harness.live_money ?? "OFF";
  const lossState = runtime?.loss_state ?? "UNKNOWN";

  return (
    <div className="status-strip" aria-live="polite" aria-busy={loading}>
      <StatusBadge state={truth(system?.system_state)}>{system?.halted ? "HALTED" : "SYSTEM"}</StatusBadge>
      <Datum label="MARKET" value={market} tone={market === "OPEN" ? "good" : undefined} />
      <StatusBadge state={feedState}>FEED</StatusBadge>
      <Datum label="SESSION" value={session} />
      <Datum label="TARGET" value={target} />
      <Datum label="USER" value={runtime?.trading_mode.user_selected ?? "UNKNOWN"} />
      <Datum label="EFFECTIVE" value={runtime?.trading_mode.effective ?? "UNKNOWN"} tone={runtime?.trading_mode.effective === "HALTED" ? "bad" : runtime?.trading_mode.deescalation_reason ? "warn" : undefined} />
      <Datum label="MONEY" value={`PAPER · LIVE ${liveMoney}`} tone={liveMoney === "OFF" || liveMoney === "DISABLED" ? "good" : "bad"} />
      <Datum label="LOSS" value={lossState} tone={lossState === "NORMAL" ? "good" : lossState === "HALTED" ? "bad" : "warn"} />
      <StatusBadge state={harnessState}>HARNESS</StatusBadge>
      <div className="ss-sse"><ConnectionIndicator status={sseStatus as SseStatus} /></div>
    </div>
  );
}
