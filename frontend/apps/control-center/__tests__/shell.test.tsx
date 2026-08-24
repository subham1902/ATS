import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Shell } from "../components/Shell";
import { SystemPanel, PolicyPanel, CampaignPanel, CandidatePanel, RiskPanel, TokenPanel, ActivityPanel } from "../components/panels";
import type { SystemReadModel, PolicyReadModel } from "@ats/api-client";

// Mock next/navigation usePathname
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("next/link", () => ({ default: (props: unknown) => {
  const { children, href } = props as { children: unknown; href: string };
  // eslint-disable-next-line @next/next/no-html-link-for-pages
  return <a href={href}>{children as string}</a>;
}}));

describe("shell", () => {
  it("renders header/nav/main and skip link", () => {
    render(<Shell systemState="READY" sseStatus="connected"><div>content</div></Shell>);
    expect(screen.getByText("ATS CONTROL CENTER")).toBeInTheDocument();
    expect(screen.getByText("A2_PAPER")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(document.querySelector('a[href="#main"]')).toBeTruthy();
  });

  it("UNKNOWN system state looks unknown not healthy", () => {
    render(<Shell systemState="UNKNOWN" sseStatus="disconnected">x</Shell>);
    expect(screen.getByLabelText("system state UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText(/unknown, not healthy/i)).toBeInTheDocument();
  });
});

describe("system status", () => {
  it("renders READY with loss state", () => {
    const sys: SystemReadModel = {
      system_state: "READY",
      system_state_version: 1,
      readiness: "READY",
      degradation_indicators: [],
      loss_state: "NORMAL",
      active_policy_id: "00000000-0000-0000-0000-000000000001",
      active_policy_version: 1,
      active_campaign_id: null,
      active_campaign_version: null,
      authority_mode: "A2_PAPER",
      reconciliation_active: false,
      halted: false,
      last_state_at: "2026-01-01T00:00:00Z",
      last_event_at: null,
    };
    render(<SystemPanel system={sys} healthLive={{ status: "LIVE", ready: true, reason_codes: [] }} healthReady={{ status: "READY", ready: true, reason_codes: [] }} error={null} />);
    expect(screen.getByLabelText("system state READY")).toBeInTheDocument();
    expect(screen.getByText("A2_PAPER")).toBeInTheDocument();
    expect(screen.getByText((t) => t.includes("loss") && t.includes("NORMAL"))).toBeInTheDocument();
  });

  it("UNKNOWN not shown as healthy", () => {
    const sys: SystemReadModel = {
      system_state: "UNKNOWN",
      system_state_version: 0,
      readiness: "UNKNOWN",
      degradation_indicators: [],
      loss_state: "NORMAL",
      active_policy_id: null,
      active_policy_version: null,
      active_campaign_id: null,
      active_campaign_version: null,
      authority_mode: "A2_PAPER",
      reconciliation_active: false,
      halted: false,
      last_state_at: "2026-01-01T00:00:00Z",
      last_event_at: null,
    };
    render(<SystemPanel system={sys} healthLive={null} healthReady={null} error={null} />);
    expect(screen.getByLabelText("system state UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText(/unknown, not healthy/i)).toBeInTheDocument();
  });

  it("DEGRADED shows indicator", () => {
    const sys: SystemReadModel = {
      system_state: "DEGRADED",
      system_state_version: 2,
      readiness: "DEGRADED",
      degradation_indicators: ["DATA_STALE"],
      loss_state: "CAUTION",
      active_policy_id: null,
      active_policy_version: null,
      active_campaign_id: null,
      active_campaign_version: null,
      authority_mode: "A2_PAPER",
      reconciliation_active: false,
      halted: false,
      last_state_at: "2026-01-01T00:00:00Z",
      last_event_at: null,
    };
    render(<SystemPanel system={sys} healthLive={null} healthReady={null} error={null} />);
    expect(screen.getAllByText(/DEGRADED/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/DATA_STALE/)).toBeInTheDocument();
  });
});

describe("health", () => {
  it("health panel shows live/ready", () => {
    const sys: SystemReadModel = {
      system_state: "READY", system_state_version: 1, readiness: "READY", degradation_indicators: [], loss_state: "NORMAL",
      active_policy_id: null, active_policy_version: null, active_campaign_id: null, active_campaign_version: null,
      authority_mode: "A2_PAPER", reconciliation_active: false, halted: false, last_state_at: "2026-01-01T00:00:00Z", last_event_at: null,
    };
    render(<SystemPanel system={sys} healthLive={{ status: "LIVE", ready: true, reason_codes: [] }} healthReady={{ status: "READY", ready: true, reason_codes: [] }} error={null} />);
    expect(screen.getByText(/health\/live: LIVE/)).toBeInTheDocument();
    expect(screen.getByText(/health\/ready: READY/)).toBeInTheDocument();
  });
});

describe("policy panel", () => {
  it("renders policy with A2 level", () => {
    const policy: PolicyReadModel = {
      policy_id: "00000000-0000-0000-0000-000000000001",
      policy_version: 1,
      owner_subject: "owner@example.com",
      lifecycle_status: "ACTIVE",
      autonomy_level: "A2",
      universe: ["EURUSD"],
      timeframe: "5m",
      event_definition_id: "EVT1",
      forecast_horizon_bars: 10,
      confidence_threshold: "0.6",
      minimum_calibration_support: 100,
      minimum_reward_risk: "1.5",
      valid_from: "2026-01-01T00:00:00Z",
      valid_until: "2027-01-01T00:00:00Z",
      activated_at: "2026-01-02T00:00:00Z",
    };
    render(<PolicyPanel policy={policy} error={null} />);
    expect(screen.getByText("00000000-0000-0000-0000-000000000001")).toBeInTheDocument();
    expect(screen.getByText("A2")).toBeInTheDocument();
  });

  it("empty state when no policy", () => {
    render(<PolicyPanel policy={null} error={null} />);
    expect(screen.getByText("No active policy")).toBeInTheDocument();
  });

  it("error state renders envelope", () => {
    render(<PolicyPanel policy={null} error={{ code: "RESOURCE_NOT_FOUND", message: "not found", correlation_id: "cid-1", details: [] }} />);
    expect(screen.getByText(/RESOURCE_NOT_FOUND/)).toBeInTheDocument();
    expect(screen.getByText("cid-1")).toBeInTheDocument();
  });
});

describe("campaign empty state", () => {
  it("shows No active campaign", () => {
    render(<CampaignPanel campaign={null} error={null} />);
    expect(screen.getByText("No active campaign")).toBeInTheDocument();
  });
});

describe("candidate panel", () => {
  it("shows empty", () => {
    render(<CandidatePanel candidate={null} error={null} />);
    expect(screen.getByText("No candidates available")).toBeInTheDocument();
  });
  it("shows candidate when present", () => {
    render(<CandidatePanel candidate={{ candidate_id: "c1", candidate_version: 1, instrument_id: "EURUSD", market_context_id: "m1", thesis_id: "t1", thesis_version: 1, distribution_id: "d1", campaign_id: "camp1", campaign_version: 1, strategy_definition_id: "s1", strategy_definition_version: 1, calibrated_probability: "0.55", expected_net_edge_r: 0.2, expected_reward_risk: "2.0", status: "CREATED", risk_decision_id: null, advisory_id: null, autonomy_token_id: null, created_at: "2026-01-01T00:00:00Z", expires_at: "2026-01-02T00:00:00Z" } as unknown as import("@ats/api-client").CandidateReadModel} error={null} />);
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
  });
});

describe("risk panel", () => {
  it("shows No risk decisions yet", () => {
    render(<RiskPanel decision={null} error={null} />);
    expect(screen.getByText("No risk decisions yet")).toBeInTheDocument();
  });
});

describe("token status", () => {
  it("safe view never exposes nonce", () => {
    const { container } = render(<TokenPanel token={{ token_id: "tok1", scope: "A2_PAPER", candidate_id: "c1", policy_id: "p1", policy_version: 1, risk_decision_id: "r1", advisory_id: "a1", system_state_version: 1, issued_at: "2026-01-01T00:00:00Z", expires_at: "2026-01-02T00:00:00Z", consumed_at: null, state: "ISSUED" } as import("@ats/api-client").AutonomyTokenReadModel} error={null} />);
    expect(screen.getByText("ISSUED")).toBeInTheDocument();
    // Details must not contain nonce field label
    const dtText = container.textContent ?? "";
    // notice mentions nonce but fields should not have a label "nonce"
    expect(screen.queryByText(/^nonce$/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Safe view only/)).toBeInTheDocument();
    expect(dtText).not.toContain("payload_hash");
  });

  it("empty token state", () => {
    render(<TokenPanel token={null} error={null} />);
    expect(screen.getByText("No autonomy tokens yet")).toBeInTheDocument();
  });
});

describe("SSE", () => {
  it("connection indicator statuses", async () => {
    const { rerender } = render(<Shell systemState="READY" sseStatus="connecting">x</Shell>);
    expect(screen.getByLabelText("SSE connecting")).toBeInTheDocument();
    rerender(<Shell systemState="READY" sseStatus="connected">x</Shell>);
    expect(screen.getByLabelText("SSE connected")).toBeInTheDocument();
    rerender(<Shell systemState="READY" sseStatus="disconnected">x</Shell>);
    expect(screen.getByLabelText("SSE disconnected")).toBeInTheDocument();
    rerender(<Shell systemState="READY" sseStatus="error">x</Shell>);
    expect(screen.getByLabelText("SSE error")).toBeInTheDocument();
  });
});

describe("activity empty", () => {
  it("shows No runtime activity yet", () => {
    render(<ActivityPanel items={[]} error={null} />);
    expect(screen.getByText("No runtime activity yet")).toBeInTheDocument();
  });
});
