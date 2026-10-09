"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { NativeObserver } from "../../components/NativeObserver";
import { LotPreview } from "../../components/LotPreview";
import { AccountConfiguration } from "../../components/AccountConfiguration";
import styles from "./accounts.module.css";

type AccountView = {
  account: {
    account_id: string;
    display_name: string;
    platform: string;
    server: string;
    account_mode: string;
    connection_state: string;
    execution_enabled: boolean;
    broker_symbol: string;
    allowed_strategy_ids: string[];
  };
  observed: {
    balance?: string;
    equity?: string;
    margin?: string;
    free_margin?: string;
    currency?: string;
    positions?: unknown[];
    orders?: unknown[];
  };
  market: { state: string; reason?: string; feed_age_seconds?: number };
  quote: { bid?: string; ask?: string; timestamp?: string } | null;
  execution_gate: string;
  risk_state: string;
  reconciliation_state: string;
};
const observed = (value: unknown) => (value == null ? "N/A" : String(value));

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountView[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [adopting, setAdopting] = useState(false);
  const [platform, setPlatform] = useState("MT5");
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/v1/accounts", { cache: "no-store" });
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (!Array.isArray(result)) throw new Error();
      setAccounts(result);
      setError(null);
    } catch {
      setError("Account service unavailable. Connection state is unknown.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement;
    const body = {
      platform,
      display_name: String(data.get("display_name")),
      broker: String(data.get("broker") ?? ""),
      server: String(data.get("server")),
      login: String(data.get("login")),
      password: String(data.get("password")),
      terminal_path: String(data.get("terminal_path") ?? "") || null,
      portable: data.get("portable") === "on",
      broker_symbol: String(data.get("broker_symbol") || "XAUUSD"),
      action: submitter?.value ?? "CONNECT_ONLY",
    };
    form.reset();
    setBusy(true);
    try {
      const response = await fetch("/v1/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error();
      const result: AccountView = await response.json();
      await refresh();
      if (result.account.connection_state === "ERROR")
        setError("Connection failed. Check credentials, terminal profile and XAUUSD symbol.");
      else if (result.account.connection_state === "NOT_CONFIGURED")
        setError("MT4 account saved. Authenticated account transport is not configured.");
      else setAdding(false);
    } catch {
      setError("Connection could not be established. Password has been cleared.");
    } finally {
      body.password = "";
      body.login = "";
      setBusy(false);
    }
  }
  async function adopt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const response = await fetch("/v1/accounts/adopt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: String(data.get("display_name")),
          terminal_path: String(data.get("terminal_path")),
          broker_symbol: String(data.get("broker_symbol")),
        }),
      });
      if (!response.ok) throw new Error();
      await refresh();
      setAdopting(false);
    } catch {
      setError("Authenticated terminal adoption failed. Verify the isolated terminal and logged-in session.");
    } finally {
      setBusy(false);
    }
  }
  async function command(id: string, operation: string, enabled?: boolean) {
    setBusy(true);
    try {
      const response = await fetch(`/v1/accounts/${encodeURIComponent(id)}/${operation}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(enabled === undefined ? {} : { body: JSON.stringify({ enabled }) }),
      });
      if (!response.ok) throw new Error();
      await refresh();
    } catch {
      setError("Account command failed. Refresh account state before continuing.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={styles.page}>
      <div className={styles.heading}>
        <div>
          <h1>MetaTrader Accounts</h1>
          <p>XAUUSD connections with separate account health and execution consent.</p>
        </div>
        <button onClick={() => setAdding(!adding)}>+ Connect Account</button>
        <button onClick={() => setAdopting(!adopting)}>Use authenticated MT5 session</button>
      </div>
      {adopting && (
        <form onSubmit={adopt}>
          <p>Monitor only. Reuses the terminal credential cache. Execution stays disabled.</p>
          <label>
            Display name <input name="display_name" required />
          </label>
          <label>
            Terminal executable{" "}
            <input name="terminal_path" defaultValue="C:\\Program Files\\MetaTrader 5\\terminal64.exe" required />
          </label>
          <label>
            Broker symbol <input name="broker_symbol" defaultValue="XAUUSD" required />
          </label>
          <button disabled={busy}>Connect Only</button>
        </form>
      )}
      <p className={styles.notice}>
        Account monitoring is available. External execution is awaiting commissioning. Execution consent and effective
        authorization are separate; check account readiness before expecting trades.
      </p>
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
      {adding && (
        <form onSubmit={connect} className={styles.form}>
          <h2>Connect an account</h2>
          <div className={styles.fields}>
            <label>
              Platform
              <select name="platform" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option>MT5</option>
                <option>MT4</option>
              </select>
            </label>
            <label>
              Display name
              <input name="display_name" required maxLength={80} />
            </label>
            <label>
              Broker
              <input name="broker" maxLength={100} />
            </label>
            <label>
              Server
              <input name="server" required maxLength={100} autoComplete="off" />
            </label>
            <label>
              Login ID
              <input name="login" required inputMode="numeric" autoComplete="off" />
            </label>
            <label>
              Password
              <input name="password" type="password" required autoComplete="new-password" />
            </label>
            <label>
              Terminal executable
              <input name="terminal_path" required={platform === "MT5"} placeholder="C:\MetaTrader\terminal64.exe" />
            </label>
            <label>
              XAUUSD broker symbol
              <input name="broker_symbol" defaultValue="XAUUSD" required maxLength={64} />
            </label>
          </div>
          <label>
            <input name="portable" type="checkbox" /> Use terminal portable profile
          </label>
          <p>
            Concurrent MT5 accounts require distinct terminal installations and data profiles. Credentials are encrypted
            locally with Windows DPAPI.
          </p>
          {platform === "MT4" && (
            <p>MT4 authentication and account monitoring require a bridge. This account will remain NOT_CONFIGURED.</p>
          )}
          <div className={styles.actions}>
            <button disabled={busy} type="submit" value="CONNECT_ONLY">
              Connect Only
            </button>
            <button disabled={busy} type="submit" value="CONNECT_AND_ENABLE_EXECUTION">
              Connect &amp; Enable Execution
            </button>
            <button disabled={busy} type="button" onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {loading && <p role="status">Loading accounts…</p>}
      {!loading && accounts.length === 0 && !error && (
        <p>No accounts connected. Add a MetaTrader account to observe XAUUSD.</p>
      )}
      <div className={styles.grid}>
        {accounts.map((view) => (
          <article key={view.account.account_id} className={styles.card}>
            <h2>{view.account.display_name}</h2>
            <p className={view.account.account_mode === "LIVE" ? styles.live : styles.badge}>
              {view.account.platform} · {view.account.account_mode} ACCOUNT ·{" "}
              {error ? "UNKNOWN" : view.account.connection_state}
            </p>
            <p>{view.account.account_id}</p>
            <p>Server: {view.account.server}</p>
            <p>
              <strong>Execution consent: {view.account.execution_enabled ? "ENABLED" : "DISABLED"}</strong>
            </p>
            <p>Routing: unavailable · Risk: {view.risk_state}</p>
            <dl className={styles.metrics}>
              <dt>Balance / equity</dt>
              <dd>
                {observed(view.observed.balance)} / {observed(view.observed.equity)} {view.observed.currency}
              </dd>
              <dt>Margin / free margin</dt>
              <dd>
                {observed(view.observed.margin)} / {observed(view.observed.free_margin)}
              </dd>
              <dt>Instrument</dt>
              <dd>{view.account.broker_symbol} → XAUUSD</dd>
              <dt>Market health</dt>
              <dd>
                {error ? "UNKNOWN" : view.market.state} · {view.market.reason ?? "N/A"}
              </dd>
              <dt>Bid / ask</dt>
              <dd>
                {observed(view.quote?.bid)} / {observed(view.quote?.ask)}
              </dd>
              <dt>Last observation</dt>
              <dd>{observed(view.quote?.timestamp)}</dd>
              <dt>Feed age</dt>
              <dd>{observed(view.market.feed_age_seconds)} s</dd>
              <dt>Positions / orders</dt>
              <dd>
                {observed(view.observed.positions?.length)} / {observed(view.observed.orders?.length)}
              </dd>
              <dt>Active strategies</dt>
              <dd>{view.account.allowed_strategy_ids.join(", ") || "None assigned"}</dd>
              <dt>Reconciliation</dt>
              <dd>{view.reconciliation_state}</dd>
            </dl>
            <details className={styles.section} open>
              <summary>Risk limits, strategy assignments & execution readiness</summary>
              <AccountConfiguration accountId={view.account.account_id} />
            </details>
            <details className={styles.section}>
              <summary>Calculate lots from entry and stop</summary>
              <LotPreview accountId={view.account.account_id} />
            </details>
            <details className={styles.section}>
              <summary>MetaTrader expert status & diagnostics</summary>
              <NativeObserver accountId={view.account.account_id} />
            </details>
            <div className={styles.actions}>
              <button disabled={busy} onClick={() => void command(view.account.account_id, "connect")}>
                Reconnect Only
              </button>
              <button disabled={busy} onClick={() => void command(view.account.account_id, "disconnect")}>
                Disconnect
              </button>
              <button
                disabled={busy || (view.account.connection_state !== "CONNECTED" && !view.account.execution_enabled)}
                onClick={() => void command(view.account.account_id, "execution", !view.account.execution_enabled)}
              >
                {view.account.execution_enabled ? "Disable Execution" : "Enable Execution Consent"}
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
