import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
  ariaLabel,
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warn" | "danger" | "unknown";
  ariaLabel?: string;
}) {
  const bg: Record<string, string> = {
    neutral: "#e5e7eb",
    success: "#dcfce7",
    warn: "#fef3c7",
    danger: "#fee2e2",
    unknown: "#f3f4f6",
  };
  const border: Record<string, string> = {
    neutral: "#9ca3af",
    success: "#16a34a",
    warn: "#d97706",
    danger: "#dc2626",
    unknown: "#6b7280",
  };
  return (
    <span
      aria-label={ariaLabel}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: "0.02em",
        background: bg[tone],
        border: `1px ${tone === "unknown" ? "dashed" : "solid"} ${border[tone]}`,
        color: "#111827",
      }}
    >
      {children}
    </span>
  );
}
