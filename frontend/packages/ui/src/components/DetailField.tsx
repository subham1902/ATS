export function DetailField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <dt style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#6b7280" }}>
        {label}
      </dt>
      <dd
        style={{
          margin: 0,
          fontSize: 13,
          color: "#111827",
          fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined,
          wordBreak: "break-all",
        }}
      >
        {value}
      </dd>
    </div>
  );
}
