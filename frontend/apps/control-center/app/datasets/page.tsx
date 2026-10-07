"use client";
import { useEffect, useState, type FormEvent } from "react";
interface Dataset {
  dataset_id: string;
  source: string;
  status: string;
  row_count: number;
  quality: unknown;
  content_hash: string;
}
export default function Datasets() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [message, setMessage] = useState("");
  const refresh = () =>
    fetch("/v1/datasets").then(async (r) => {
      if (!r.ok) throw new Error();
      setDatasets((await r.json()).datasets);
    });
  useEffect(() => {
    refresh().catch(() => setMessage("DATASET_REGISTRY_UNAVAILABLE"));
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(form.entries());
    try {
      const response = await fetch("/v1/datasets/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body, timeframe: body.timeframe || null }),
      });
      if (!response.ok) throw new Error("Import rejected");
      const result = await response.json();
      setMessage(`${result.dataset_id}: ${result.status}`);
      await refresh();
    } catch {
      setMessage("DATASET_IMPORT_REJECTED");
    }
  }
  return (
    <>
      <h1>XAUUSD datasets</h1>
      <p>
        CSV or Parquet imports receive immutable identities and a quality report. Importing data grants no strategy
        validation.
      </p>
      <form onSubmit={submit} style={{ display: "grid", gap: 12, maxWidth: 650 }}>
        {[
          ["path", "Local dataset path"],
          ["source", "Source / broker provenance"],
          ["broker_symbol", "Broker symbol"],
          ["source_timezone", "Source timezone"],
        ].map(([name, label]) => (
          <label key={name}>
            {label}
            <input
              required
              name={name}
              defaultValue={name === "broker_symbol" ? "XAUUSD" : name === "source_timezone" ? "UTC" : ""}
            />
          </label>
        ))}
        <label>
          Timeframe
          <select name="timeframe">
            <option value="">Ticks</option>
            {["1m", "5m", "15m", "1h", "1d"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Price basis
          <select name="price_basis">
            {["BID_ASK", "BID", "ASK", "LAST", "MID"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <button type="submit">Import and assess quality</button>
      </form>
      <p role="status">{message}</p>
      {datasets.map((dataset) => (
        <section key={dataset.dataset_id}>
          <h2>{dataset.dataset_id}</h2>
          <p>
            {dataset.source} · {dataset.status} · {dataset.row_count} rows
          </p>
          <p>Content hash: {dataset.content_hash}</p>
          <pre>{JSON.stringify(dataset.quality, null, 2)}</pre>
        </section>
      ))}
    </>
  );
}
