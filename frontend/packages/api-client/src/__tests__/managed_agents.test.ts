import { describe, it, expect, vi } from "vitest";
import { createApiClient, ApiError } from "../client";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("managed-agent client", () => {
  it("targets the real managed routes with the right verbs", async () => {
    const fetchImpl = vi.fn(async () => json(200, { agents: [] }));
    const c = createApiClient({ baseUrl: "http://x", fetchImpl: fetchImpl as unknown as typeof fetch });
    await c.listManagedAgents(true);
    await c.updateManagedAgent("a b", { model: "m" });
    await c.enableManagedAgent("a");
    await c.disableManagedAgent("a");
    await c.duplicateManagedAgent("a", "Copy");
    await c.deleteManagedAgent("a");
    await c.deleteManagedAgent("a", { hard: true, confirm: true });
    const calls = (fetchImpl.mock.calls as unknown as [string, RequestInit][]).map(([u, i]) => `${i.method} ${u}`);
    expect(calls).toEqual([
      "GET http://x/v1/agents/managed?include_archived=true",
      "PATCH http://x/v1/agents/managed/a%20b",
      "POST http://x/v1/agents/managed/a/enable",
      "POST http://x/v1/agents/managed/a/disable",
      "POST http://x/v1/agents/managed/a/duplicate",
      "DELETE http://x/v1/agents/managed/a",
      "DELETE http://x/v1/agents/managed/a?hard=true&confirm=true",
    ]);
  });

  it("surfaces the server's FastAPI detail as the error message", async () => {
    const fetchImpl = async () => json(422, { detail: "Cannot hard-delete 'X': run history exists; archive instead" });
    const c = createApiClient({ baseUrl: "http://x", fetchImpl: fetchImpl as unknown as typeof fetch });
    const err = await c.deleteManagedAgent("a", { hard: true, confirm: true }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).message).toContain("run history exists");
  });

  it("exposes no execution-shaped method", () => {
    const c = createApiClient({ baseUrl: "http://x" });
    const managed = Object.keys(c).filter((k) => /ManagedAgent/.test(k));
    expect(managed.length).toBeGreaterThan(0);
    for (const k of managed) {
      expect(k).not.toMatch(/order|token|broker|portfolio|authorize|live|execute|place|submit/i);
    }
    expect(managed.sort()).toEqual(
      [
        "createManagedAgent",
        "deleteManagedAgent",
        "disableManagedAgent",
        "duplicateManagedAgent",
        "enableManagedAgent",
        "getManagedAgent",
        "getManagedAgentSchema",
        "listManagedAgentRuns",
        "listManagedAgentVersions",
        "listManagedAgents",
        "updateManagedAgent",
      ].sort(),
    );
  });
});
