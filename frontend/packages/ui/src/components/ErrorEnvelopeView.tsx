export interface ErrorEnvelopeShape {
  code: string;
  message: string;
  correlation_id: string;
  details: { field: string | null; issue: string }[];
}

export function ErrorEnvelopeView({ envelope, status }: { envelope: ErrorEnvelopeShape | null; status?: number }) {
  if (!envelope) {
    return (
      <div role="alert" style={{ padding: 12, border: "1px solid #fecaca", background: "#fef2f2", borderRadius: 8, color: "#7f1d1d" }}>
        <strong>Request failed{status ? ` (${status})` : ""}</strong>
        <div style={{ fontSize: 13, marginTop: 4 }}>No typed error envelope returned.</div>
      </div>
    );
  }
  return (
    <div role="alert" style={{ padding: 12, border: "1px solid #fecaca", background: "#fef2f2", borderRadius: 8, color: "#7f1d1d" }}>
      <div style={{ fontWeight: 700 }}>
        {envelope.code} {status ? `· ${status}` : ""}
      </div>
      <div style={{ marginTop: 4 }}>{envelope.message}</div>
      <div style={{ marginTop: 8, fontSize: 12, color: "#991b1b" }}>
        <span>correlation ID: </span>
        <code style={{ background: "white", padding: "1px 4px", borderRadius: 4 }}>{envelope.correlation_id}</code>
      </div>
      {envelope.details.length > 0 ? (
        <ul style={{ marginTop: 8, paddingLeft: 16, fontSize: 13 }}>
          {envelope.details.map((d: { field: string | null; issue: string }, i: number) => (
            <li key={i}>
              {d.field ? <><code>{d.field}</code>: </> : null}
              {d.issue}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
