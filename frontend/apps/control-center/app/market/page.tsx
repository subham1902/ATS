"use client";
import { useEffect, useState } from "react";
import { XauUsdChart } from "../../components/xauusd-chart/XauUsdChart";
import { useMetaTraderFeed } from "../../components/xauusd-chart/useMetaTraderFeed";
import { FootprintProxy } from "../../components/xauusd-chart/footprint";

export default function Market() {
  const [accountId, setAccountId] = useState("");
  const [accounts, setAccounts] = useState<{ account_id: string; display_name: string }[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/v1/accounts", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("ACCOUNTS_UNAVAILABLE");
        return response.json();
      })
      .then((rows) => {
        if (!controller.signal.aborted)
          setAccounts(rows.map((row: { account: { account_id: string; display_name: string } }) => row.account));
      })
      .catch(() => {
        if (!controller.signal.aborted) setAccounts([]);
      });
    return () => controller.abort();
  }, []);
  const [interval, setInterval] = useState("5m");
  const { quote, candles, footprint, error } = useMetaTraderFeed(interval, accountId);
  return (
    <>
      <p className="eyebrow">Observed broker data</p>
      <h1>XAUUSD market</h1>
      {quote?.state !== "LIVE" && (
        <p className="notice" role="note">
          Feed is not live. Any quotes and chart bars below are retained observations; check the UTC timestamp before
          using them.
        </p>
      )}
      <label>
        Data account{" "}
        <select value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          <option value="">Automatic (requires one connected account)</option>
          {accounts.map((account) => (
            <option key={account.account_id} value={account.account_id}>
              {account.display_name}
            </option>
          ))}
        </select>
      </label>
      <p role="status">
        {quote?.source ?? "MetaTrader"} {quote?.state ?? "DISCONNECTED"}
      </p>
      <p>
        Source: MetaTrader {quote?.source === "MT4" ? "4" : "5"} · Symbol: {quote?.broker_symbol ?? "N/A"} · Canonical:
        XAUUSD
      </p>
      <p>
        Bid: {quote?.bid_price ?? "N/A"} · Ask: {quote?.ask_price ?? "N/A"} · Spread: {quote?.spread ?? "N/A"}
      </p>
      <p>
        UTC observation: {quote?.exchange_timestamp ?? "N/A"} · Session research label: {quote?.market_session ?? "N/A"}
      </p>
      <p>
        Tick volume: {quote?.tick_volume ?? "N/A"} · Real volume: {quote?.real_volume ?? "N/A"} · Volume provenance:{" "}
        {quote?.volume_provenance ?? "UNKNOWN"}
      </p>
      {error && <p role="alert">{error}</p>}
      <label>
        Timeframe{" "}
        <select value={interval} onChange={(event) => setInterval(event.target.value)}>
          {["1m", "5m", "15m", "1h", "1d"].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      {candles.length === 0 && <p className="panel">No observed candles available for this account and timeframe.</p>}
      <div className="panel">
        <XauUsdChart candles={candles} />
      </div>
      <FootprintProxy data={footprint} />
    </>
  );
}
