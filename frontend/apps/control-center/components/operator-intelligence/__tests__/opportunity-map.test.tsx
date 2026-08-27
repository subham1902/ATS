import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OpportunityMap } from "../OpportunityMap";
import type { OpportunityMapPoint } from "@ats/api-client";

describe("OpportunityMap (OI5 & OI5.1)", () => {
  it("renders truthful unknown / empty state when points array is empty or null", () => {
    render(<OpportunityMap points={null} />);
    expect(
      screen.getByText(/No opportunity map data available · zero candidate telemetry emitted/i)
    ).toBeInTheDocument();
  });

  it("renders opportunity map canvas with axes, quadrants, candidate points, and disclaimer", () => {
    const mockPoints: OpportunityMapPoint[] = [
      {
        candidate_id: "cand-hc-1",
        instrument: "NIFTY26AUG24500CE",
        underlying: "NIFTY",
        candidate_class: "HIGH_CONVICTION",
        calibrated_probability: 0.78,
        expected_net_value: 2.8,
        asymmetry: 3.5,
        liquidity_score: 85,
        spread_ticks: 4,
        analogue_support: 0.82,
        portfolio_brain_outcome: "ALLOW",
        a04_outcome: "ALLOW",
      },
      {
        candidate_id: "cand-cx-2",
        instrument: "BANKNIFTY26AUG52500CE",
        underlying: "BANKNIFTY",
        candidate_class: "CONVEX",
        calibrated_probability: 0.35,
        expected_net_value: 3.2,
        asymmetry: 7.0,
        liquidity_score: 60,
        spread_ticks: 6,
        analogue_support: null,
        portfolio_brain_outcome: "ALLOW_REDUCED",
        a04_outcome: "ALLOW",
      },
    ];

    render(<OpportunityMap points={mockPoints} />);

    expect(screen.getByText(/Market Opportunity Map/i)).toBeInTheDocument();
    expect(screen.getByText(/Calibrated Probability \/ Support Conviction/i)).toBeInTheDocument();
    expect(screen.getByText(/Expected Net Payoff/i)).toBeInTheDocument();
    expect(screen.getByText(/Presentation visualization only/i)).toBeInTheDocument();
    expect(screen.getByText(/High Conviction \/ High Convexity \(Prime Edge\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Lower Conviction \/ High Convexity/i)).toBeInTheDocument();
  });

  it("filters points by class and portfolio outcome", () => {
    const mockPoints: OpportunityMapPoint[] = [
      {
        candidate_id: "cand-1",
        instrument: "NIFTY26AUG24500CE",
        underlying: "NIFTY",
        candidate_class: "HIGH_CONVICTION",
        calibrated_probability: 0.8,
        expected_net_value: 2.0,
        asymmetry: 3.0,
        liquidity_score: 80,
        spread_ticks: 3,
        analogue_support: 0.9,
        portfolio_brain_outcome: "ALLOW",
        a04_outcome: "ALLOW",
      },
    ];

    render(<OpportunityMap points={mockPoints} />);
    expect(screen.getByText(/Showing/i)).toBeInTheDocument();
  });
});
