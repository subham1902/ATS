import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { AccountConfiguration } from "../components/AccountConfiguration";
import { LotPreview } from "../components/LotPreview";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("account configuration", () => {
  it("saves a paused versioned configuration without execution consent", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      let data: unknown;
      if (url.endsWith("readiness")) data = { reason_codes: ["EXTERNAL_ROUTING_NOT_COMMISSIONED"] };
      else if (url.endsWith("strategy-os"))
        data = { strategies: [{ strategy_id: "XAU-020", version: 1, status: "RESEARCH" }] };
      else if (init?.method === "PUT") data = { configuration: JSON.parse(String(init.body)).config };
      else data = { configuration: null };
      return { ok: true, json: async () => data };
    });
    vi.stubGlobal("fetch", fetcher);
    render(<AccountConfiguration accountId="ACC-test" />);
    await screen.findByRole("checkbox", { name: "XAU-020 v1" });
    fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
    await screen.findByText(/Configuration saved/);
    const write = fetcher.mock.calls.find(([, init]) => init?.method === "PUT");
    const payload = JSON.parse(String(write?.[1]?.body));
    expect(payload.expected_revision).toBe(0);
    expect(payload.config.revision).toBe(1);
    expect(payload.config.paused).toBe(true);
    expect(payload.config.monthly_loss_fraction).toBe("0.08");
    expect(payload.config.execution_enabled).toBeUndefined();
  });
  it("shows a broker preview failure without inventing lot values", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<LotPreview accountId="ACC-test" />);
    fireEvent.change(screen.getByLabelText("Entry price"), { target: { value: "2300" } });
    fireEvent.change(screen.getByLabelText("Stop-loss price"), { target: { value: "2290" } });
    fireEvent.change(screen.getByLabelText(/Modeled round-trip/), { target: { value: "44" } });
    fireEvent.submit(screen.getByRole("button", { name: "Calculate lots" }).closest("form")!);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Preview unavailable"));
    expect(screen.queryByText("volume")).not.toBeInTheDocument();
  });
});
