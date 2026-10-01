import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { ApiError } from "@ats/api-client";
import type { ManagedAgent, ManagedAgentConfigVersion, ManagedAgentRun, ManagedAgentSchema } from "@ats/api-client";
import { ManagedAgentsView } from "../components/managed/ManagedAgentsView";
import { ManagedAgentWizard, WIZARD_STEPS } from "../components/managed/ManagedAgentWizard";
import { ManagedAgentDetail } from "../components/managed/ManagedAgentDetail";
import type { ManagedApi } from "../components/managed/shared";

vi.mock("next/link", () => ({
  default: (props: unknown) => {
    const { children, href } = props as { children: unknown; href: string };
    return <a href={href}>{children as string}</a>;
  },
}));

const SCHEMA: ManagedAgentSchema = {
  agent_types: ["RESEARCH", "ANALYSIS"],
  statuses: ["DISABLED", "IDLE", "RUNNING", "ERROR", "ARCHIVED"],
  capabilities: ["READ_MARKET_DATA", "RUN_RESEARCH", "GENERATE_REPORT"],
  data_scopes: ["MARKET_DATA", "DATASETS"],
  research_scopes: ["REGIME", "COSTS"],
  limits: { timeout_s: { min_exclusive: 0, max: 86400 }, max_concurrency: { min: 1, max: 32 } },
};

function agent(over: Partial<ManagedAgent> = {}): ManagedAgent {
  return {
    agent_id: "a1",
    name: "Regime Researcher",
    description: "Regime research",
    agent_type: "RESEARCH",
    provider: "acme",
    model: "acme-large",
    system_instructions: "Analyze only.",
    capabilities: ["READ_MARKET_DATA", "RUN_RESEARCH"],
    data_scopes: ["MARKET_DATA"],
    research_scopes: ["REGIME"],
    timeout_s: 300,
    max_concurrency: 2,
    credential_ref: "ACME_API_KEY",
    enabled: false,
    status: "DISABLED",
    current_config_version: 1,
    created_at: "2026-09-30T10:00:00Z",
    updated_at: "2026-09-30T10:00:00Z",
    archived_at: null,
    last_run_at: null,
    last_error: null,
    ...over,
  };
}

function makeApi(over: Partial<Record<keyof ManagedApi, unknown>> = {}): ManagedApi {
  const base = {
    getManagedAgentSchema: vi.fn(async () => SCHEMA),
    listManagedAgents: vi.fn(async () => ({ agents: [agent()] })),
    getManagedAgent: vi.fn(async () => ({ agent: agent() })),
    createManagedAgent: vi.fn(async (b: { name: string }) => ({ agent: agent({ name: b.name }) })),
    updateManagedAgent: vi.fn(async () => ({ agent: agent({ current_config_version: 2 }) })),
    enableManagedAgent: vi.fn(async () => ({ agent: agent({ enabled: true, status: "IDLE" }) })),
    disableManagedAgent: vi.fn(async () => ({ agent: agent() })),
    duplicateManagedAgent: vi.fn(async (_id: string, name: string) => ({ agent: agent({ agent_id: "a2", name }) })),
    deleteManagedAgent: vi.fn(async () => ({
      mode: "archived",
      agent: agent({ archived_at: "2026-10-01T00:00:00Z" }),
    })),
    listManagedAgentVersions: vi.fn(async (): Promise<{ versions: ManagedAgentConfigVersion[] }> => ({
      versions: [
        { agent_id: "a1", version: 1, snapshot: {} as never, reason: "created", created_at: "2026-09-30T10:00:00Z" },
      ],
    })),
    listManagedAgentRuns: vi.fn(async (): Promise<{ runs: ManagedAgentRun[] }> => ({ runs: [] })),
  };
  return { ...base, ...over } as unknown as ManagedApi;
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));
const type = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("managed agent list", () => {
  it("shows agents with version, capability count and an Add Agent action", async () => {
    render(<ManagedAgentsView api={makeApi()} />);
    expect(await screen.findByText("Regime Researcher")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add Agent" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Regime Researcher" })).toHaveAttribute("href", "/agents/managed/a1");
    expect(screen.getByRole("link", { name: "Agents Playground" })).toHaveAttribute("href", "/agents");
  });

  it("shows an empty state", async () => {
    render(<ManagedAgentsView api={makeApi({ listManagedAgents: async () => ({ agents: [] }) })} />);
    expect(await screen.findByText(/No managed agents yet/)).toBeInTheDocument();
  });

  it("shows the API error", async () => {
    const api = makeApi({
      listManagedAgents: async () => {
        throw new Error("boom");
      },
    });
    render(<ManagedAgentsView api={api} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("filters by search and status, and re-queries with archived visibility", async () => {
    const api = makeApi({
      listManagedAgents: vi.fn(async (inc?: boolean) => ({
        agents: [
          agent(),
          agent({ agent_id: "a3", name: "Cost Analyst", agent_type: "ANALYSIS", status: "IDLE", enabled: true }),
          ...(inc
            ? [agent({ agent_id: "a4", name: "Old One", status: "ARCHIVED", archived_at: "2026-10-01T00:00:00Z" })]
            : []),
        ],
      })),
    });
    render(<ManagedAgentsView api={api} />);
    await screen.findByText("Cost Analyst");
    type("Search", "cost");
    expect(screen.queryByText("Regime Researcher")).not.toBeInTheDocument();
    type("Search", "");
    type("Status", "IDLE");
    expect(screen.queryByText("Regime Researcher")).not.toBeInTheDocument();
    expect(screen.getByText("Cost Analyst")).toBeInTheDocument();
    type("Status", "ALL");
    expect(screen.queryByText("Old One")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Show\s+archived/));
    expect(await screen.findByText("Old One")).toBeInTheDocument();
    expect(api.listManagedAgents).toHaveBeenLastCalledWith(true);
  });
});

async function fillThroughReview(api: ManagedApi) {
  render(<ManagedAgentWizard api={api} onCancel={() => undefined} onCreated={() => undefined} />);
  await screen.findByLabelText("Name");
  type("Name", "Alpha Scout");
  click("Next");
  type("Provider", "acme");
  type("Model", "acme-large");
  type(/Credential reference/, "ACME_API_KEY");
  click("Next");
  click("Next"); // responsibilities
  fireEvent.click(screen.getByLabelText("MARKET_DATA"));
  click("Next");
  fireEvent.click(screen.getByLabelText("REGIME"));
  click("Next");
  fireEvent.click(screen.getByLabelText("RUN_RESEARCH"));
  click("Next");
  click("Next"); // limits (defaults valid)
}

describe("add-agent wizard", () => {
  it("walks all eight steps and creates the agent with only a credential reference", async () => {
    const api = makeApi();
    await fillThroughReview(api);
    expect(
      screen.getByText(`Step ${WIZARD_STEPS.length} of ${WIZARD_STEPS.length}:`, { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/can research, analyze and propose\. It cannot authorize or execute trades/),
    ).toBeInTheDocument();
    expect(screen.getByText("DISABLED")).toBeInTheDocument();
    click("Create agent");
    await waitFor(() => expect(api.createManagedAgent).toHaveBeenCalledTimes(1));
    const body = (api.createManagedAgent as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][0] as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      name: "Alpha Scout",
      credential_ref: "ACME_API_KEY",
      capabilities: ["RUN_RESEARCH"],
      data_scopes: ["MARKET_DATA"],
      research_scopes: ["REGIME"],
    });
    // No secret-bearing or authority-bearing keys can be submitted.
    expect(Object.keys(body).filter((k) => /secret|api_key|password|token|order|broker|execute/i.test(k))).toEqual([]);
  });

  it("validates required fields before advancing", async () => {
    render(<ManagedAgentWizard api={makeApi()} onCancel={() => undefined} onCreated={() => undefined} />);
    await screen.findByLabelText("Name");
    click("Next");
    expect(screen.getByRole("alert")).toHaveTextContent(/Name is required/);
    type("Name", "Alpha");
    click("Next");
    click("Next");
    expect(screen.getByRole("alert")).toHaveTextContent(/Provider is required/);
  });

  it("rejects a secret-looking credential reference client-side", async () => {
    const api = makeApi();
    render(<ManagedAgentWizard api={api} onCancel={() => undefined} onCreated={() => undefined} />);
    await screen.findByLabelText("Name");
    type("Name", "Alpha");
    click("Next");
    type("Provider", "acme");
    type("Model", "m");
    type(/Credential reference/, "sk-live-abc123secret");
    click("Next");
    expect(screen.getByRole("alert")).toHaveTextContent(/never a secret value/);
    expect(api.createManagedAgent).not.toHaveBeenCalled();
  });

  it("requires at least one capability and bounded limits", async () => {
    render(<ManagedAgentWizard api={makeApi()} onCancel={() => undefined} onCreated={() => undefined} />);
    await screen.findByLabelText("Name");
    type("Name", "Alpha");
    click("Next");
    type("Provider", "acme");
    type("Model", "m");
    click("Next");
    click("Next");
    click("Next");
    click("Next");
    click("Next"); // capabilities, none chosen
    expect(screen.getByRole("alert")).toHaveTextContent(/at least one capability/);
  });

  it("offers only the server-supplied capabilities and no financial-authority control", async () => {
    render(<ManagedAgentWizard api={makeApi()} onCancel={() => undefined} onCreated={() => undefined} />);
    await screen.findByLabelText("Name");
    type("Name", "Alpha");
    click("Next");
    type("Provider", "acme");
    type("Model", "m");
    click("Next");
    click("Next");
    click("Next");
    click("Next");
    const group = screen.getByRole("group", { name: "Capabilities" });
    const labels = within(group)
      .getAllByRole("checkbox")
      .map((c) => c.parentElement?.textContent?.trim());
    expect(labels).toEqual(SCHEMA.capabilities);
    expect(group.textContent ?? "").not.toMatch(
      /AUTHORIZE|MINT|PLACE_ORDER|SUBMIT_ORDER|MUTATE_PORTFOLIO|LIVE_EXECUTION|BROKER_WRITE/i,
    );
  });

  it("surfaces a server rejection on create", async () => {
    const api = makeApi({
      createManagedAgent: async () => {
        throw new Error("Agent name 'Alpha Scout' is already taken");
      },
    });
    await fillThroughReview(api);
    click("Create agent");
    expect(await screen.findByRole("alert")).toHaveTextContent(/already taken/);
  });
});

describe("managed agent detail", () => {
  it("renders configuration, exact version, runs and history", async () => {
    const api = makeApi({
      getManagedAgent: async () => ({ agent: agent({ current_config_version: 3 }) }),
      listManagedAgentRuns: async () => ({
        runs: [
          {
            run_id: "r1",
            agent_id: "a1",
            config_version: 2,
            status: "COMPLETED",
            started_at: "2026-09-30T11:00:00Z",
            finished_at: null,
            error: null,
          },
        ],
      }),
      listManagedAgentVersions: async () => ({
        versions: [1, 2, 3].map((v) => ({
          agent_id: "a1",
          version: v,
          snapshot: {} as never,
          reason: v === 1 ? "created" : "edited",
          created_at: "2026-09-30T10:00:00Z",
        })),
      }),
    });
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    expect(await screen.findByRole("heading", { name: "Regime Researcher" })).toBeInTheDocument();
    expect(screen.getByText(/configuration v3/)).toBeInTheDocument();
    expect(screen.getByText(/ran under config v2/)).toBeInTheDocument();
    expect(screen.getByText(/^v1 · created/)).toBeInTheDocument();
    expect(screen.getByText(/^v3 · edited/)).toBeInTheDocument();
    expect(screen.getByText("READ_MARKET_DATA, RUN_RESEARCH")).toBeInTheDocument();
    expect(screen.getByText("ACME_API_KEY")).toBeInTheDocument();
  });

  it("enables a disabled agent and states disable semantics honestly", async () => {
    const api = makeApi();
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    click("Enable");
    await waitFor(() => expect(api.enableManagedAgent).toHaveBeenCalledWith("a1"));

    const enabled = makeApi({ getManagedAgent: async () => ({ agent: agent({ enabled: true, status: "IDLE" }) }) });
    render(<ManagedAgentDetail api={enabled} agentId="a1" />);
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Disable" }).length).toBeGreaterThan(0));
    fireEvent.click(screen.getAllByRole("button", { name: "Disable" })[0]);
    await waitFor(() => expect(enabled.disableManagedAgent).toHaveBeenCalledWith("a1"));
    expect(await screen.findByText(/not cancelled/)).toBeInTheDocument();
  });

  it("edits as a new configuration revision, sending only changed fields", async () => {
    const api = makeApi();
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).not.toBeDisabled());
    click("Edit");
    expect(screen.getByText(/creates configuration/i)).toHaveTextContent(/v2/);
    type("Model", "acme-xl");
    click("Save new version");
    await waitFor(() =>
      expect(api.updateManagedAgent).toHaveBeenCalledWith("a1", { model: "acme-xl", expected_version: 1 }),
    );
    expect(await screen.findByText(/Saved as configuration v2/)).toBeInTheDocument();
  });

  it("tells the user to reload when the server reports a stale edit, without retrying", async () => {
    const api = makeApi({
      updateManagedAgent: vi.fn(async () => {
        throw new ApiError(
          409,
          null,
          null,
          "Agent 'Regime Researcher' changed since you opened it (you have v1, current is v2); reload before saving",
        );
      }),
    });
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).not.toBeDisabled());
    click("Edit");
    type("Model", "acme-xl");
    click("Save new version");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This agent changed since you opened it. Reload before saving.",
    );
    expect(api.updateManagedAgent).toHaveBeenCalledTimes(1);
    click("Reload latest");
    await waitFor(() => expect(api.getManagedAgent).toHaveBeenCalledTimes(2));
  });

  it("duplicates into an independent, disabled agent", async () => {
    const api = makeApi();
    const onNavigate = vi.fn();
    render(<ManagedAgentDetail api={api} agentId="a1" onNavigate={onNavigate} />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    click("Duplicate");
    type("Name for the copy", "Regime Researcher B");
    click("Create copy");
    await waitFor(() => expect(api.duplicateManagedAgent).toHaveBeenCalledWith("a1", "Regime Researcher B"));
    expect(onNavigate).toHaveBeenCalledWith("/agents/managed/a2");
  });

  it("archives only after an explanatory confirmation", async () => {
    const api = makeApi();
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    click("Archive");
    expect(api.deleteManagedAgent).not.toHaveBeenCalled();
    expect(screen.getByText(/previous runs and research evidence remain/i)).toBeInTheDocument();
    click("Confirm archive");
    await waitFor(() => expect(api.deleteManagedAgent).toHaveBeenCalledWith("a1"));
    expect(await screen.findByText(/runs and configuration history remain available/)).toBeInTheDocument();
  });

  it("shows the server's reason when hard delete is refused and steers to archive", async () => {
    const api = makeApi({
      deleteManagedAgent: vi.fn(async () => {
        throw new Error("Cannot hard-delete 'Regime Researcher': run history exists; archive instead");
      }),
    });
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    const del = screen.getByRole("button", { name: "Delete permanently" });
    expect(del).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I understand this/));
    fireEvent.click(del);
    expect(await screen.findByRole("alert")).toHaveTextContent(/run history exists.*Archive instead/);
    expect(api.deleteManagedAgent).toHaveBeenCalledWith("a1", { hard: true, confirm: true });
  });

  it("offers no lifecycle mutations on an archived agent but keeps its history visible", async () => {
    const api = makeApi({
      getManagedAgent: async () => ({ agent: agent({ archived_at: "2026-10-01T00:00:00Z", status: "ARCHIVED" }) }),
    });
    render(<ManagedAgentDetail api={api} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    for (const name of ["Enable", "Disable", "Edit", "Duplicate", "Archive"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
    expect(screen.getByText(/^v1 · created/)).toBeInTheDocument();
  });

  it("shows a load error", async () => {
    const api = makeApi({
      getManagedAgent: async () => {
        throw new Error("Unknown agent 'zzz'");
      },
    });
    render(<ManagedAgentDetail api={api} agentId="zzz" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Unknown agent/);
  });
});

describe("authority boundary (UI)", () => {
  it("never renders an execution-authority control in the edit form", async () => {
    render(<ManagedAgentDetail api={makeApi()} agentId="a1" />);
    await screen.findByRole("heading", { name: "Regime Researcher" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).not.toBeDisabled());
    click("Edit");
    const controls = Array.from(document.querySelectorAll("input, select, textarea, button")).map(
      (el) => `${el.textContent ?? ""} ${(el as HTMLInputElement).value ?? ""} ${el.id}`,
    );
    expect(controls.join("\n")).not.toMatch(
      /AUTHORIZE|MINT|PLACE_ORDER|SUBMIT_ORDER|MUTATE_PORTFOLIO|LIVE_EXECUTION|BROKER_WRITE/i,
    );
  });
});
