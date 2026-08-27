import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  FIXTURE_SCENARIOS,
  getFixtureScenario,
} from "../fixtures";
import { OperatorIntelligenceView } from "../OperatorIntelligenceView";
import type { FixtureScenarioId } from "@ats/api-client";

describe("Operator Intelligence Fixtures & Replay (OI7)", () => {
  it("provides all 10 deterministic fixture scenarios", () => {
    const requiredScenarios: FixtureScenarioId[] = [
      "NORMAL_QUIET_MARKET",
      "HIGH_CONVICTION_CANDIDATE",
      "HYPOTHETICAL_CONVEX_CANDIDATE",
      "HYPOTHETICAL_RARE_EVENT_CANDIDATE",
      "SAFE_DUE_DRAWDOWN",
      "HALTED",
      "HARNESS_UNAVAILABLE",
      "STALE_AGENT_ADVISORY",
      "CANDIDATE_REJECTED_PORTFOLIO_BRAIN",
      "CANDIDATE_DENIED_A04",
    ];

    expect(Object.keys(FIXTURE_SCENARIOS)).toHaveLength(10);
    for (const scId of requiredScenarios) {
      const snap = getFixtureScenario(scId);
      expect(snap).toBeDefined();
      expect(snap.scenario_id).toBe(scId);
      expect(snap.provenance).toBe("FIXTURE");
      expect(snap.survival).toBeDefined();
      expect(snap.scanner).toBeDefined();
      expect(snap.edge_ledger).toBeDefined();
    }
  });

  it("renders OperatorIntelligenceView with scenario selector and updates telemetry on switch", () => {
    render(<OperatorIntelligenceView />);

    expect(screen.getByText(/Operator Intelligence & Observability/i)).toBeInTheDocument();
    expect(screen.getByText(/ADVISORY_ONLY · NO REAL ORDERS/i)).toBeInTheDocument();
    expect(screen.getByText(/NORMAL · Unrestricted Bounded Execution/i)).toBeInTheDocument();

    // Select scenario 6: HALTED
    const select = screen.getByRole("combobox", { name: /Scenario Replay Selector/i });
    fireEvent.change(select, { target: { value: "HALTED" } });

    expect(screen.getByText(/SYSTEM HALTED · All Trading Blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/SAFETY_HALTED/i)).toBeInTheDocument();
  });

  it("verifies SAFE_DUE_DRAWDOWN scenario triggers SAFE mode and entry prohibitions", () => {
    const snap = getFixtureScenario("SAFE_DUE_DRAWDOWN");
    expect(snap.survival.effective_survival_state).toBe("SAFE");
    expect(snap.survival.new_entry_permission).toBe(false);
    expect(snap.survival.reduction_permission).toBe(true);
    expect(snap.survival.reason_codes).toContain("SESSION_DRAWDOWN");
  });

  it("verifies HARNESS_UNAVAILABLE scenario shows OFFLINE agents and safe state", () => {
    const snap = getFixtureScenario("HARNESS_UNAVAILABLE");
    expect(snap.survival.effective_survival_state).toBe("SAFE");
    expect(snap.agents.every((a) => a.status === "OFFLINE")).toBe(true);
    expect(snap.agents.every((a) => a.authority === "ADVISORY_ONLY")).toBe(true);
  });
});
