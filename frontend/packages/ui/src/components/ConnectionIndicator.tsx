import { Badge } from "./Badge";

export type SseStatus = "connecting" | "connected" | "disconnected" | "error";

export function ConnectionIndicator({ status }: { status: SseStatus }) {
  const map: Record<SseStatus, { tone: "success" | "warn" | "danger" | "neutral"; label: string }> = {
    connected: { tone: "success", label: "SSE connected" },
    connecting: { tone: "warn", label: "SSE connecting" },
    disconnected: { tone: "neutral", label: "SSE disconnected" },
    error: { tone: "danger", label: "SSE error" },
  };
  const v = map[status];
  return (
    <span role="status" aria-live="polite" aria-label={v.label}>
      <Badge tone={v.tone}>{v.label}</Badge>
    </span>
  );
}
