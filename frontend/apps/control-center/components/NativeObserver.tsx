"use client";
import { useCallback, useEffect, useState } from "react";
export function NativeObserver({ accountId }: { accountId: string }) {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/native-observer`);
      if (!response.ok) throw Error();
      setState(await response.json());
    } catch {
      setState({ state: "UNKNOWN", reason: "NATIVE_OBSERVER_UNAVAILABLE" });
    }
  }, [accountId]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  async function reloadClock() {
    try {
      const response = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/clock/refresh`, { method: "POST" });
      if (!response.ok) throw Error();
      setState(await response.json());
    } catch {
      setState({ state: "UNKNOWN", reason: "VALID_INDEPENDENT_CLOCK_EVIDENCE_REQUIRED" });
    }
  }
  return (
    <details>
      <summary>Native MetaTrader observer</summary>
      <p>
        Local EA observations only. File freshness is not execution authority or independently verified clock evidence.
      </p>
      <button onClick={() => void refresh()}>Refresh observer</button>
      <button onClick={() => void reloadClock()}>Reload verified live clock evidence</button>
      {state && <pre>{JSON.stringify(state, null, 2)}</pre>}
    </details>
  );
}
