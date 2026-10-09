"use client";
import { useEffect, useState } from "react";
interface Strategy {
  strategy_id: string;
  definition_id: string;
  version: number;
  direction: string | null;
  trade_horizon: string | null;
  status: string;
  datasets_tested: string[];
  backtest_results: string[];
  walk_forward_results: string[];
  holdout_results: string[];
  paper_results: string[];
}
export default function Strategies() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    fetch("/v1/strategy-os")
      .then(async (response) => {
        if (!response.ok) throw new Error();
        setStrategies((await response.json()).strategies);
      })
      .catch(() => setError("STRATEGY_REGISTRY_UNAVAILABLE"));
  }, []);
  return (
    <>
      <h1>XAUUSD strategies</h1>
      <p>
        Immutable XAUUSD lineages. Prior market performance carries no authority. All definitions remain research only;
        independent validation is required for promotion.
      </p>
      <p>
        Bounded quote backtests are available in Agent Playground. Scheduled research and empirical probability
        calibration remain unavailable.
      </p>
      <div className="toolbar">
        <label>
          Find strategy
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ID, definition or status"
          />
        </label>
        <span>
          {
            strategies.filter((s) =>
              `${s.strategy_id} ${s.definition_id} ${s.status}`.toLowerCase().includes(query.toLowerCase()),
            ).length
          }{" "}
          strategies
        </span>
      </div>
      {error && <p role="alert">{error}</p>}
      <div
        role="region"
        aria-label="Strategy evidence table"
        tabIndex={0}
        style={{ maxWidth: "100%", overflowX: "auto" }}
      >
        <table>
          <thead>
            <tr>
              <th>ID / version</th>
              <th>Status</th>
              <th>Direction / horizon</th>
              <th>Datasets</th>
              <th>Backtests</th>
              <th>Walk forward / holdout</th>
              <th>Paper forward</th>
            </tr>
          </thead>
          <tbody>
            {strategies
              .filter((s) =>
                `${s.strategy_id} ${s.definition_id} ${s.status}`.toLowerCase().includes(query.toLowerCase()),
              )
              .map((s) => (
                <tr key={s.strategy_id}>
                  <td>
                    {s.strategy_id}
                    <br />
                    {s.version}
                    <br />
                    Definition: {s.definition_id}
                  </td>
                  <td>{s.status}</td>
                  <td>
                    {s.direction ?? "UNKNOWN"} / {s.trade_horizon ?? "UNKNOWN"}
                  </td>
                  <td>{s.datasets_tested.join(", ") || "None"}</td>
                  <td>{s.backtest_results.join(", ") || "NOT_RUN"}</td>
                  <td>
                    {s.walk_forward_results.join(", ") || "NOT_RUN"} / {s.holdout_results.join(", ") || "NOT_RUN"}
                  </td>
                  <td>{s.paper_results.join(", ") || "NOT_RUN"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
