"use client";
import { useEffect, useState } from "react";
import { ServiceSummary } from "../../components/ServiceSummary";
export default function System() {
  const [state, setState] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch("/v1/system")
      .then((r) => (r.ok ? r.json() : null))
      .then(setState)
      .catch(() => setState(null))
      .finally(() => setLoading(false));
  }, []);
  return (
    <>
      <h1>System</h1>
      <p>XAUUSD only · MetaTrader data only · PaperBroker only. Financial authority remains deterministic.</p>
      <div className="panel">
        <h2>Connection status</h2>
        <p role="status">
          {loading
            ? "Loading service observations…"
            : state
              ? "Service responded  /  inspect diagnostics for individual subsystem health"
              : "Service unavailable / health unknown"}
        </p>
      </div>
      <ServiceSummary state={state} />
      <details>
        <summary>Detailed service diagnostics</summary>
        <pre>{state ? JSON.stringify(state, null, 2) : "System state unknown"}</pre>
      </details>
    </>
  );
}
