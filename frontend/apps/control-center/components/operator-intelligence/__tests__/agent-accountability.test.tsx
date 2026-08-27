import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { AgentAccountability } from "../AgentAccountability";
import type { AgentAccountabilityEntry, TimelineEvent } from "@ats/api-client";

describe("AgentAccountability (OI4 & OI4.1)", () => {
  it("renders truthful unknown / empty state when agents list is empty or null", () => {
    render(<AgentAccountability agents={null} />);
    expect(
      screen.getByText(/No agent accountability telemetry available · intelligence harness offline/i)
    ).toBeInTheDocument();
  });

  it("renders agent cards with mandatory ADVISORY ONLY badge and metrics", () => {
    const mockAgents: AgentAccountabilityEntry[] = [
      {
        agent_id: "session-market-agent",
        role: "Session Market Agent",
        status: "ACTIVE",
        last_wake: "2026-08-27T10:00:00Z",
        wake_reason: "IV_SHOCK",
        data_cutoff: "2026-08-27T09:59:00Z",
        evidence_refs: ["ev-snapshot-01", "ev-regime-02"],
        recommendation: "VOL_EXPANSION",
        proposal_id: "prop-1234",
        authority: "ADVISORY_ONLY",
        latency_ms: 280,
        provider_model: "openrouter/anthropic/claude-3.7-sonnet",
        tool_calls_count: 4,
        is_stale: false,
      },
      {
        agent_id: "position-agent",
        role: "Position Agent",
        status: "STALE",
        last_wake: "2026-08-27T09:15:00Z",
        wake_reason: "POSITION_PNL_DRIFT",
        data_cutoff: "2026-08-27T09:10:00Z",
        evidence_refs: [],
        recommendation: "TIGHTEN_STOPS",
        proposal_id: null,
        authority: "ADVISORY_ONLY",
        latency_ms: 450,
        provider_model: "openrouter/anthropic/claude-3.7-sonnet",
        tool_calls_count: 2,
        is_stale: true,
      },
    ];

    const mockTimeline: TimelineEvent[] = [
      {
        event_id: "evt-01",
        timestamp: "2026-08-27T10:00:00Z",
        material_event: "NIFTY IV SPIKE > 2.5 sigma",
        agent_wake: "Session Market Agent",
        evidence_queried: ["OptionChainSnapshot", "RegimeEvidence"],
        recommendation: "VOL_EXPANSION",
        proposal_id: "prop-1234",
        governor_result: "APPROVED",
        authority_note: "ADVISORY_ONLY — deterministic governor authorized",
      },
    ];

    render(<AgentAccountability agents={mockAgents} timeline={mockTimeline} />);

    expect(screen.getAllByText("Session Market Agent").length).toBeGreaterThan(0);
    expect(screen.getByText("Position Agent")).toBeInTheDocument();
    expect(screen.getAllByText("ADVISORY ONLY").length).toBeGreaterThan(0);
    expect(screen.getAllByText("VOL_EXPANSION").length).toBeGreaterThan(0);
    expect(screen.getByText(/⚠️ STALE/i)).toBeInTheDocument();

    // Timeline elements
    expect(screen.getByText("NIFTY IV SPIKE > 2.5 sigma")).toBeInTheDocument();
    expect(screen.getByText("APPROVED")).toBeInTheDocument();
    expect(
      screen.getByText(/ADVISORY_ONLY — deterministic governor authorized/i)
    ).toBeInTheDocument();
  });
});
