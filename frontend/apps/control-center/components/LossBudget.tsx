"use client";

import { useEffect, useState } from "react";

type Budget = {
  account_id: string;
  state: "UNKNOWN" | "VERIFIED_BUDGET";
  reason_codes: string[];
  starting_day_equity: string | null;
  starting_month_equity: string | null;
  net_booked_day: string | null;
  net_booked_month: string | null;
  daily_remaining: string | null;
  monthly_remaining: string | null;
  grants_authority: false;
  observed_at: string | null;
  currency: string | null;
};

export function LossBudget({ accountId }: { accountId: string }) {
  const [budget, setBudget] = useState<Budget | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    let alive = true;
    let pending = false;
    async function refresh() {
      if (pending) return;
      pending = true;
      try {
        const response = await fetch(`/v1/accounts/${encodeURIComponent(accountId)}/loss-budget`, {
          cache: "no-store",
        });
        if (!response.ok) throw Error();
        const result: Budget = await response.json();
        if (
          result.account_id !== accountId ||
          !["UNKNOWN", "VERIFIED_BUDGET"].includes(result.state) ||
          !Array.isArray(result.reason_codes) ||
          !result.reason_codes.every((reason) => typeof reason === "string") ||
          result.grants_authority !== false
        )
          throw Error();
        if (alive) {
          setBudget(result);
          setNow(Date.now());
          setUnavailable(false);
        }
      } catch {
        if (alive) {
          setBudget(null);
          setUnavailable(true);
        }
      } finally {
        pending = false;
      }
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    const freshness = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      alive = false;
      clearInterval(timer);
      clearInterval(freshness);
    };
  }, [accountId]);
  const age = budget?.observed_at ? now - Date.parse(budget.observed_at) : NaN;
  const fresh = budget?.account_id === accountId && budget.state === "VERIFIED_BUDGET" && age >= 0 && age <= 5000;
  const value = (field: keyof Budget) => (fresh ? String(budget[field] ?? "UNKNOWN") : "UNKNOWN");
  return (
    <section aria-label="Account loss budgets">
      <h3>Daily & monthly loss budgets</h3>
      <p>
        {unavailable
          ? "Accounting service unavailable — budget UNKNOWN."
          : fresh
            ? "VERIFIED BUDGET"
            : budget
              ? "Budget UNKNOWN — fresh, complete evidence required."
              : "Checking evidence…"}
      </p>
      {fresh && <p>Account currency: {budget?.currency ?? "UNKNOWN"}</p>}
      <p>
        Net realized P&L, including costs and swap, against observed start-of-period equity. Deposits are not trading
        profit. These figures do not grant execution authority.
      </p>
      <dl className="stat-grid">
        <div>
          <dt>Start-of-day equity</dt>
          <dd>{value("starting_day_equity")}</dd>
        </div>
        <div>
          <dt>Day net realized P&L</dt>
          <dd>{value("net_booked_day")}</dd>
        </div>
        <div>
          <dt>Day remaining budget</dt>
          <dd>{value("daily_remaining")}</dd>
        </div>
        <div>
          <dt>Start-of-month equity</dt>
          <dd>{value("starting_month_equity")}</dd>
        </div>
        <div>
          <dt>Month net realized P&L</dt>
          <dd>{value("net_booked_month")}</dd>
        </div>
        <div>
          <dt>Month remaining budget</dt>
          <dd>{value("monthly_remaining")}</dd>
        </div>
      </dl>
      {!!budget?.reason_codes.length && (
        <ul>
          {budget.reason_codes.map((reason) => (
            <li key={reason}>{reason.replaceAll("_", " ")}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
