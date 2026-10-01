"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError } from "@ats/api-client";
import type {
  ManagedAgent,
  ManagedAgentConfig,
  ManagedAgentConfigVersion,
  ManagedAgentRun,
  ManagedAgentSchema,
} from "@ats/api-client";
import {
  box,
  btn,
  btnDanger,
  CheckboxGroup,
  CREDENTIAL_REF_HINT,
  errorMessage,
  fieldStyle,
  fmtTime,
  NAME_HINT,
  SAFETY_STATEMENT,
  type ManagedApi,
} from "./shared";

function isConflict(e: unknown): boolean {
  return e instanceof ApiError && e.status === 409 && /changed since you opened it/.test(e.message);
}

const EDITABLE_KEYS: (keyof ManagedAgentConfig)[] = [
  "name",
  "description",
  "agent_type",
  "provider",
  "model",
  "system_instructions",
  "capabilities",
  "data_scopes",
  "research_scopes",
  "timeout_s",
  "max_concurrency",
  "credential_ref",
];

function toConfig(a: ManagedAgent): ManagedAgentConfig {
  return {
    name: a.name,
    description: a.description,
    agent_type: a.agent_type,
    provider: a.provider,
    model: a.model,
    system_instructions: a.system_instructions,
    capabilities: [...a.capabilities],
    data_scopes: [...a.data_scopes],
    research_scopes: [...a.research_scopes],
    timeout_s: a.timeout_s,
    max_concurrency: a.max_concurrency,
    credential_ref: a.credential_ref,
  };
}

export function ManagedAgentDetail(props: {
  api: ManagedApi;
  agentId: string;
  /** Called after the agent is gone from the active roster (archived/hard-deleted) or duplicated. */
  onNavigate?: (href: string) => void;
}) {
  const { api, agentId, onNavigate } = props;
  const [agent, setAgent] = useState<ManagedAgent | null>(null);
  const [versions, setVersions] = useState<ManagedAgentConfigVersion[]>([]);
  const [runs, setRuns] = useState<ManagedAgentRun[]>([]);
  const [schema, setSchema] = useState<ManagedAgentSchema | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mode, setMode] = useState<"view" | "edit" | "duplicate" | "archive">("view");
  const [draft, setDraft] = useState<ManagedAgentConfig | null>(null);
  const [dupName, setDupName] = useState("");
  const [hardAck, setHardAck] = useState(false);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [a, v, r] = await Promise.all([
        api.getManagedAgent(agentId),
        api.listManagedAgentVersions(agentId),
        api.listManagedAgentRuns(agentId),
      ]);
      setAgent(a.agent);
      setVersions(v.versions);
      setRuns(r.runs);
    } catch (e) {
      setLoadError(errorMessage(e));
    }
  }, [api, agentId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let live = true;
    api
      .getManagedAgentSchema()
      .then((s) => {
        if (live) setSchema(s);
      })
      .catch(() => undefined); // Edit simply stays unavailable without the schema.
    return () => {
      live = false;
    };
  }, [api]);

  if (loadError)
    return (
      <div style={{ padding: 24 }}>
        <p role="alert" style={{ color: "#b42318" }}>
          Could not load agent: {loadError}
        </p>
        <Link href="/agents/managed">Back to Managed Agents</Link>
      </div>
    );
  if (!agent) return <div style={{ padding: 24 }}>Loading…</div>;

  const archived = agent.archived_at !== null;

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setActionError(null);
    setNotice(null);
    try {
      await fn();
      setNotice(done);
      await load();
    } catch (e) {
      setActionError(errorMessage(e));
    }
  };

  const toggle = () =>
    run(
      () => (agent.enabled ? api.disableManagedAgent(agent.agent_id) : api.enableManagedAgent(agent.agent_id)),
      agent.enabled
        ? "Agent disabled. No new runs will start; a run already in progress is not cancelled."
        : "Agent enabled.",
    );

  const saveEdit = async () => {
    if (!draft) return;
    if (!NAME_HINT.test(draft.name.trim()))
      return setActionError("Name must be 1-64 chars: letters, digits, space, _ or -.");
    if (draft.credential_ref && !CREDENTIAL_REF_HINT.test(draft.credential_ref))
      return setActionError("Credential reference must be an environment variable NAME, never a secret value.");
    const base = toConfig(agent);
    const changed: Partial<ManagedAgentConfig> = {};
    for (const k of EDITABLE_KEYS) {
      if (JSON.stringify(draft[k]) !== JSON.stringify(base[k])) (changed as Record<string, unknown>)[k] = draft[k];
    }
    if (Object.keys(changed).length === 0) return setActionError("No changes to save.");
    setActionError(null);
    try {
      const { agent: updated } = await api.updateManagedAgent(agent.agent_id, {
        ...changed,
        expected_version: agent.current_config_version,
      });
      setMode("view");
      setNotice(`Saved as configuration v${updated.current_config_version}. Earlier versions and runs are unchanged.`);
      await load();
    } catch (e) {
      setActionError(isConflict(e) ? "This agent changed since you opened it. Reload before saving." : errorMessage(e));
    }
  };

  const doDuplicate = async () => {
    if (!NAME_HINT.test(dupName.trim()))
      return setActionError("Name must be 1-64 chars: letters, digits, space, _ or -.");
    setActionError(null);
    try {
      const { agent: copy } = await api.duplicateManagedAgent(agent.agent_id, dupName.trim());
      setMode("view");
      setNotice(`Created “${copy.name}” (disabled, independent history).`);
      onNavigate?.(`/agents/managed/${copy.agent_id}`);
    } catch (e) {
      setActionError(errorMessage(e));
    }
  };

  const doArchive = async () => {
    setActionError(null);
    try {
      await api.deleteManagedAgent(agent.agent_id);
      setMode("view");
      setNotice("Agent archived. Its runs and configuration history remain available.");
      await load();
    } catch (e) {
      setActionError(errorMessage(e));
    }
  };

  const doHardDelete = async () => {
    setActionError(null);
    try {
      await api.deleteManagedAgent(agent.agent_id, { hard: true, confirm: true });
      onNavigate?.("/agents/managed");
    } catch (e) {
      // The server decides eligibility; surface its reason and steer to archive.
      setActionError(`${errorMessage(e)} — use Archive instead.`);
    }
  };

  const row = (label: string, value: React.ReactNode) => (
    <>
      <dt style={{ fontWeight: 600 }}>{label}</dt>
      <dd style={{ margin: "0 0 8px" }}>{value}</dd>
    </>
  );

  return (
    <div style={{ padding: 24 }}>
      <p>
        <Link href="/agents/managed">← Managed Agents</Link>
      </p>
      <h1>{agent.name}</h1>
      <p>
        <strong>{agent.status}</strong> · configuration v{agent.current_config_version}
        {archived ? " · archived" : ""}
      </p>
      <p style={{ opacity: 0.8 }}>{SAFETY_STATEMENT}</p>

      {notice ? <p role="status">{notice}</p> : null}
      {actionError ? (
        <p role="alert" style={{ color: "#b42318" }}>
          {actionError}
        </p>
      ) : null}

      {!archived && mode === "view" && (
        <div style={{ marginBottom: 16 }}>
          <button type="button" style={btn} onClick={toggle}>
            {agent.enabled ? "Disable" : "Enable"}
          </button>
          <button
            type="button"
            style={btn}
            disabled={!schema}
            onClick={() => {
              setDraft(toConfig(agent));
              setActionError(null);
              setMode("edit");
            }}
          >
            Edit
          </button>
          <button
            type="button"
            style={btn}
            onClick={() => {
              setDupName(`${agent.name} copy`.slice(0, 64));
              setActionError(null);
              setMode("duplicate");
            }}
          >
            Duplicate
          </button>
          <button
            type="button"
            style={btnDanger}
            onClick={() => {
              setActionError(null);
              setMode("archive");
            }}
          >
            Archive
          </button>
        </div>
      )}

      {mode === "archive" && (
        <section style={box} aria-label="Confirm archive">
          <p>
            <strong>Archive “{agent.name}”?</strong>
          </p>
          <ul>
            <li>The agent becomes archived and is disabled.</li>
            <li>Its previous runs and research evidence remain available.</li>
            <li>Its configuration history remains available.</li>
          </ul>
          <button type="button" style={btnDanger} onClick={doArchive}>
            Confirm archive
          </button>
          <button type="button" style={btn} onClick={() => setMode("view")}>
            Cancel
          </button>
        </section>
      )}

      {mode === "duplicate" && (
        <section style={box} aria-label="Duplicate agent">
          <label htmlFor="dup-name">Name for the copy</label>
          <input id="dup-name" style={fieldStyle} value={dupName} onChange={(e) => setDupName(e.target.value)} />
          <p style={{ opacity: 0.75 }}>
            The copy gets its own identity and history, starts DISABLED, and does not inherit runs.
          </p>
          <button type="button" style={btn} onClick={doDuplicate}>
            Create copy
          </button>
          <button type="button" style={btn} onClick={() => setMode("view")}>
            Cancel
          </button>
        </section>
      )}

      {mode === "edit" && draft && schema && (
        <section style={box} aria-label="Edit agent">
          <p>
            Saving creates configuration <strong>v{agent.current_config_version + 1}</strong>. Previous versions and
            past runs keep the version they ran under.
          </p>
          <label htmlFor="ed-name">Name</label>
          <input
            id="ed-name"
            style={fieldStyle}
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <label htmlFor="ed-desc" style={{ display: "block", marginTop: 8 }}>
            Description
          </label>
          <textarea
            id="ed-desc"
            style={fieldStyle}
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          />
          <label htmlFor="ed-provider" style={{ display: "block", marginTop: 8 }}>
            Provider
          </label>
          <input
            id="ed-provider"
            style={fieldStyle}
            value={draft.provider}
            onChange={(e) => setDraft({ ...draft, provider: e.target.value })}
          />
          <label htmlFor="ed-model" style={{ display: "block", marginTop: 8 }}>
            Model
          </label>
          <input
            id="ed-model"
            style={fieldStyle}
            value={draft.model}
            onChange={(e) => setDraft({ ...draft, model: e.target.value })}
          />
          <label htmlFor="ed-cred" style={{ display: "block", marginTop: 8 }}>
            Credential reference (environment variable name)
          </label>
          <input
            id="ed-cred"
            style={fieldStyle}
            autoComplete="off"
            value={draft.credential_ref ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, credential_ref: e.target.value.trim() === "" ? null : e.target.value.trim() })
            }
          />
          <label htmlFor="ed-instr" style={{ display: "block", marginTop: 8 }}>
            System instructions
          </label>
          <textarea
            id="ed-instr"
            rows={5}
            style={fieldStyle}
            value={draft.system_instructions}
            onChange={(e) => setDraft({ ...draft, system_instructions: e.target.value })}
          />
          <CheckboxGroup
            legend="Capabilities"
            options={schema.capabilities}
            value={draft.capabilities}
            onChange={(v) => setDraft({ ...draft, capabilities: v })}
          />
          <CheckboxGroup
            legend="Data access"
            options={schema.data_scopes}
            value={draft.data_scopes}
            onChange={(v) => setDraft({ ...draft, data_scopes: v })}
          />
          <CheckboxGroup
            legend="Research scope"
            options={schema.research_scopes}
            value={draft.research_scopes}
            onChange={(v) => setDraft({ ...draft, research_scopes: v })}
          />
          <label htmlFor="ed-timeout">Timeout (seconds)</label>
          <input
            id="ed-timeout"
            type="number"
            style={fieldStyle}
            value={draft.timeout_s}
            onChange={(e) => setDraft({ ...draft, timeout_s: Number(e.target.value) })}
          />
          <label htmlFor="ed-conc" style={{ display: "block", marginTop: 8 }}>
            Max concurrency
          </label>
          <input
            id="ed-conc"
            type="number"
            style={fieldStyle}
            value={draft.max_concurrency}
            onChange={(e) => setDraft({ ...draft, max_concurrency: Number(e.target.value) })}
          />
          <div style={{ marginTop: 12 }}>
            <button type="button" style={btn} onClick={saveEdit}>
              Save new version
            </button>
            <button type="button" style={btn} onClick={() => setMode("view")}>
              Cancel
            </button>
            <button
              type="button"
              style={btn}
              onClick={() => {
                setMode("view");
                setActionError(null);
                void load();
              }}
            >
              Reload latest
            </button>
          </div>
        </section>
      )}

      <section style={box} aria-label="Configuration">
        <h2 style={{ marginTop: 0 }}>Configuration</h2>
        <dl>
          {row("Description", agent.description || "—")}
          {row("Type", agent.agent_type)}
          {row("Provider / model", `${agent.provider || "—"} / ${agent.model || "—"}`)}
          {row("Enabled", agent.enabled ? "Yes" : "No")}
          {row("Credential reference", agent.credential_ref ?? "none")}
          {row("Capabilities", agent.capabilities.join(", ") || "none")}
          {row("Data access", agent.data_scopes.join(", ") || "none")}
          {row("Research scope", agent.research_scopes.join(", ") || "none")}
          {row("Runtime limits", `${agent.timeout_s}s timeout, concurrency ${agent.max_concurrency}`)}
          {row("Created", fmtTime(agent.created_at))}
          {row("Updated", fmtTime(agent.updated_at))}
          {row("Last run", fmtTime(agent.last_run_at))}
          {row("Last error", agent.last_error ?? "—")}
          {archived ? row("Archived", fmtTime(agent.archived_at)) : null}
        </dl>
      </section>

      <section style={box} aria-label="Recent runs">
        <h2 style={{ marginTop: 0 }}>Recent runs</h2>
        {runs.length === 0 ? (
          <p>No runs recorded.</p>
        ) : (
          <ul>
            {runs.map((r) => (
              <li key={r.run_id}>
                {fmtTime(r.started_at)} · {r.status} · ran under config v{r.config_version}
                {r.error ? ` · ${r.error}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={box} aria-label="Configuration history">
        <h2 style={{ marginTop: 0 }}>Configuration history</h2>
        <ul>
          {[...versions]
            .sort((a, b) => b.version - a.version)
            .map((v) => (
              <li key={v.version}>
                v{v.version} · {v.reason} · {fmtTime(v.created_at)}
              </li>
            ))}
        </ul>
      </section>

      <details style={box}>
        <summary>Advanced: permanent deletion</summary>
        <p>
          Permanent deletion is only accepted by the server for an agent that never ran and has a single configuration
          version. Otherwise archive it.
        </p>
        <label>
          <input type="checkbox" checked={hardAck} onChange={(e) => setHardAck(e.target.checked)} /> I understand this
          permanently erases the agent
        </label>
        <div style={{ marginTop: 8 }}>
          <button type="button" style={btnDanger} disabled={!hardAck} onClick={doHardDelete}>
            Delete permanently
          </button>
        </div>
      </details>
    </div>
  );
}
