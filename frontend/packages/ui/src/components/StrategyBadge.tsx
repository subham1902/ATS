import type { ReactNode } from "react";

const BADGE_CONFIG: Record<
  string,
  { icon: string; label: string; bg: string; border: string; color: string; tooltip: string }
> = {
  SCALPING: {
    icon: "⚡",
    label: "Scalping",
    bg: "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)",
    border: "#d97706",
    color: "#92400e",
    tooltip: "Sub-5m holding, high-frequency entries",
  },
  INTRADAY: {
    icon: "📊",
    label: "Intraday",
    bg: "linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)",
    border: "#3b82f6",
    color: "#1e40af",
    tooltip: "Session-bound, exits before market close",
  },
  SWING: {
    icon: "📈",
    label: "Swing",
    bg: "linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)",
    border: "#10b981",
    color: "#065f46",
    tooltip: "Multi-day holding period",
  },
  POSITIONAL: {
    icon: "🏗️",
    label: "Positional",
    bg: "linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)",
    border: "#8b5cf6",
    color: "#5b21b6",
    tooltip: "Week+ holding, structural thesis",
  },
  LONG_TERM: {
    icon: "🏔️",
    label: "Long Term",
    bg: "linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%)",
    border: "#ec4899",
    color: "#9d174d",
    tooltip: "Multi-week to month holding",
  },
  META_ROUTER: {
    icon: "🔀",
    label: "Meta Router",
    bg: "linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%)",
    border: "#a855f7",
    color: "#6b21a8",
    tooltip: "Strategy router / ensemble / meta-learning",
  },
  BASELINE: {
    icon: "📐",
    label: "Baseline",
    bg: "linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%)",
    border: "#9ca3af",
    color: "#374151",
    tooltip: "Benchmark reference strategy",
  },
};

export function StrategyBadge({
  badge,
  size = "normal",
}: {
  badge: string;
  size?: "small" | "normal" | "large";
}) {
  const config = BADGE_CONFIG[badge] ?? BADGE_CONFIG.BASELINE;
  const fontSize = size === "small" ? 10 : size === "large" ? 13 : 11;
  const padding = size === "small" ? "1px 5px" : size === "large" ? "4px 10px" : "2px 7px";

  return (
    <span
      title={config.tooltip}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        padding,
        borderRadius: 6,
        fontSize,
        fontWeight: 700,
        background: config.bg,
        border: `1px solid ${config.border}`,
        color: config.color,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
        cursor: "default",
        transition: "transform 0.15s ease",
      }}
    >
      <span style={{ fontSize: fontSize + 1 }}>{config.icon}</span>
      {config.label}
    </span>
  );
}
