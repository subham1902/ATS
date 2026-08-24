import type { ReactNode } from "react";

export function Card({
  title,
  children,
  actions,
  labelledBy,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  labelledBy?: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy ?? undefined}
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: 16,
        background: "white",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <h2 id={labelledBy} style={{ margin: 0, fontSize: 14, fontWeight: 700, letterSpacing: "0.02em", textTransform: "uppercase", color: "#374151" }}>
          {title}
        </h2>
        {actions}
      </div>
      <div>{children}</div>
    </section>
  );
}
