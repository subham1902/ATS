"use client";

import React, { useEffect, useState } from "react";
import type { ManagedAgent, ManagedAgentConfig, ManagedAgentSchema } from "@ats/api-client";
import {
  box,
  btn,
  CheckboxGroup,
  CREDENTIAL_REF_HINT,
  emptyConfig,
  errorMessage,
  fieldStyle,
  NAME_HINT,
  SAFETY_STATEMENT,
  type ManagedApi,
} from "./shared";

export const WIZARD_STEPS = [
  "Identity",
  "Provider & Model",
  "Responsibilities",
  "Data Access",
  "Research Scope",
  "Capabilities",
  "Runtime Limits",
  "Review & Create",
] as const;

export function validateStep(step: number, cfg: ManagedAgentConfig, schema: ManagedAgentSchema): string | null {
  switch (step) {
    case 0:
      if (!NAME_HINT.test(cfg.name.trim())) return "Name is required: 1-64 chars, letters, digits, space, _ or -.";
      return null;
    case 1:
      if (!cfg.provider.trim()) return "Provider is required.";
      if (!cfg.model.trim()) return "Model is required.";
      if (cfg.credential_ref && !CREDENTIAL_REF_HINT.test(cfg.credential_ref))
        return "Credential reference must be an environment variable NAME (A-Z, 0-9, _), never a secret value.";
      return null;
    case 5:
      return cfg.capabilities.length === 0 ? "Select at least one capability." : null;
    case 6: {
      const { timeout_s, max_concurrency } = schema.limits;
      if (!(cfg.timeout_s > timeout_s.min_exclusive && cfg.timeout_s <= timeout_s.max))
        return `Timeout must be above ${timeout_s.min_exclusive} and at most ${timeout_s.max} seconds.`;
      if (!(
        Number.isInteger(cfg.max_concurrency) &&
        cfg.max_concurrency >= max_concurrency.min &&
        cfg.max_concurrency <= max_concurrency.max
      ))
        return `Max concurrency must be a whole number from ${max_concurrency.min} to ${max_concurrency.max}.`;
      return null;
    }
    default:
      return null;
  }
}

export function ManagedAgentWizard(props: {
  api: ManagedApi;
  onCreated: (agent: ManagedAgent) => void;
  onCancel: () => void;
}) {
  const { api, onCreated, onCancel } = props;
  const [schema, setSchema] = useState<ManagedAgentSchema | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cfg, setCfg] = useState<ManagedAgentConfig>(emptyConfig(""));
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .getManagedAgentSchema()
      .then((s) => {
        if (!live) return;
        setSchema(s);
        setCfg((c) => ({ ...c, agent_type: c.agent_type || s.agent_types[0] || "" }));
      })
      .catch((e) => {
        if (live) setLoadError(errorMessage(e));
      });
    return () => {
      live = false;
    };
  }, [api]);

  if (loadError)
    return (
      <div role="alert" style={box}>
        Could not load the agent schema: {loadError}
      </div>
    );
  if (!schema) return <div style={box}>Loading…</div>;

  const set = <K extends keyof ManagedAgentConfig>(k: K, v: ManagedAgentConfig[K]) => setCfg((c) => ({ ...c, [k]: v }));

  const next = () => {
    const problem = validateStep(step, cfg, schema);
    setError(problem);
    if (!problem) setStep((s) => s + 1);
  };

  const create = async () => {
    for (let i = 0; i < WIZARD_STEPS.length - 1; i++) {
      const problem = validateStep(i, cfg, schema);
      if (problem) {
        setStep(i);
        setError(problem);
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      const { agent } = await api.createManagedAgent({
        ...cfg,
        name: cfg.name.trim(),
        credential_ref: cfg.credential_ref || null,
      });
      onCreated(agent);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const last = step === WIZARD_STEPS.length - 1;

  return (
    <section aria-label="Add managed agent" style={box}>
      <h2 style={{ marginTop: 0 }}>Add Agent</h2>
      <p aria-live="polite">
        Step {step + 1} of {WIZARD_STEPS.length}: <strong>{WIZARD_STEPS[step]}</strong>
      </p>

      {step === 0 && (
        <div>
          <label htmlFor="ma-name">Name</label>
          <input id="ma-name" style={fieldStyle} value={cfg.name} onChange={(e) => set("name", e.target.value)} />
          <label htmlFor="ma-desc" style={{ display: "block", marginTop: 12 }}>
            Description
          </label>
          <textarea
            id="ma-desc"
            style={fieldStyle}
            value={cfg.description}
            onChange={(e) => set("description", e.target.value)}
          />
          <label htmlFor="ma-type" style={{ display: "block", marginTop: 12 }}>
            Agent type
          </label>
          <select
            id="ma-type"
            style={fieldStyle}
            value={cfg.agent_type}
            onChange={(e) => set("agent_type", e.target.value)}
          >
            {schema.agent_types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      )}

      {step === 1 && (
        <div>
          <label htmlFor="ma-provider">Provider</label>
          <input
            id="ma-provider"
            style={fieldStyle}
            value={cfg.provider}
            onChange={(e) => set("provider", e.target.value)}
          />
          <label htmlFor="ma-model" style={{ display: "block", marginTop: 12 }}>
            Model
          </label>
          <input id="ma-model" style={fieldStyle} value={cfg.model} onChange={(e) => set("model", e.target.value)} />
          <label htmlFor="ma-cred" style={{ display: "block", marginTop: 12 }}>
            Credential reference (environment variable name, optional)
          </label>
          <input
            id="ma-cred"
            style={fieldStyle}
            placeholder="PROVIDER_API_KEY"
            autoComplete="off"
            value={cfg.credential_ref ?? ""}
            onChange={(e) => set("credential_ref", e.target.value.trim() === "" ? null : e.target.value.trim())}
          />
          <p style={{ opacity: 0.75 }}>
            Enter the <em>name</em> of the environment variable that holds the credential. ATS never stores or transmits
            the secret itself — do not paste a key here.
          </p>
        </div>
      )}

      {step === 2 && (
        <div>
          <label htmlFor="ma-instr">System instructions</label>
          <textarea
            id="ma-instr"
            rows={6}
            style={fieldStyle}
            value={cfg.system_instructions}
            onChange={(e) => set("system_instructions", e.target.value)}
          />
          <p style={{ opacity: 0.75 }}>
            Instructions describe the agent&apos;s job. They do not grant any authority: what an agent may do is fixed
            by its capabilities.
          </p>
        </div>
      )}

      {step === 3 && (
        <CheckboxGroup
          legend="Data access"
          options={schema.data_scopes}
          value={cfg.data_scopes}
          onChange={(v) => set("data_scopes", v)}
        />
      )}

      {step === 4 && (
        <CheckboxGroup
          legend="Research scope"
          options={schema.research_scopes}
          value={cfg.research_scopes}
          onChange={(v) => set("research_scopes", v)}
        />
      )}

      {step === 5 && (
        <CheckboxGroup
          legend="Capabilities"
          hint="Research and proposal capabilities only."
          options={schema.capabilities}
          value={cfg.capabilities}
          onChange={(v) => set("capabilities", v)}
        />
      )}

      {step === 6 && (
        <div>
          <label htmlFor="ma-timeout">Timeout (seconds)</label>
          <input
            id="ma-timeout"
            type="number"
            style={fieldStyle}
            value={cfg.timeout_s}
            onChange={(e) => set("timeout_s", Number(e.target.value))}
          />
          <label htmlFor="ma-conc" style={{ display: "block", marginTop: 12 }}>
            Max concurrency
          </label>
          <input
            id="ma-conc"
            type="number"
            style={fieldStyle}
            value={cfg.max_concurrency}
            onChange={(e) => set("max_concurrency", Number(e.target.value))}
          />
          <p style={{ opacity: 0.75 }}>
            Max concurrency is enforced when a run is admitted. Timeout is recorded for the future executor; nothing
            enforces it yet.
          </p>
        </div>
      )}

      {last && (
        <div>
          <dl>
            <dt>Name</dt>
            <dd>{cfg.name}</dd>
            <dt>Type</dt>
            <dd>{cfg.agent_type}</dd>
            <dt>Provider / model</dt>
            <dd>
              {cfg.provider} / {cfg.model}
            </dd>
            <dt>Credential reference</dt>
            <dd>{cfg.credential_ref ?? "none"}</dd>
            <dt>Data access</dt>
            <dd>{cfg.data_scopes.join(", ") || "none"}</dd>
            <dt>Research scope</dt>
            <dd>{cfg.research_scopes.join(", ") || "none"}</dd>
            <dt>Capabilities</dt>
            <dd>{cfg.capabilities.join(", ")}</dd>
            <dt>Limits</dt>
            <dd>
              {cfg.timeout_s}s timeout, concurrency {cfg.max_concurrency}
            </dd>
          </dl>
          <p>
            <strong>{SAFETY_STATEMENT}</strong>
          </p>
          <p>
            The agent is created <strong>DISABLED</strong>. Enabling it is a separate, explicit step.
          </p>
        </div>
      )}

      {error ? (
        <p role="alert" style={{ color: "#b42318" }}>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 16 }}>
        <button type="button" style={btn} onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          style={btn}
          disabled={step === 0}
          onClick={() => {
            setError(null);
            setStep((s) => s - 1);
          }}
        >
          Back
        </button>
        {last ? (
          <button type="button" style={btn} disabled={busy} onClick={create}>
            {busy ? "Creating…" : "Create agent"}
          </button>
        ) : (
          <button type="button" style={btn} onClick={next}>
            Next
          </button>
        )}
      </div>
    </section>
  );
}
