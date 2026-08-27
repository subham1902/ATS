import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EdgeLedger } from "../EdgeLedger";
import type { EdgeLedgerReadModel } from "@ats/api-client";

describe("EdgeLedger (OI2 & OI2.1)", () => {
  it("renders truthful unknown / empty state when ledger is null", () => {
    render(<EdgeLedger ledger={null} />);
    expect(
      screen.getByText(/No Edge Ledger records available · state unknown/i)
    ).toBeInTheDocument();
  });

  it("renders edge ledger rows with cost decomposition, decisions and UNKNOWN values", () => {
    const mockLedger: EdgeLedgerReadModel = {
      as_of: "2026-08-27T10:00:00Z",
      source: "LIVE",
      entries: [
        {
          candidate_id: "cand-uuid-1234-5678",
          timestamp: "2026-08-27T10:00:00Z",
          underlying: "NIFTY",
          instrument: "NIFTY26AUG24500CE",
          direction: "CALL",
          strategy: "VOL_EXPANSION",
          candidate_class: "HIGH_CONVICTION",
          predicted_probability: 0.76,
          market_implied_probability: 0.52,
          gross_edge: 1.85,
          spread_cost: 0.15,
          slippage_estimate: 0.1,
          fees_estimate: 0.05,
          theta_cost: 0.2,
          execution_uncertainty: 0.05,
          calibration_uncertainty: 0.05,
          expected_net_value: 1.25,
          portfolio_penalty: 0.0,
          approved_capital: "50000.00",
          approved_quantity: "75",
          portfolio_brain_outcome: "ALLOW",
          a04_outcome: "ALLOW",
          eventual_outcome: "WIN",
          realized_pnl: "+1.30R",
        },
        {
          candidate_id: "cand-uuid-9999-0000",
          timestamp: "2026-08-27T10:05:00Z",
          underlying: "BANKNIFTY",
          instrument: "BANKNIFTY26AUG51000PE",
          direction: "PUT",
          strategy: "MOMENTUM_BREAKOUT",
          candidate_class: "CONVEX",
          predicted_probability: null, // UNKNOWN
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
          portfolio_brain_outcome: "DENY",
          a04_outcome: "DENY",
          eventual_outcome: null,
          realized_pnl: null,
        },
      ],
    };

    render(<EdgeLedger ledger={mockLedger} />);

    expect(screen.getByText("NIFTY26AUG24500CE")).toBeInTheDocument();
    expect(screen.getByText("76.0%")).toBeInTheDocument();
    expect(screen.getByText("+1.85R")).toBeInTheDocument();
    expect(screen.getByText("+1.25R")).toBeInTheDocument();
    expect(screen.getByText("BANKNIFTY26AUG51000PE")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });

  it("filters ledger rows by candidate class and decision", () => {
    const mockLedger: EdgeLedgerReadModel = {
      as_of: "2026-08-27T10:00:00Z",
      source: "LIVE",
      entries: [
        {
          candidate_id: "cand-1",
          timestamp: "2026-08-27T10:00:00Z",
          underlying: "NIFTY",
          instrument: "NIFTY26AUG24500CE",
          direction: "CALL",
          strategy: "VOL_EXPANSION",
          candidate_class: "HIGH_CONVICTION",
          predicted_probability: 0.75,
          market_implied_probability: 0.5,
          gross_edge: 1.5,
          spread_cost: 0.1,
          slippage_estimate: 0.1,
          fees_estimate: 0.05,
          theta_cost: 0.1,
          execution_uncertainty: 0.0,
          calibration_uncertainty: 0.0,
          expected_net_value: 1.15,
          portfolio_penalty: 0.0,
          approved_capital: "25000",
          approved_quantity: "50",
          portfolio_brain_outcome: "ALLOW",
          a04_outcome: "ALLOW",
          eventual_outcome: null,
          realized_pnl: null,
        },
        {
          candidate_id: "cand-2",
          timestamp: "2026-08-27T10:01:00Z",
          underlying: "BANKNIFTY",
          instrument: "BANKNIFTY26AUG52000CE",
          direction: "CALL",
          strategy: "MEAN_REVERSION",
          candidate_class: "STANDARD",
          predicted_probability: 0.55,
          market_implied_probability: 0.48,
          gross_edge: 0.4,
          spread_cost: 0.3,
          slippage_estimate: 0.1,
          fees_estimate: 0.05,
          theta_cost: 0.1,
          execution_uncertainty: 0.0,
          calibration_uncertainty: 0.0,
          expected_net_value: -0.15,
          portfolio_penalty: 0.0,
          approved_capital: "0",
          approved_quantity: "0",
          portfolio_brain_outcome: "DENY",
          a04_outcome: "DENY",
          eventual_outcome: null,
          realized_pnl: null,
        },
      ],
    };

    render(<EdgeLedger ledger={mockLedger} />);

    expect(screen.getByText("NIFTY26AUG24500CE")).toBeInTheDocument();
    expect(screen.getByText("BANKNIFTY26AUG52000CE")).toBeInTheDocument();

    // Expand cost breakdown of row 1
    const hideOrBreakdownButtons = screen.getAllByText("Cost Breakdown");
    fireEvent.click(hideOrBreakdownButtons[0]);
    expect(screen.getByText(/Spread Cost:/i)).toBeInTheDocument();
  });
});
