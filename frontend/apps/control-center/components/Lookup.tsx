"use client";
import { useState } from "react";
import { isApiError } from "@ats/api-client";
import type { ErrorEnvelope } from "@ats/api-client";

export function Lookup({
  title,
  placeholder,
  render,
  fetcher,
  emptyMessage,
}: {
  title: string;
  placeholder: string;
  emptyMessage: string;
  fetcher: (id: string) => Promise<unknown>;
  render: (data: unknown, id: string) => React.ReactNode;
}) {
  const [id, setId] = useState("");
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState<ErrorEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const v = await fetcher(id.trim());
      setData(v);
    } catch (err) {
      if (isApiError(err)) setError(err.envelope);
      else setError({ code: "CLIENT_ERROR", message: String(err), correlation_id: "n/a", details: [] });
    } finally {
      setLoading(false);
    }
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 800 }}>
      <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{title}</h1>
      <form onSubmit={submit} style={{ display: "flex", gap: 8 }} aria-label={`${title} lookup`}>
        <label htmlFor="lookup-id" style={{ position: "absolute", left: -9999 }}>ID</label>
        <input
          id="lookup-id"
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder={placeholder}
          style={{ flex: 1, padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 8, fontSize: 13 }}
        />
        <button type="submit" disabled={loading} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #111827", background: "#111827", color: "white", fontWeight: 600, cursor: "pointer" }}>
          {loading ? "Loading…" : "Fetch"}
        </button>
      </form>
      {!data && !error ? <div role="status" style={{ padding: 16, background: "#f9fafb", border: "1px dashed #d1d5db", borderRadius: 8, textAlign: "center", color: "#6b7280" }}>{emptyMessage}</div> : null}
      {data ? render(data, id) : null}
      {error ? (
        <div role="alert" style={{ padding: 12, border: "1px solid #fecaca", background: "#fef2f2", borderRadius: 8 }}>
          <strong>{error.code}</strong> — {error.message}
          <div style={{ fontSize: 11, marginTop: 4 }}>correlation {error.correlation_id}</div>
        </div>
      ) : null}
    </div>
  );
}
