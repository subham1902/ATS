export function ServiceSummary({ state }: { state: unknown }) {
  if (!state || typeof state !== "object" || Array.isArray(state)) return null;
  const fields = Object.entries(state).filter(
    ([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value),
  );
  if (!fields.length) return null;
  return (
    <dl className="metric-grid">
      {fields.map(([key, value]) => (
        <div className="metric-card" key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{value === null ? "UNKNOWN" : typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
