"use client";
import { useEffect, useState } from "react";
import { useMetaTraderFeed } from "./xauusd-chart/useMetaTraderFeed";

export function Dashboard() {
  const { quote, error } = useMetaTraderFeed();
  const [runtime, setRuntime] = useState<{
    open_positions: unknown[];
    pnl: { realized: string; unrealized: string };
    loss_state: string;
  } | null>(null);
  const [strategies, setStrategies] = useState<number | null>(null);
  const [datasets, setDatasets] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch("/v1/runtime/status", { signal: controller.signal }),
      fetch("/v1/strategies/registry", { signal: controller.signal }),
      fetch("/v1/datasets", { signal: controller.signal }),
    ])
      .then(async ([r, s, d]) => {
        if (r.ok) setRuntime(await r.json());
        if (s.ok) setStrategies((await s.json()).strategies.length);
        if (d.ok) setDatasets((await d.json()).datasets.at(-1)?.dataset_id ?? null);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  const metrics = [
    ["Instrument", "XAUUSD"],
    ["Connection", `${quote?.source ?? "MetaTrader"} ${quote?.state ?? "DISCONNECTED"}`],
    ["Bid", quote?.bid_price ?? "N/A"],
    ["Ask", quote?.ask_price ?? "N/A"],
    ["Spread", quote?.spread ?? "N/A"],
    ["Last observation (UTC)", quote?.exchange_timestamp ?? "N/A"],
    ["Feed age", quote?.freshness_ms == null ? "N/A" : `${quote.freshness_ms} ms`],
    ["Research strategies", strategies ?? "N/A"],
    ["Paper positions", runtime?.open_positions.length ?? "N/A"],
    ["Paper realized P&L", runtime?.pnl.realized ?? "N/A"],
    ["Paper unrealized P&L", runtime?.pnl.unrealized ?? "N/A"],
    ["Risk state", runtime?.loss_state ?? "UNKNOWN"],
    ["Current dataset", datasets ?? "None imported"],
  ];
  return (
    <>
      <h1>XAUUSD dashboard</h1>
      <p>The XAUUSD-specialized ATS currently has no repository evidence establishing profitability.</p>
      {error && <p role="alert">{error}</p>}
      <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 16 }}>
        {metrics.map(([label, value]) => (
          <div
            key={label}
            style={{
              background: "white",
              padding: 20,
              border: "1px solid #ddd",
              borderRadius: 8,
              overflowWrap: "anywhere",
            }}
          >
            <dt>{label}</dt>
            <dd style={{ margin: "10px 0 0", fontWeight: 600 }}>{value}</dd>
          </div>
        ))}
      </dl>
      <p>Strategies are RESEARCH_ONLY. Paper-forward validation requires clean-room evidence and A04 authority.</p>
    </>
  );
}
