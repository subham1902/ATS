import type { ReactNode } from "react";

export function MetricStrip({ items, ariaLabel = "Key metrics" }: { items: Array<{ label: string; value: ReactNode; tone?: "positive" | "negative" | "neutral"; hint?: string }>; ariaLabel?: string }) {
  return (
    <dl aria-label={ariaLabel} style={{ margin: 0, display: "grid", gridTemplateColumns: `repeat(${Math.min(items.length, 6)}, minmax(92px, 1fr))`, border: "1px solid var(--ats-border)", borderRadius: "var(--ats-radius)", background: "white", overflow: "hidden" }}>
      {items.map((item) => <div key={item.label} title={item.hint} style={{ minWidth: 0, padding: "10px 12px", borderRight: "1px solid #edf0f2" }}><dt style={{ color: "var(--ats-muted)", fontSize: 10, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase" }}>{item.label}</dt><dd className={item.tone === "positive" ? "ats-positive" : item.tone === "negative" ? "ats-negative" : undefined} style={{ margin: "3px 0 0", fontSize: 16, fontWeight: 750, fontVariantNumeric: "tabular-nums", overflow: "hidden", textOverflow: "ellipsis" }}>{item.value}</dd></div>)}
    </dl>
  );
}
