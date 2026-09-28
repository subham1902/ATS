export function PerformanceMetric({
  label,
  value,
  unit = "",
  trend,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "flat";
  tone?: "positive" | "negative" | "neutral" | "warn";
}) {
  const toneColors: Record<string, { value: string; bg: string }> = {
    positive: { value: "#16a34a", bg: "#f0fdf4" },
    negative: { value: "#dc2626", bg: "#fef2f2" },
    warn: { value: "#d97706", bg: "#fffbeb" },
    neutral: { value: "#111827", bg: "#f9fafb" },
  };
  const c = toneColors[tone];
  const trendIcon = trend === "up" ? "▲" : trend === "down" ? "▼" : trend === "flat" ? "—" : "";
  const trendColor = trend === "up" ? "#16a34a" : trend === "down" ? "#dc2626" : "#6b7280";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        padding: "8px 10px",
        borderRadius: 8,
        background: c.bg,
        border: `1px solid ${c.value}15`,
        minWidth: 80,
      }}
    >
      <div
        style={{ fontSize: 10, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}
      >
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
        <span
          style={{
            fontSize: 16,
            fontWeight: 900,
            fontFamily: "monospace",
            color: c.value,
          }}
        >
          {value}
        </span>
        {unit && <span style={{ fontSize: 10, color: "#6b7280", fontWeight: 500 }}>{unit}</span>}
        {trendIcon && (
          <span style={{ fontSize: 9, color: trendColor, fontWeight: 700, marginLeft: 2 }}>{trendIcon}</span>
        )}
      </div>
    </div>
  );
}
