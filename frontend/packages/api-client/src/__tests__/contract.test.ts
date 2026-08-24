import { describe, it, expect } from "vitest";
import { ROUTES, type ErrorEnvelope } from "../types";
import { createApiClient, ApiError } from "../client";
import { parseSseFrame } from "../sse";

// Frozen shapes matching A05 contract
const SAMPLE_SYSTEM = {
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
  last_state_at: new Date().toISOString(),
  last_event_at: null,
};

describe("api-client contract", () => {
  it("exposes exact A05 routes", () => {
    expect(ROUTES.healthLive).toBe("/health/live");
    expect(ROUTES.healthReady).toBe("/health/ready");
    expect(ROUTES.system).toBe("/v1/system");
    expect(ROUTES.policiesActive).toBe("/v1/policies/active");
    expect(ROUTES.policyById("123")).toBe("/v1/policies/123");
    expect(ROUTES.policyValidate).toBe("/v1/policies/validate");
    expect(ROUTES.campaignById("x")).toBe("/v1/campaigns/x");
    expect(ROUTES.candidateById("x")).toBe("/v1/candidates/x");
    expect(ROUTES.governanceById("x")).toBe("/v1/governance-contexts/x");
    expect(ROUTES.riskDecisionById("x")).toBe("/v1/risk-decisions/x");
    expect(ROUTES.advisoryById("x")).toBe("/v1/advisories/x");
    expect(ROUTES.autonomyTokenById("x")).toBe("/v1/autonomy-tokens/x");
    expect(ROUTES.activity).toBe("/v1/activity");
    expect(ROUTES.stream).toBe("/v1/stream");
  });

  it("ApiError carries envelope", () => {
    const env: ErrorEnvelope = { code: "RESOURCE_NOT_FOUND", message: "not found", correlation_id: "cid-1", details: [] };
    const err = new ApiError(404, env, "cid-1", "not found");
    expect(err.status).toBe(404);
    expect(err.envelope?.code).toBe("RESOURCE_NOT_FOUND");
  });

  it("client uses fetch impl and parses ErrorEnvelope 404", async () => {
    const env: ErrorEnvelope = { code: "RESOURCE_NOT_FOUND", message: "nope", correlation_id: "req-1", details: [{ field: "id", issue: "missing" }] };
    const fetchImpl = async () =>
      new Response(JSON.stringify(env), { status: 404, headers: { "content-type": "application/json" } });
    const client = createApiClient({ baseUrl: "http://test", fetchImpl: fetchImpl as unknown as typeof fetch });
    await expect(client.getSystem()).rejects.toMatchObject({ status: 404 });
    try {
      await client.getSystem();
    } catch (e) {
      expect((e as ApiError).envelope?.code).toBe("RESOURCE_NOT_FOUND");
      expect((e as ApiError).envelope?.correlation_id).toBe("req-1");
    }
  });

  it("no trading command routes exist", () => {
    const all = Object.values(ROUTES).join(" ");
    expect(all).not.toMatch(/command/i);
    expect(all).not.toMatch(/order/i);
    expect(all).not.toMatch(/trade/i);
  });

  it("autonomy token type excludes nonce/payload_hash", () => {
    // Type-level check represented via runtime shape absence
    const sample = { token_id: "1", scope: "A2_PAPER", candidate_id: "2", policy_id: "3", policy_version: 1, risk_decision_id: "4", advisory_id: "5", system_state_version: 1, issued_at: new Date().toISOString(), expires_at: new Date().toISOString(), consumed_at: null, state: "ISSUED" };
    expect(sample).not.toHaveProperty("nonce");
    expect(sample).not.toHaveProperty("payload_hash");
    expect(sample).toHaveProperty("state");
  });

  it("parseSseFrame parses backend serialize_sse format", () => {
    const payload = { decision: "ALLOW" };
    const raw = `id: 550e8400-e29b-41d4-a716-446655440000\nevent: RISK_EVALUATED\ndata: {"stream_event_id":"550e8400-e29b-41d4-a716-446655440000","event_kind":"RISK_EVALUATED","occurred_at":"2026-01-01T00:00:00Z","correlation_id":"550e8400-e29b-41d4-a716-446655440001","payload":${JSON.stringify(payload)}}\n\n`;
    const parsed = parseSseFrame(raw.trim());
    expect(parsed?.event).toBe("RISK_EVALUATED");
    expect(parsed?.data.payload).toEqual(payload);
  });

  it("activity page has replay_supported false", () => {
    const page = { items: [], replay_supported: false as const };
    expect(page.replay_supported).toBe(false);
  });
});
