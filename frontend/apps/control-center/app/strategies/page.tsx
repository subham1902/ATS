"use client";
import { useEffect, useState } from "react";
interface Strategy {
  strategy_id: string;
  version: string;
  status: string;
  implementation_status: string;
  datasets_tested: string[];
  latest_research_run: string | null;
  out_of_sample_status: string;
  cost_stress_status: string;
  paper_forward_status: string;
  promotion_status: string;
}
export default function Strategies() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch("/v1/strategies/registry")
      .then(async (response) => {
        if (!response.ok) throw new Error();
        setStrategies((await response.json()).strategies);
      })
      .catch(() => setError("STRATEGY_REGISTRY_UNAVAILABLE"));
  }, []);
  return (
    <>
      <h1>XAUUSD strategies</h1>
      <p>Definitions survive. Prior market performance carries no authority. Every strategy starts RESEARCH_ONLY.</p>
      {error && <p role="alert">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>ID / version</th>
            <th>Status</th>
            <th>Datasets</th>
            <th>Latest run</th>
            <th>Out of sample</th>
            <th>Cost stress</th>
            <th>Paper forward</th>
            <th>Promotion</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => (
            <tr key={s.strategy_id}>
              <td>
                {s.strategy_id}
                <br />
                {s.version}
              </td>
              <td>
                {s.status} · {s.implementation_status}
              </td>
              <td>{s.datasets_tested.join(", ") || "None"}</td>
              <td>{s.latest_research_run ?? "N/A"}</td>
              <td>{s.out_of_sample_status}</td>
              <td>{s.cost_stress_status}</td>
              <td>{s.paper_forward_status}</td>
              <td>{s.promotion_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
