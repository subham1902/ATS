import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { OperatorIntelligenceView } from "../OperatorIntelligenceView";
import { formatTimeIST } from "../../../lib/formatTime";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";

describe("Operator Intelligence Live Provenance & Truthfulness Regressions", () => {
  it("enforces that LIVE mode cannot silently fall back to fixtures when initialSnapshot is empty LIVE", () => {
    const liveEmptySnapshot: OperatorIntelligenceSnapshot = {
      provenance: "LIVE",
      scanner: {
        last_scan_at: "2026-08-27T08:00:00Z",
        data_cutoff: "2026-08-27T08:00:00Z",
        source_state: "LIVE",
        funnel: { universe_observed: 22, fresh: 22, stale: 0, invalid_reference: 0 },
        rejections: { liquidity: 0, spread: 0, calibration: 0, negative_ev: 0, portfolio_capacity: 0, a04: 0 },
        candidates_by_class: { standard: 0, high_conviction: 0, convex: 0, rare_event: 0 },
        candidate_ids: [],
      },
      edge_ledger: { entries: [], as_of: "2026-08-27T08:00:00Z", source: "LIVE" },
      survival: {
        effective_survival_state: "NORMAL",
        user_selected_mode: "NORMAL",
        effective_mode: "NORMAL",
        reason_codes: [],
        session_equity: "100000.00",
        hwm: "100000.00",
        drawdown_fraction: "0",
        available_risk: "100000.00",
        open_positions: 0,
        new_entry_permission: true,
        reduction_permission: true,
        feed_healthy: true,
        broker_healthy: true,
        reconciliation_active: false,
        loss_state: "NORMAL",
        last_state_at: "2026-08-27T08:00:00Z",
      },
      agents: [],
      timeline: [],
      opportunity_map: [],
      evidence_lineage: {},
    };

    render(<OperatorIntelligenceView initialSnapshot={liveEmptySnapshot} isLiveAvailable={true} />);

    // 1. Provenance badge must be LIVE TELEMETRY, not FIXTURE
    expect(screen.getByText(/● LIVE TELEMETRY/i)).toBeInTheDocument();
    expect(screen.queryByText(/FIXTURE: NORMAL_QUIET_MARKET/i)).not.toBeInTheDocument();

    // 2. Candidate from fixture (cand-nqe-01) must NOT be present
    expect(screen.queryByText(/cand-nqe-01/i)).not.toBeInTheDocument();

    // 3. Must show honest empty candidate message
    expect(screen.getByText(/NO LIVE CANDIDATES/i)).toBeInTheDocument();
  });

  it("verifies formatTimeIST produces deterministic HH:MM:SS IST without hydration divergence", () => {
    const isoUtc = "2026-08-27T07:30:00.000Z";
    // 07:30 UTC + 5:30 = 13:00:00 IST
    const formatted = formatTimeIST(isoUtc);
    expect(formatted).toBe("13:00:00 IST");

    expect(formatTimeIST(null)).toBe("UNKNOWN");
    expect(formatTimeIST("invalid")).toBe("UNKNOWN");
  });
});
