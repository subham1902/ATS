import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { OpportunityScanner } from "../OpportunityScanner";
import type { OpportunityScannerReadModel } from "@ats/api-client";

describe("OpportunityScanner (OI1)", () => {
  it("renders truthful unknown / empty state when scanner is null", () => {
    render(<OpportunityScanner scanner={null} />);
    expect(
      screen.getByText(/No scanner telemetry available · state unknown · not active/i)
    ).toBeInTheDocument();
  });

  it("renders funnel counts, rejection breakdown and candidate classes", () => {
    const mockScanner: OpportunityScannerReadModel = {
      last_scan_at: "2026-08-27T10:00:00Z",
      data_cutoff: "2026-08-27T09:59:50Z",
      source_state: "LIVE",
      funnel: {
        universe_observed: 200,
        fresh: 190,
        stale: 7,
        invalid_reference: 4,
      },
      rejections: {
        liquidity: 51,
        spread: 32,
        calibration: 23,
        negative_ev: 44,
        portfolio_capacity: 5,
        a04: 3,
      },
      candidates_by_class: {
        standard: 35,
        high_conviction: 8,
        convex: 6,
        rare_event: 1,
      },
      candidate_ids: ["cand-01", "cand-02"],
    };

    render(<OpportunityScanner scanner={mockScanner} />);

    expect(screen.getByText("Opportunity Scanner")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument(); // Universe Observed
    expect(screen.getByText("190")).toBeInTheDocument(); // Fresh
    expect(screen.getByText("7")).toBeInTheDocument(); // Stale
    expect(screen.getByText("4")).toBeInTheDocument(); // Invalid Ref
    expect(screen.getByText("51")).toBeInTheDocument(); // Liquidity rej
    expect(screen.getByText("35")).toBeInTheDocument(); // Standard candidate count
    expect(screen.getByText("8")).toBeInTheDocument(); // High conviction
    expect(screen.getByText("cand-01")).toBeInTheDocument();
  });

  it("renders stale warning when source_state is STALE", () => {
    const mockScanner: OpportunityScannerReadModel = {
      last_scan_at: "2026-08-27T09:00:00Z",
      data_cutoff: "2026-08-27T08:55:00Z",
      source_state: "STALE",
      funnel: { universe_observed: 50, fresh: 0, stale: 50, invalid_reference: 0 },
      rejections: { liquidity: 0, spread: 0, calibration: 0, negative_ev: 0, portfolio_capacity: 0, a04: 0 },
      candidates_by_class: { standard: 0, high_conviction: 0, convex: 0, rare_event: 0 },
      candidate_ids: [],
    };

    render(<OpportunityScanner scanner={mockScanner} />);
    expect(screen.getByText(/⚠️ Scan telemetry stale/i)).toBeInTheDocument();
  });
});
