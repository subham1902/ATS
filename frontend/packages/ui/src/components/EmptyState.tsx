export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        padding: "16px",
        borderRadius: 8,
        background: "#f9fafb",
        border: "1px dashed #d1d5db",
        color: "#374151",
        textAlign: "center",
      }}
    >
      <div style={{ fontWeight: 600 }}>{message}</div>
      {hint ? <div style={{ marginTop: 4, fontSize: 13, color: "#6b7280" }}>{hint}</div> : null}
    </div>
  );
}
