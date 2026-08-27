import { describe, expect, it } from "vitest";
import type {
  CandidateClass,
  EdgeLedgerEntry,
  OpportunityScannerReadModel,
  SurvivalTelemetryReadModel,
  AgentAccountabilityEntry,
} from "../operator-intelligence";

describe("operator-intelligence contract", () => {
  it("supports all required candidate classes as read-model union", () => {
    const classes: CandidateClass[] = ["STANDARD", "HIGH_CONVICTION", "CONVEX", "RARE_EVENT"];
    expect(classes).toHaveLength(4);
  });

  it("handles null / UNKNOWN metrics strictly without synthesizing data", () => {
    const entry: EdgeLedgerEntry = {
      candidate_id: "cand-test-1",
      timestamp: "2026-08-27T10:00:00Z",
      underlying: "NIFTY",
      instrument: "NIFTY26AUG24500CE",
      direction: "CALL",
      strategy: "VOL_EXPANSION",
      candidate_class: "STANDARD",
      predicted_probability: null,
      market_implied_probability: null,
      gross_edge: null,
      spread_cost: null,
      slippage_estimate: null,
      fees_estimate: null,
      theta_cost: null,
      execution_uncertainty: null,
      calibration_uncertainty: null,
      expected_net_value: null,
      portfolio_penalty: null,
      approved_capital: null,
      approved_quantity: null,
      portfolio_brain_outcome: "UNKNOWN",
      a04_outcome: "UNKNOWN",
      eventual_outcome: null,
      realized_pnl: null,
    };

    expect(entry.predicted_probability).toBeNull();
    expect(entry.market_implied_probability).toBeNull();
    expect(entry.portfolio_brain_outcome).toBe("UNKNOWN");
    expect(entry.a04_outcome).toBe("UNKNOWN");
  });

  it("structures opportunity scanner funnel and rejections correctly", () => {
    const scanner: OpportunityScannerReadModel = {
      last_scan_at: "2026-08-27T10:00:00Z",
      data_cutoff: "2026-08-27T09:59:50Z",
      source_state: "LIVE",
      funnel: {
        universe_observed: 150,
        fresh: 142,
        stale: 6,
        invalid_reference: 2,
      },
      rejections: {
        liquidity: 45,
        spread: 30,
        calibration: 15,
        negative_ev: 20,
        portfolio_capacity: 5,
        a04: 2,
      },
      candidates_by_class: {
        standard: 18,
        high_conviction: 4,
        convex: 2,
        rare_event: 1,
      },
      candidate_ids: ["c1", "c2", "c3"],
    };

    expect(scanner.funnel.universe_observed).toBe(150);
    expect(scanner.rejections.liquidity).toBe(45);
    expect(scanner.candidates_by_class.high_conviction).toBe(4);
  });

  it("enforces ADVISORY_ONLY authority invariant on agent accountability", () => {
    const agent: AgentAccountabilityEntry = {
      agent_id: "session-market-agent",
      role: "Session Market Agent",
      status: "ACTIVE",
      last_wake: "2026-08-27T10:00:00Z",
      wake_reason: "IV_SHOCK",
      data_cutoff: "2026-08-27T09:59:00Z",
      evidence_refs: ["ev-123"],
      recommendation: "VOL_EXPANSION",
      proposal_id: "prop-456",
      authority: "ADVISORY_ONLY",
      latency_ms: 320,
      provider_model: "openrouter/anthropic/claude-3.7-sonnet",
      tool_calls_count: 3,
      is_stale: false,
    };

    expect(agent.authority).toBe("ADVISORY_ONLY");
  });

  it("enforces safe survival telemetry schema", () => {
    const survival: SurvivalTelemetryReadModel = {
      effective_survival_state: "SAFE",
      user_selected_mode: "NORMAL",
      effective_mode: "SAFE",
      reason_codes: ["SESSION_DRAWDOWN"],
      session_equity: "982000.00",
      hwm: "1000000.00",
      drawdown_fraction: "0.018",
      available_risk: "25000.00",
      open_positions: 1,
      new_entry_permission: false,
      reduction_permission: true,
      feed_healthy: true,
      broker_healthy: true,
      reconciliation_active: false,
      loss_state: "CAUTION",
      last_state_at: "2026-08-27T10:00:00Z",
    };

    expect(survival.effective_survival_state).toBe("SAFE");
    expect(survival.new_entry_permission).toBe(false);
  });
});
