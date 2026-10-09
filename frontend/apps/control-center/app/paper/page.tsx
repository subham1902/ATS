"use client";
import { useEffect, useState } from "react";
export default function Paper() {
  const [state, setState] = useState<unknown>(null);
  useEffect(() => {
    fetch("/v1/runtime/status")
      .then((r) => (r.ok ? r.json() : null))
      .then(setState)
      .catch(() => setState(null));
  }, []);
  return (
    <>
      <h1>Paper trading</h1>
      <p>PaperBroker only · LIVE_MONEY=FALSE · A04 authorization required.</p>
      <p>XAUUSD strategies remain RESEARCH_ONLY until new validation evidence exists.</p>
      <pre style={{ maxWidth: "100%", overflowX: "auto" }}>
        {state ? JSON.stringify(state, null, 2) : "Runtime state unavailable"}
      </pre>
    </>
  );
}
