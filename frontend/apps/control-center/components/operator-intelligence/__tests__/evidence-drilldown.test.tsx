import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EvidenceDrilldown } from "../EvidenceDrilldown";
import type { EvidenceLineageNode } from "@ats/api-client";

describe("EvidenceDrilldown (OI6)", () => {
  it("renders truthful unknown / empty state when lineageMap is null or empty", () => {
    render(<EvidenceDrilldown lineageMap={null} />);
    expect(
      screen.getByText(/No machine evidence lineage available · select or enter a candidate ID/i)
    ).toBeInTheDocument();
  });

  it("renders lineage DAG stages with status badges, summaries and extracted metrics", () => {
    const mockLineage: Record<string, EvidenceLineageNode[]> = {
      "cand-1234": [
        {
          node_type: "MarketSnapshot",
          node_id: "node-snap-01",
          timestamp: "2026-08-27T09:59:50Z",
          status: "VERIFIED",
          metrics: { spot: 24510.5, iv_atm: 14.8, bid_ask_spread_ticks: 2 },
          hash: "a8f3b20c91e457d11099238475aabbcd",
          summary: "Authoritative L1/L2 book snapshot captured across 15 ATM/OTM strikes.",
        },
        {
          node_type: "RegimeEvidence",
          node_id: "node-regime-02",
          timestamp: "2026-08-27T09:59:52Z",
          status: "VERIFIED",
          metrics: { regime: "VOLATILITY_EXPANSION", regime_confidence: 0.88 },
          hash: "c91e457d11099238475aabbcda8f3b20",
          summary: "Market regime classified as VOLATILITY_EXPANSION with 0.88 confidence.",
        },
        {
          node_type: "OpportunityCandidate",
          node_id: "node-cand-03",
          timestamp: "2026-08-27T09:59:55Z",
          status: "VERIFIED",
          metrics: { candidate_class: "HIGH_CONVICTION", net_ev: 1.45, reward_risk: 3.2 },
          hash: "e457d11099238475aabbcda8f3b20c91",
          summary: "Candidate proposed: NIFTY Bull Call Spread 24500/24700 CE.",
        },
        {
          node_type: "PortfolioAllocationDecision",
          node_id: "node-port-04",
          timestamp: "2026-08-27T09:59:56Z",
          status: "VERIFIED",
          metrics: { outcome: "ALLOW", approved_capital: 50000, approved_qty: 75 },
          hash: "11099238475aabbcda8f3b20c91e457d",
          summary: "Portfolio Brain permitted capital allocation with zero penalty.",
        },
        {
          node_type: "A04Decision",
          node_id: "node-a04-05",
          timestamp: "2026-08-27T09:59:58Z",
          status: "VERIFIED",
          metrics: { kernel_decision: "ALLOW", rule_checks_passed: 12 },
          hash: "75aabbcda8f3b20c91e457d110992384",
          summary: "A04 deterministic kernel verified risk limits and approved candidate.",
        },
      ],
    };

    render(<EvidenceDrilldown candidateId="cand-1234" lineageMap={mockLineage} />);

    expect(screen.getByText("MarketSnapshot")).toBeInTheDocument();
    expect(screen.getByText("RegimeEvidence")).toBeInTheDocument();
    expect(screen.getByText("OpportunityCandidate")).toBeInTheDocument();
    expect(screen.getByText("PortfolioAllocationDecision")).toBeInTheDocument();
    expect(screen.getByText("A04Decision")).toBeInTheDocument();
    expect(screen.getAllByText("VERIFIED").length).toBe(5);

    // Expand MarketSnapshot node inspector
    fireEvent.click(screen.getByText("MarketSnapshot"));
    expect(screen.getByText(/Extracted Verified Parameters:/i)).toBeInTheDocument();
    expect(screen.getByText(/iv_atm:/i)).toBeInTheDocument();
  });
});
