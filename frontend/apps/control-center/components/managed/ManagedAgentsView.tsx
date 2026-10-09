"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { ManagedAgent } from "@ats/api-client";
import { box, btn, errorMessage, fieldStyle, fmtTime, type ManagedApi } from "./shared";
import { ManagedAgentWizard } from "./ManagedAgentWizard";

export function ManagedAgentsView(props: { api: ManagedApi; onCreated?: (agent: ManagedAgent) => void }) {
  const { api, onCreated } = props;
  const [agents, setAgents] = useState<ManagedAgent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [type, setType] = useState("ALL");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setAgents((await api.listManagedAgents(showArchived)).agents);
    } catch (e) {
      setError(errorMessage(e));
      setAgents([]);
    }
  }, [api, showArchived]);

  useEffect(() => {
    void load();
  }, [load]);

  const types = useMemo(() => Array.from(new Set((agents ?? []).map((a) => a.agent_type))).sort(), [agents]);
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (agents ?? []).filter(
      (a) =>
        (!q || a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)) &&
        (status === "ALL" || a.status === status) &&
        (type === "ALL" || a.agent_type === type),
    );
  }, [agents, search, status, type]);

  return (
    <div style={{ padding: 24 }}>
      <h1>Managed Agents</h1>
      <p style={{ opacity: 0.8 }}>
        Configurable research agents. They can analyze and propose; they cannot authorize or execute trades. The{" "}
        <Link href="/agents">Agents Playground</Link> provides these same research templates and bounded quote jobs.
      </p>

      {adding ? (
        <ManagedAgentWizard
          api={api}
          onCancel={() => setAdding(false)}
          onCreated={(agent) => {
            setAdding(false);
            onCreated?.(agent);
            void load();
          }}
        />
      ) : (
        <button type="button" style={btn} onClick={() => setAdding(true)}>
          + Add Agent
        </button>
      )}

      <div style={{ ...box, marginTop: 16 }}>
        <label htmlFor="ma-search">Search</label>
        <input id="ma-search" style={fieldStyle} value={search} onChange={(e) => setSearch(e.target.value)} />
        <label htmlFor="ma-status" style={{ marginRight: 8 }}>
          Status
        </label>
        <select id="ma-status" value={status} onChange={(e) => setStatus(e.target.value)}>
          {["ALL", "DISABLED", "IDLE", "RUNNING", "ERROR", "ARCHIVED"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>{" "}
        <label htmlFor="ma-type-filter" style={{ marginRight: 8 }}>
          Type
        </label>
        <select id="ma-type-filter" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="ALL">ALL</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>{" "}
        <label>
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Show
          archived
        </label>
      </div>

      {error ? (
        <p role="alert" style={{ color: "#b42318" }}>
          Could not load managed agents: {error}
        </p>
      ) : null}
      {agents === null ? <p>Loading…</p> : null}
      {agents !== null && !error && agents.length === 0 ? (
        <p>No managed agents yet. Use “+ Add Agent” to create one; new agents start disabled.</p>
      ) : null}
      {agents !== null && agents.length > 0 && visible.length === 0 ? (
        <p>No agents match the current filters.</p>
      ) : null}

      {visible.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {[
                "Name",
                "Type",
                "Provider / model",
                "Enabled",
                "Status",
                "Config",
                "Capabilities",
                "Last run",
                "Last error",
              ].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: 6 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((a) => (
              <tr key={a.agent_id}>
                <td style={{ padding: 6 }}>
                  <Link href={`/agents/managed/${a.agent_id}`}>{a.name}</Link>
                </td>
                <td style={{ padding: 6 }}>{a.agent_type}</td>
                <td style={{ padding: 6 }}>
                  {a.provider || "—"} / {a.model || "—"}
                </td>
                <td style={{ padding: 6 }}>{a.enabled ? "Enabled" : "Disabled"}</td>
                <td style={{ padding: 6 }}>{a.status}</td>
                <td style={{ padding: 6 }}>v{a.current_config_version}</td>
                <td style={{ padding: 6 }}>{a.capabilities.length}</td>
                <td style={{ padding: 6 }}>{fmtTime(a.last_run_at)}</td>
                <td style={{ padding: 6 }}>{a.last_error ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
