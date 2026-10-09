"use client";

import { useEffect, useState, type FormEvent } from "react";

type Job = { run_id: string; status: string; error: string | null; result: unknown };
type Dataset = { dataset_id: string; normalized_hash: string; status: string; row_count: number };
type Agent = {
  agent_id: string;
  name: string;
  enabled: boolean;
  current_config_version: number;
  capabilities: string[];
};

export function ResearchJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function refresh() {
    const response = await fetch("/v1/strategy-os/jobs", { cache: "no-store" });
    if (!response.ok) throw new Error("Research queue unavailable");
    setJobs((await response.json()).jobs);
  }
  useEffect(() => {
    void Promise.all([fetch("/v1/datasets"), fetch("/v1/agents/managed")])
      .then(async ([d, a]) => {
        if (!d.ok || !a.ok) throw new Error("Research inputs unavailable");
        setDatasets((await d.json()).datasets);
        setAgents((await a.json()).agents);
        await refresh();
      })
      .catch(() => setError("Research inputs unavailable"));
    const timer = setInterval(() => void refresh().catch(() => setError("Research queue unavailable")), 3000);
    return () => clearInterval(timer);
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const dataset = datasets.find((d) => d.dataset_id === data.get("dataset"));
    const agent = agents.find((a) => a.agent_id === data.get("agent"));
    if (!dataset || !agent) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/v1/strategy-os/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          idempotency: crypto.randomUUID(),
          job: {
            agent_id: agent.agent_id,
            agent_config_version: agent.current_config_version,
            strategy_id: String(data.get("strategy")),
            strategy_version: 1,
            dataset_id: dataset.dataset_id,
            dataset_hash: dataset.normalized_hash,
            method_version: "CAUSAL-QUOTE-V1",
            cost_model_version: "QUOTE-COST-V1",
            parameters: {
              tick_size: Number(data.get("tick")),
              quantity: Number(data.get("quantity")),
              commission: Number(data.get("commission")),
              slippage: Number(data.get("slippage")),
              latency_ms: Number(data.get("latency")),
              bar_seconds: Number(data.get("interval")),
            },
            budget_rows: dataset.row_count,
            timeout_seconds: Number(data.get("timeout")),
            cadence: "MANUAL",
          },
        }),
      });
      if (!response.ok) throw new Error("Job denied: verify enabled agent, versions, quote dataset, budgets and costs");
      await refresh();
      const run = await fetch("/v1/strategy-os/jobs/run-next", { method: "POST" });
      if (!run.ok) throw new Error("Research worker unavailable");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Bounded research jobs">
      <h2>Run quote research</h2>
      <p>
        Research only. Observed bid/ask ticks required. Costs use price units, not broker lots. No strategy promotion.
        Scheduling, holdout and probability calibration remain unavailable.
      </p>
      {error && <p role="alert">{error}</p>}
      <form onSubmit={submit}>
        <label>
          Enabled backtest agent{" "}
          <select name="agent" required>
            {agents
              .filter((a) => a.enabled && a.capabilities.includes("RUN_BACKTEST"))
              .map((a) => (
                <option key={a.agent_id} value={a.agent_id}>
                  {a.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          Dataset{" "}
          <select name="dataset" required>
            {datasets
              .filter((d) => d.status === "RESEARCH_ONLY")
              .map((d) => (
                <option key={d.dataset_id}>{d.dataset_id}</option>
              ))}
          </select>
        </label>
        <label>
          Strategy v1{" "}
          <select name="strategy">
            <option>XAU-003</option>
            <option>XAU-013</option>
            <option>XAU-016</option>
            <option>XAU-009</option>
            <option>XAU-001</option>
          </select>
        </label>
        <label>
          Quote-bar seconds{" "}
          <select name="interval">
            <option>60</option>
            <option>300</option>
            <option>900</option>
            <option>3600</option>
          </select>
        </label>
        {[
          ["tick", "Tick size"],
          ["quantity", "Price units"],
          ["commission", "Commission per unit per side"],
          ["slippage", "Slippage price"],
          ["latency", "Latency ms"],
          ["timeout", "Timeout seconds"],
        ].map(([name, label]) => (
          <label key={name}>
            {label} <input name={name} type="number" step="any" min="0" required />
          </label>
        ))}
        <button disabled={busy}>{busy ? "Running bounded research…" : "Run Backtest Agent"}</button>
      </form>
      {jobs.map((job) => (
        <article key={job.run_id}>
          <h3>
            {job.run_id} · {job.status}
          </h3>
          {job.error && <p>{job.error}</p>}
          {job.status === "QUEUED" || job.status === "RUNNING" ? (
            <button
              onClick={() =>
                void fetch(`/v1/strategy-os/jobs/${job.run_id}/cancel`, { method: "POST" })
                  .then(refresh)
                  .catch(() => setError("Cancellation failed"))
              }
            >
              Cancel job
            </button>
          ) : null}
          {job.result != null && (
            <details>
              <summary>Versioned research evidence</summary>
              <pre>{JSON.stringify(job.result, null, 2)}</pre>
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
