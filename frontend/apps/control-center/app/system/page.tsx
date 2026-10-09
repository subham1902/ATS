"use client";
import { useEffect, useState } from "react";
export default function System() {
  const [state, setState] = useState<unknown>(null);
  useEffect(() => {
    fetch("/v1/system")
      .then((r) => (r.ok ? r.json() : null))
      .then(setState)
      .catch(() => setState(null));
  }, []);
  return (
    <>
      <h1>System</h1>
      <p>XAUUSD only · MetaTrader data only · PaperBroker only. Financial authority remains deterministic.</p>
      <pre style={{ maxWidth: "100%", overflowX: "auto" }}>
        {state ? JSON.stringify(state, null, 2) : "System state unknown"}
      </pre>
    </>
  );
}
