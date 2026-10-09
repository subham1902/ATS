import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import Strategies from "../app/strategies/page";
import { ServiceSummary } from "../components/ServiceSummary";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("operator interface", () => {
  it("filters actual strategy records without creating evidence", async () => {
    const record = {
      strategy_id: "XAU-001",
      definition_id: "trend",
      version: 1,
      status: "RESEARCH",
      direction: null,
      trade_horizon: null,
      datasets_tested: [],
      backtest_results: [],
      walk_forward_results: [],
      holdout_results: [],
      paper_results: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ strategies: [record, { ...record, strategy_id: "XAU-002", definition_id: "range" }] }),
      }),
    );
    render(<Strategies />);
    await screen.findByText(/Definition: trend/);
    fireEvent.change(screen.getByRole("searchbox", { name: "Find strategy" }), { target: { value: "XAU-002" } });
    expect(screen.queryByText(/Definition: trend/)).not.toBeInTheDocument();
    expect(screen.getByText(/Definition: range/)).toBeInTheDocument();
    expect(screen.getByText("UNKNOWN / UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("1 strategies")).toBeInTheDocument();
  });
  it("keeps null observations unknown and false distinct from missing", () => {
    render(
      <ServiceSummary
        state={{ loss_state: null, halted: false, authority_mode: "A2_PAPER", nested: { secret: "not rendered" } }}
      />,
    );
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.queryByText("not rendered")).not.toBeInTheDocument();
  });
});
