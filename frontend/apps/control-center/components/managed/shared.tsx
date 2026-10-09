"use client";

import React from "react";
import type { ApiClient, ManagedAgentConfig } from "@ats/api-client";

export type ManagedApi = Pick<
  ApiClient,
  | "getManagedAgentSchema"
  | "listManagedAgents"
  | "getManagedAgent"
  | "createManagedAgent"
  | "updateManagedAgent"
  | "enableManagedAgent"
  | "disableManagedAgent"
  | "duplicateManagedAgent"
  | "deleteManagedAgent"
  | "listManagedAgentVersions"
  | "listManagedAgentRuns"
>;

/** UX hints only. The server stays authoritative for every rule. */
export const NAME_HINT = /^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$/;
export const CREDENTIAL_REF_HINT = /^[A-Z][A-Z0-9_]{1,63}$/;

export const SAFETY_STATEMENT = "This agent can research, analyze and propose. It cannot authorize or execute trades.";

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Request failed";
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export const box: React.CSSProperties = {
  border: "1px solid var(--border, #d0d7de)",
  background: "white",
  borderRadius: 10,
  padding: 24,
  marginBottom: 16,
};
export const fieldStyle: React.CSSProperties = { display: "block", width: "100%", padding: 6, marginTop: 4 };
export const btn: React.CSSProperties = { padding: "6px 14px", cursor: "pointer", marginRight: 8 };
export const btnDanger: React.CSSProperties = { ...btn, color: "#b42318" };

export function CheckboxGroup(props: {
  legend: string;
  options: string[];
  value: string[];
  onChange: (next: string[]) => void;
  hint?: string;
}) {
  const { legend, options, value, onChange, hint } = props;
  return (
    <fieldset style={{ border: "none", padding: 0, margin: "0 0 12px" }}>
      <legend style={{ fontWeight: 600 }}>{legend}</legend>
      {hint ? <p style={{ margin: "4px 0", opacity: 0.75 }}>{hint}</p> : null}
      {options.map((opt) => (
        <label key={opt} style={{ display: "block", padding: "2px 0" }}>
          <input
            type="checkbox"
            checked={value.includes(opt)}
            onChange={(e) => onChange(e.target.checked ? [...value, opt] : value.filter((v) => v !== opt))}
          />{" "}
          {opt}
        </label>
      ))}
    </fieldset>
  );
}

export function emptyConfig(agentType: string): ManagedAgentConfig {
  return {
    name: "",
    description: "",
    agent_type: agentType,
    provider: "",
    model: "",
    system_instructions: "",
    capabilities: [],
    data_scopes: [],
    research_scopes: [],
    timeout_s: 300,
    max_concurrency: 1,
    credential_ref: null,
  };
}
