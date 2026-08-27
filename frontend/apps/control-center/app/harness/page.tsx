"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Badge } from "@ats/ui";
import { getApiClient } from "../../lib/api";
import { formatTimeIST } from "../../lib/formatTime";

type HarnessStatus = {
  harness: { state: string; authority: string; version: string; checked_at: string; active_sessions: number; reason_codes: string[]; live_money: string; execution_target: string; real_orders_placed: number };
  llm: { provider: string; primary_model: string; fallback_model: string | null; endpoint: string; health: string; availability: string | null; last_latency_ms: number | null; last_error_code: string | null; requests: number; successes: number; failures: number; retries: number; fallback_count: number } | null;
  agents: Array<{ agent_type: string; status: string; last_trigger_at: string | null; last_latency_ms: number | null; model: string | null }>;
  advisory_recent: Array<{ timestamp: string; prompt_preview: string; provider: string; latency_ms: number; evidence_refs_count: number; answer_preview: string }>;
  safety: Record<string, string>;
};

export default function HarnessPage() {
  const client = useMemo(() => getApiClient(), []);
  const [data, setData] = useState<HarnessStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("Summarize the current market regime and explain why ATS currently has or does not have executable opportunities. Cite only supplied ATS evidence.");
  const [evidence, setEvidence] = useState("");
  const [advisory, setAdvisory] = useState<{ provider: string; answer: string; latency_ms: number | null } | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/v1/harness/status`);
      if (!res.ok) throw new Error(`${res.status}`);
      const j = (await res.json()) as HarnessStatus;
      setData(j);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  const ask = useCallback(async () => {
    setLoading(true);
    setAdvisory(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/v1/harness/advisory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, evidence_summary: evidence, evidence_refs: [] }),
      });
      const j = (await res.json()) as { provider: string; answer: string; latency_ms: number | null };
      if (!res.ok) throw new Error((j as unknown as { detail: string }).detail ?? JSON.stringify(j));
      setAdvisory(j);
      void refresh();
    } catch (e) {
      setAdvisory({ provider: "ERROR", answer: e instanceof Error ? e.message : String(e), latency_ms: null });
    } finally {
      setLoading(false);
    }
  }, [prompt, evidence, refresh]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>Harness Console</h1>
        <span style={{ fontSize: 12, color: "#6b7280" }}>ADVISORY_ONLY · LIVE_MONEY DISABLED · REAL_ORDERS 0</span>
      </div>

      {error && (
        <Card title="Connection">
          <div style={{ fontSize: 12, color: "#b45309" }}>Harness endpoint unavailable: {error}</div>
        </Card>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
        <Card title="Harness">
          {data ? (
            <div style={{ fontSize: 12, lineHeight: 1.6 }}>
              <div><strong>Health:</strong> <Badge tone={data.harness.state === "HEALTHY" ? "success" : data.harness.state === "STOPPED" ? "neutral" : "warn"}>{data.harness.state}</Badge> <span style={{ marginLeft: 8, color: "#6b7280" }}>{data.harness.version}</span></div>
              <div><strong>Authority:</strong> {data.harness.authority}</div>
              <div><strong>Sessions:</strong> {data.harness.active_sessions}</div>
              <div><strong>Checked:</strong> {formatTimeIST(data.harness.checked_at)}</div>
              <div><strong>Reasons:</strong> {data.harness.reason_codes.join(", ") || "—"}</div>
              <div><strong>Execution:</strong> {data.harness.execution_target} · {data.harness.live_money} · real_orders {data.harness.real_orders_placed}</div>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "#6b7280" }}>Loading…</div>
          )}
        </Card>

        <Card title="Local LLM">
          {data?.llm ? (
            <div style={{ fontSize: 12, lineHeight: 1.6 }}>
              <div><strong>Provider:</strong> {data.llm.provider}</div>
              <div><strong>Model:</strong> {data.llm.primary_model} <span style={{ color: "#6b7280" }}>fallback {data.llm.fallback_model ?? "none"}</span></div>
              <div><strong>Endpoint:</strong> <span style={{ fontFamily: "monospace" }}>{data.llm.endpoint}</span></div>
              <div><strong>Health:</strong> {data.llm.health} {data.llm.availability ? `· ${data.llm.availability}` : ""}</div>
              <div><strong>Latency:</strong> {data.llm.last_latency_ms ?? "—"} ms {data.llm.last_error_code ? `· ${data.llm.last_error_code}` : ""}</div>
              <div><strong>Counts:</strong> req {data.llm.requests} ok {data.llm.successes} fail {data.llm.failures} retry {data.llm.retries} fallback {data.llm.fallback_count}</div>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: "#6b7280" }}>{data ? "LLM not attached — deterministic fallback active" : "Loading…"}</div>
          )}
        </Card>
      </div>

      <Card title="Agents">
        {data?.agents?.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
            {data.agents.map((a) => (
              <div key={a.agent_type} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 10, background: "#f8fafc" }}>
                <div style={{ fontSize: 12, fontWeight: 700 }}>{a.agent_type}</div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>Status <Badge tone={a.status === "ACTIVE" ? "success" : a.status === "IDLE" ? "neutral" : "warn"}>{a.status}</Badge></div>
                <div style={{ fontSize: 11, color: "#64748b" }}>Last: {a.last_trigger_at ? formatTimeIST(a.last_trigger_at) : "—"} {a.last_latency_ms ? `· ${a.last_latency_ms}ms` : ""}</div>
                <div style={{ fontSize: 11, color: "#64748b" }}>Model: {a.model ?? "—"}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: "#6b7280" }}>{data ? "No agents registered" : "Loading…"}</div>
        )}
      </Card>

      <Card title="Advisory (Harness → Ollama)">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label style={{ fontSize: 12, fontWeight: 600 }}>Prompt (evidence-backed, ADVISORY_ONLY)</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} style={{ width: "100%", fontSize: 12, padding: 8, borderRadius: 6, border: "1px solid #d1d5db" }} />
          <label style={{ fontSize: 12, fontWeight: 600 }}>Evidence summary (optional — cited refs only)</label>
          <textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} rows={3} placeholder="Paste ATS evidence snapshot or leave blank for general advisory" style={{ width: "100%", fontSize: 12, padding: 8, borderRadius: 6, border: "1px solid #d1d5db" }} />
          <button type="button" onClick={ask} disabled={loading} style={{ alignSelf: "flex-start", padding: "8px 14px", borderRadius: 8, border: "1px solid #111827", background: loading ? "#e5e7eb" : "#111827", color: loading ? "#6b7280" : "white", fontWeight: 700, fontSize: 12, cursor: loading ? "not-allowed" : "pointer" }}>
            {loading ? "Asking…" : "Ask Harness (local Ollama)"}
          </button>
          {advisory && (
            <div style={{ marginTop: 8, padding: 10, background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 12, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Provider: {advisory.provider} {advisory.latency_ms ? `· ${advisory.latency_ms}ms` : ""} · ADVISORY_ONLY</div>
              <div>{advisory.answer}</div>
            </div>
          )}
        </div>
      </Card>

      <Card title="Advisory Timeline">
        {data?.advisory_recent?.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.advisory_recent.slice().reverse().slice(0, 8).map((r, i) => (
              <div key={`${r.timestamp}-${i}`} style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 8, background: "white" }}>
                <div style={{ fontSize: 11, color: "#6b7280" }}>{formatTimeIST(r.timestamp)} · {r.provider} · {r.latency_ms}ms · refs {r.evidence_refs_count}</div>
                <div style={{ fontSize: 12, marginTop: 4, color: "#374151" }}>{r.prompt_preview}</div>
                <div style={{ fontSize: 11, marginTop: 4, color: "#6b7280", whiteSpace: "pre-wrap" }}>{r.answer_preview}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: "#6b7280" }}>No advisories yet — use the prompt box above.</div>
        )}
      </Card>

      <Card title="Safety">
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
          <div><strong>HARNESS AUTHORITY:</strong> {data?.safety?.HARNESS_AUTHORITY ?? "ADVISORY_ONLY"}</div>
          <div><strong>REAL ORDER AUTHORITY:</strong> {data?.safety?.REAL_ORDER_AUTHORITY ?? "NONE"}</div>
          <div><strong>LIVE MONEY:</strong> {data?.safety?.LIVE_MONEY ?? "DISABLED"}</div>
          <div><strong>EXECUTION TARGET:</strong> {data?.safety?.EXECUTION_TARGET ?? "PAPER"}</div>
          <div><strong>REAL ORDERS PLACED:</strong> {data?.safety?.REAL_ORDERS_PLACED ?? "0"}</div>
        </div>
      </Card>
    </div>
  );
}
