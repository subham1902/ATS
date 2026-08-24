import { Badge } from "./Badge";

export type SystemState = "READY" | "DEGRADED" | "RECONCILING" | "HALTED" | "UNKNOWN";

const label: Record<SystemState, string> = {
  READY: "READY",
  DEGRADED: "DEGRADED",
  RECONCILING: "RECONCILING",
  HALTED: "HALTED",
  UNKNOWN: "UNKNOWN",
};

const tone: Record<SystemState, "success" | "warn" | "danger" | "neutral" | "unknown"> = {
  READY: "success",
  DEGRADED: "warn",
  RECONCILING: "warn",
  HALTED: "danger",
  UNKNOWN: "unknown",
};

const icon: Record<SystemState, string> = {
  READY: "●",
  DEGRADED: "◐",
  RECONCILING: "⟳",
  HALTED: "■",
  UNKNOWN: "?",
};

export function SystemStateBadge({ state }: { state: SystemState }) {
  return (
    <Badge tone={tone[state]} ariaLabel={`system state ${state}`}>
      <span aria-hidden>{icon[state]}</span> {label[state]}
      {state === "UNKNOWN" ? <span aria-hidden style={{ opacity: 0.8 }}> — unknown, not healthy</span> : null}
    </Badge>
  );
}
