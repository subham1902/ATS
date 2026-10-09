"use client";
import { useState, type FormEvent } from "react";
export function LotPreview({ accountId }: { accountId: string }) {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setResult(null);
    setError("");
    try {
      const response = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/sizing-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          side: fields.get("side"),
          entry: Number(fields.get("entry")),
          stop: Number(fields.get("stop")),
          roundtrip_cost_per_lot: Number(fields.get("cost")),
        }),
      });
      if (!response.ok)
        throw Error(
          "Preview unavailable. Connect the account, save risk settings and verify accepted live data first.",
        );
      setResult(await response.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details>
      <summary>Broker lot-sizing preview</summary>
      <p>
        Read-only broker calculation. Costs must be explicit. Period loss accounting remains unverified; a preview
        cannot authorize a trade.
      </p>
      <form onSubmit={preview}>
        <div className="toolbar">
          <label>
            Side
            <select name="side">
              <option>BUY</option>
              <option>SELL</option>
            </select>
          </label>
          <label>
            Entry price
            <input name="entry" required type="number" min="0.00001" step="any" />
          </label>
          <label>
            Stop-loss price
            <input name="stop" required type="number" min="0.00001" step="any" />
          </label>
          <label>
            Modeled round-trip costs per lot (account currency)
            <input name="cost" required type="number" min="0" step="any" />
          </label>
          <button disabled={busy}>Calculate lots</button>
        </div>
      </form>
      {error && <p role="alert">{error}</p>}
      {result && (
        <dl className="metric-grid">
          {Object.entries(result).map(([key, value]) => (
            <div key={key} className="metric-card">
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>{value == null ? "UNKNOWN" : String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </details>
  );
}
