import type { ReactNode } from "react";

export type HealthState = "HEALTHY" | "READY" | "ACTIVE" | "DEGRADED" | "STALE" | "UNKNOWN" | "BLOCKED" | "HALTED" | "OFFLINE";

const presentation: Record<HealthState, { icon: string; color: string; background: string; border: string }> = {
  HEALTHY: { icon: "●", color: "#067647", background: "#ecfdf3", border: "#abefc6" },
  READY: { icon: "●", color: "#067647", background: "#ecfdf3", border: "#abefc6" },
  ACTIVE: { icon: "◆", color: "#175cd3", background: "#eff8ff", border: "#b2ddff" },
  DEGRADED: { icon: "▲", color: "#b54708", background: "#fffaeb", border: "#fedf89" },
  STALE: { icon: "◷", color: "#b54708", background: "#fffaeb", border: "#fedf89" },
  UNKNOWN: { icon: "?", color: "#475467", background: "#f2f4f7", border: "#d0d5dd" },
  BLOCKED: { icon: "⊘", color: "#b42318", background: "#fef3f2", border: "#fecdca" },
  HALTED: { icon: "■", color: "#b42318", background: "#fef3f2", border: "#fecdca" },
  OFFLINE: { icon: "○", color: "#475467", background: "#f2f4f7", border: "#d0d5dd" },
};

export function SystemHealthIndicator({ state, label, detail, compact = false }: { state: HealthState; label?: ReactNode; detail?: string | null; compact?: boolean }) {
  const style = presentation[state];
  return (
    <span className="health-indicator" data-state={state} title={detail ?? undefined} aria-label={`${label ? `${String(label)} ` : ""}${state}${detail ? `. ${detail}` : ""}`} style={{ display: "inline-flex", alignItems: "center", gap: 5, minHeight: compact ? 22 : 26, maxWidth: "100%", padding: compact ? "2px 6px" : "3px 8px", border: `1px solid ${style.border}`, borderRadius: 999, background: style.background, color: style.color, fontSize: compact ? 10 : 11, fontWeight: 800, letterSpacing: ".035em", whiteSpace: "nowrap" }}>
      <span aria-hidden="true" style={{ fontSize: 9 }}>{style.icon}</span>
      {label ? <span style={{ color: "#475467", fontWeight: 700 }}>{label}</span> : null}
      <span>{state}</span>
    </span>
  );
}

export function StatusBadge({ state, children, title }: { state: HealthState; children?: ReactNode; title?: string }) {
  return <SystemHealthIndicator state={state} label={children} detail={title} compact />;
}
