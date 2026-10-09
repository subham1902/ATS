"use client";
import { useEffect, useState, type FormEvent } from "react";
type Assignment = { strategy_id: string; strategy_version: number; enabled: boolean };
type Configuration = {
  revision: number;
  canonical_symbol: "XAUUSD";
  risk_per_trade: string;
  daily_loss_fraction: string;
  monthly_loss_fraction: string;
  max_open_risk_fraction: string;
  max_strategy_risk_fraction: string;
  max_volume: string;
  max_positions: number;
  margin_fraction: string;
  sizing_mode: "RISK_BASED";
  equity_reference: "START_OF_PERIOD";
  loss_basis: "NET_REALIZED";
  assignments: Assignment[];
  paused: boolean;
};
const defaults: Configuration = {
  revision: 0,
  canonical_symbol: "XAUUSD",
  risk_per_trade: "0.005",
  daily_loss_fraction: "0.03",
  monthly_loss_fraction: "0.08",
  max_open_risk_fraction: "0.01",
  max_strategy_risk_fraction: "0.01",
  max_volume: "0.10",
  max_positions: 1,
  margin_fraction: "0.30",
  sizing_mode: "RISK_BASED",
  equity_reference: "START_OF_PERIOD",
  loss_basis: "NET_REALIZED",
  assignments: [],
  paused: true,
};
export function AccountConfiguration({ accountId }: { accountId: string }) {
  const [config, setConfig] = useState<Configuration | null>(null);
  const [strategies, setStrategies] = useState<Assignment[]>([]);
  const [message, setMessage] = useState("");
  const [readiness, setReadiness] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const refreshReadiness = () =>
      fetch(`/v1/accounts/${encodeURIComponent(accountId)}/readiness`, { signal: controller.signal })
        .then(async (response) => {
          if (!response.ok) throw Error();
          const state = await response.json();
          if (!controller.signal.aborted)
            setReadiness(Array.isArray(state.reason_codes) ? state.reason_codes : ["READINESS_UNAVAILABLE"]);
        })
        .catch(() => {
          if (!controller.signal.aborted) setReadiness(["READINESS_UNAVAILABLE"]);
        });
    void refreshReadiness();
    const readinessTimer = window.setInterval(refreshReadiness, 5000);
    Promise.all([
      fetch(`/v1/accounts/${encodeURIComponent(accountId)}/configuration`, { signal: controller.signal }),
      fetch("/v1/strategy-os", { signal: controller.signal }),
    ])
      .then(async ([a, b]) => {
        if (!a.ok || !b.ok) throw Error();
        const c = await a.json();
        const s = await b.json();
        if (!Array.isArray(s.strategies) || !("configuration" in c)) throw Error();
        if (!controller.signal.aborted) {
          setConfig(c.configuration ?? defaults);
          setStrategies(
            s.strategies
              .filter((r: { status: string }) => r.status !== "RETIRED")
              .map((r: { strategy_id: string; version: number }) => ({
                strategy_id: r.strategy_id,
                strategy_version: r.version,
                enabled: false,
              })),
          );
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setMessage("Configuration unavailable. Reload before making changes.");
      });
    return () => {
      controller.abort();
      window.clearInterval(readinessTimer);
    };
  }, [accountId]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config) return;
    setBusy(true);
    try {
      const response = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/configuration`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_revision: config.revision,
          config: { ...config, revision: config.revision + 1 },
        }),
      });
      if (!response.ok) throw Error("Save rejected. Check limits and reload for the latest revision.");
      setConfig((await response.json()).configuration);
      const readinessResponse = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/readiness`);
      setReadiness(readinessResponse.ok ? (await readinessResponse.json()).reason_codes : ["READINESS_UNAVAILABLE"]);
      setMessage("Configuration saved. Execution consent cleared; settings do not grant authority.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details>
      <summary>Strategy assignments and risk settings</summary>
      <p>
        Versioned operator settings. Risk-based sizing; net realized loss against start-of-period equity. Saving clears
        execution consent. These settings are not yet connected to external execution.
      </p>
      <h3>Execution readiness</h3>
      <ul>
        {readiness.map((reason) => (
          <li key={reason}>{reason.replaceAll("_", " ")}</li>
        ))}
      </ul>
      {message && <p role="status">{message}</p>}
      {config && (
        <form onSubmit={save}>
          <div className="metric-grid">
            {(
              [
                ["risk_per_trade", "Per-trade risk fraction"],
                ["daily_loss_fraction", "Daily loss fraction (max 0.03)"],
                ["monthly_loss_fraction", "Monthly loss fraction (max 0.08)"],
                ["max_open_risk_fraction", "Aggregate open-risk fraction"],
                ["max_strategy_risk_fraction", "Strategy exposure fraction"],
                ["max_volume", "Maximum broker lots"],
                ["margin_fraction", "Maximum equity allocated to margin"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  required
                  type="number"
                  step="any"
                  min="0.000001"
                  value={config[key]}
                  onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                />
              </label>
            ))}
            <label>
              Maximum positions
              <input
                required
                type="number"
                min="1"
                max="100"
                value={config.max_positions}
                onChange={(e) => setConfig({ ...config, max_positions: Number(e.target.value) })}
              />
            </label>
          </div>
          <fieldset>
            <legend>Assigned strategy versions</legend>
            {strategies.map((s) => {
              const active = config.assignments.find((a) => a.strategy_id === s.strategy_id);
              return (
                <label key={s.strategy_id} style={{ display: "block" }}>
                  <input
                    type="checkbox"
                    checked={active?.enabled ?? false}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        assignments: [
                          ...config.assignments.filter((a) => a.strategy_id !== s.strategy_id),
                          { ...s, enabled: e.target.checked },
                        ],
                      })
                    }
                  />{" "}
                  {s.strategy_id} v{active?.strategy_version ?? s.strategy_version}
                </label>
              );
            })}
          </fieldset>
          <label>
            <input
              type="checkbox"
              checked={config.paused}
              onChange={(e) => setConfig({ ...config, paused: e.target.checked })}
            />{" "}
            Pause new entries
          </label>
          <p>Revision {config.revision} · XAUUSD · configuration only</p>
          <button disabled={busy} type="submit">
            Save configuration
          </button>
        </form>
      )}
    </details>
  );
}
