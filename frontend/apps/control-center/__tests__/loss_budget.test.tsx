import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { LossBudget } from "../components/LossBudget";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function response(changes: Record<string, unknown> = {}) {
  return {
    account_id: "ACC-test",
    state: "UNKNOWN",
    grants_authority: false,
    reason_codes: ["PERIOD_HISTORY_OR_BASELINE_REQUIRED"],
    observed_at: new Date().toISOString(),
    currency: "USD",
    starting_day_equity: "1000",
    starting_month_equity: "1000",
    net_booked_day: "0",
    net_booked_month: "0",
    daily_remaining: "30",
    monthly_remaining: "80",
    ...changes,
  };
}

describe("account loss budgets", () => {
  it("does not display invented zero loss or capacity when evidence is unknown", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => response() }));
    render(<LossBudget accountId="ACC-test" />);
    await screen.findByText("PERIOD HISTORY OR BASELINE REQUIRED");
    expect(screen.getAllByText("UNKNOWN", { selector: "dd" })).toHaveLength(6);
    expect(screen.queryByText("80")).not.toBeInTheDocument();
  });
  it("shows verified costs-based budgets with no authority", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => response({ state: "VERIFIED_BUDGET", reason_codes: [] }) }),
    );
    render(<LossBudget accountId="ACC-test" />);
    await screen.findByText("VERIFIED BUDGET");
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText(/do not grant execution authority/)).toBeInTheDocument();
  });
  it("stale verified response stays unknown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => response({ state: "VERIFIED_BUDGET", observed_at: "2020-01-01T00:00:00Z" }),
      }),
    );
    render(<LossBudget accountId="ACC-test" />);
    await screen.findByText(/Budget UNKNOWN/);
    expect(screen.queryByText("80")).not.toBeInTheDocument();
  });
  it("cross-account response fails closed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => response({ account_id: "ACC-other", state: "VERIFIED_BUDGET" }),
      }),
    );
    render(<LossBudget accountId="ACC-test" />);
    await screen.findByText(/Accounting service unavailable/);
    expect(screen.queryByText("80")).not.toBeInTheDocument();
  });
});
