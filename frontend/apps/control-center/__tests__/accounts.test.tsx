import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import Accounts from "../app/accounts/page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function account(mode = "LIVE") {
  return {
    account: {
      account_id: "ACC-test",
      display_name: "Broker account",
      platform: "MT5",
      server: "TestServer",
      account_mode: mode,
      connection_state: "CONNECTED",
      execution_enabled: false,
      broker_symbol: "GOLD",
      allowed_strategy_ids: [],
    },
    observed: {},
    market: { state: "DEGRADED", reason: "AWAITING_OBSERVED_TICK" },
    quote: null,
    execution_gate: "EXTERNAL_ROUTING_NOT_IMPLEMENTED",
    risk_state: "RISK_PROFILE_REQUIRED",
    reconciliation_state: "UNKNOWN",
  };
}

describe("MetaTrader Accounts", () => {
  it("shows LIVE accounts and unknown observations without inventing balances", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [account()] }));
    render(<Accounts />);
    expect(await screen.findByText("Broker account")).toBeInTheDocument();
    expect(screen.getByText(/LIVE ACCOUNT/)).toBeInTheDocument();
    expect(screen.getAllByText("N/A / N/A", { selector: "dd" })).toHaveLength(4);
    expect(screen.getByText(/External execution is awaiting commissioning/)).toBeInTheDocument();
  });

  it("connects only by default and clears credentials after submission", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    fetch.mockImplementation(async (_url, init) =>
      init?.method === "POST" ? { ok: true, json: async () => account("DEMO") } : { ok: true, json: async () => [] },
    );
    vi.stubGlobal("fetch", fetch);
    render(<Accounts />);
    fireEvent.click(screen.getByRole("button", { name: "+ Connect Account" }));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Local" } });
    fireEvent.change(screen.getByLabelText("Server"), { target: { value: "TestServer" } });
    fireEvent.change(screen.getByLabelText("Login ID"), { target: { value: "123" } });
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    fireEvent.change(password, { target: { value: "test" + "-password" } });
    fireEvent.change(screen.getByLabelText("Terminal executable"), { target: { value: "C:/MT5/terminal64.exe" } });
    fireEvent.click(screen.getByRole("button", { name: "Connect Only" }));
    await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [, submitted] = fetch.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(submitted.body).action).toBe("CONNECT_ONLY");
    expect(password.value).toBe("");
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
  });

  it("provides the explicit execution-enable connection choice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<Accounts />);
    await screen.findByText(/No accounts connected/);
    fireEvent.click(screen.getByRole("button", { name: "+ Connect Account" }));
    expect(screen.getByRole("button", { name: "Connect & Enable Execution" })).toHaveValue(
      "CONNECT_AND_ENABLE_EXECUTION",
    );
  });

  it("shows account-service failure as unknown", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("unavailable")));
    render(<Accounts />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection state is unknown");
  });
});
