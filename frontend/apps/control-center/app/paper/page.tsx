"use client";
import { useEffect, useState } from "react";
import { ServiceSummary } from "../../components/ServiceSummary";
export default function Paper() {
  const [state, setState] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch("/v1/runtime/status")
      .then((r) => (r.ok ? r.json() : null))
      .then(setState)
      .catch(() => setState(null))
      .finally(() => setLoading(false));
  }, []);
  return (
    <>
      <h1>Paper trading</h1>
      <p>PaperBroker only · LIVE_MONEY=FALSE · A04 authorization required.</p>
      <p>XAUUSD strategies remain RESEARCH_ONLY until new validation evidence exists.</p>
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
        <pre>{state ? JSON.stringify(state, null, 2) : "Runtime state unavailable"}</pre>
      </details>
    </>
  );
}
