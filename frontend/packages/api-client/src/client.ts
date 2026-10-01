import type {
  ActivityPage,
  AdvisoryReadModel,
  AutonomyTokenReadModel,
  CampaignReadModel,
  CandidateReadModel,
  ErrorEnvelope,
  GovernanceContextReadModel,
  HealthReadModel,
  PolicyReadModel,
  PolicyValidationReadModel,
  PolicyValidationRequest,
  RiskDecisionReadModel,
  SystemReadModel,
  FeedHealthView,
  MarketQuoteView,
  MarketSnapshotView,
  CandleSeriesView,
  RuntimeStatusReadModel,
  StrategyRegistryOverview,
  LeaderboardResponse,
  StrategyRegistryEntry,
  StrategyPerformanceReport,
  ManagedAgent,
  ManagedAgentConfigVersion,
  ManagedAgentDeleteResult,
  ManagedAgentRun,
  ManagedAgentSchema,
  CreateManagedAgentRequest,
  UpdateManagedAgentRequest,
} from "./types";
import { ROUTES } from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly envelope: ErrorEnvelope | null,
    public readonly correlationId: string | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  correlationId?: string;
}

function resolveBaseUrl(options?: ClientOptions): string {
  if (options?.baseUrl) return options.baseUrl.replace(/\/$/, "");
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return (process.env.NEXT_PUBLIC_API_BASE_URL as string).replace(/\/$/, "");
  }
  return "";
}

async function parseError(res: Response): Promise<ErrorEnvelope | null> {
  try {
    const j = (await res.json()) as ErrorEnvelope & { detail?: unknown };
    if (j && typeof j.code === "string" && typeof j.message === "string") return j;
    // FastAPI HTTPException bodies are {detail: "..."}; keep the reason.
    if (j && typeof j.detail === "string") {
      return { code: `HTTP_${res.status}`, message: j.detail, correlation_id: "", details: [] };
    }
    return null;
  } catch {
    return null;
  }
}

async function request<T>(path: string, init: RequestInit, opts?: ClientOptions): Promise<T> {
  const base = resolveBaseUrl(opts);
  const url = `${base}${path}`;
  const fetchFn = opts?.fetchImpl ?? fetch;
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (opts?.correlationId) headers["x-correlation-id"] = opts.correlationId;
  const res = await fetchFn(url, { ...init, headers });
  if (!res.ok) {
    const envelope = await parseError(res);
    const corr = envelope?.correlation_id ?? res.headers.get("x-correlation-id") ?? null;
    throw new ApiError(res.status, envelope, corr, envelope?.message ?? `Request failed ${res.status} ${path}`);
  }
  // 204 / empty
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export function createApiClient(options?: ClientOptions) {
  const opts = options;
  return {
    getHealthLive: () => request<HealthReadModel>(ROUTES.healthLive, { method: "GET" }, opts),
    getHealthReady: () => request<HealthReadModel>(ROUTES.healthReady, { method: "GET" }, opts),
    getSystem: () => request<SystemReadModel>(ROUTES.system, { method: "GET" }, opts),
    getActivePolicy: () => request<PolicyReadModel>(ROUTES.policiesActive, { method: "GET" }, opts),
    getPolicy: (id: string) => request<PolicyReadModel>(ROUTES.policyById(id), { method: "GET" }, opts),
    validatePolicy: (body: PolicyValidationRequest) =>
      request<PolicyValidationReadModel>(
        ROUTES.policyValidate,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
        opts,
      ),
    getCampaign: (id: string) => request<CampaignReadModel>(ROUTES.campaignById(id), { method: "GET" }, opts),
    getCandidate: (id: string) => request<CandidateReadModel>(ROUTES.candidateById(id), { method: "GET" }, opts),
    getGovernanceContext: (id: string) =>
      request<GovernanceContextReadModel>(ROUTES.governanceById(id), { method: "GET" }, opts),
    getRiskDecision: (id: string) =>
      request<RiskDecisionReadModel>(ROUTES.riskDecisionById(id), { method: "GET" }, opts),
    getAdvisory: (id: string) => request<AdvisoryReadModel>(ROUTES.advisoryById(id), { method: "GET" }, opts),
    getAutonomyToken: (id: string) =>
      request<AutonomyTokenReadModel>(ROUTES.autonomyTokenById(id), { method: "GET" }, opts),
    getActivity: () => request<ActivityPage>(ROUTES.activity, { method: "GET" }, opts),
    streamUrl: () => `${resolveBaseUrl(opts)}${ROUTES.stream}`,
    getMarketHealth: () => request<FeedHealthView>(ROUTES.marketHealth, { method: "GET" }, opts),
    getMarketQuote: (instrument?: string) =>
      request<MarketQuoteView>(ROUTES.marketQuote(instrument), { method: "GET" }, opts),
    getMarketSnapshot: (instrument?: string) =>
      request<MarketSnapshotView>(ROUTES.marketSnapshot(instrument), { method: "GET" }, opts),
    getMarketCandles: (interval: string = "5m", instrument?: string, limit?: number) =>
      request<CandleSeriesView>(ROUTES.marketCandles(interval, instrument, limit), { method: "GET" }, opts),
    marketStreamUrl: (instrument?: string) => `${resolveBaseUrl(opts)}${ROUTES.marketStream(instrument)}`,
    getRuntimeStatus: () => request<RuntimeStatusReadModel>(ROUTES.runtimeStatus, { method: "GET" }, opts),
    // Strategy Registry & Leaderboard
    getStrategyRegistry: () => request<StrategyRegistryOverview>(ROUTES.strategyRegistry, { method: "GET" }, opts),
    getStrategyLeaderboard: (timeframe?: string, context?: string, badge?: string) =>
      request<LeaderboardResponse>(ROUTES.strategyLeaderboard(timeframe, context, badge), { method: "GET" }, opts),
    getStrategy: (id: string) => request<StrategyRegistryEntry>(ROUTES.strategyById(id), { method: "GET" }, opts),
    getStrategyReport: (id: string) =>
      request<StrategyPerformanceReport>(ROUTES.strategyReport(id), { method: "GET" }, opts),
    // Managed agents (proposal-only). There is intentionally no method that
    // executes, authorizes, or mutates capital: the domain has none.
    getManagedAgentSchema: () =>
      request<ManagedAgentSchema>(ROUTES.managedAgentSchema, { method: "GET" }, opts),
    listManagedAgents: (includeArchived = false) =>
      request<{ agents: ManagedAgent[] }>(ROUTES.managedAgents(includeArchived), { method: "GET" }, opts),
    getManagedAgent: (id: string) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgentById(id), { method: "GET" }, opts),
    createManagedAgent: (body: CreateManagedAgentRequest) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgents(), jsonInit("POST", body), opts),
    updateManagedAgent: (id: string, body: UpdateManagedAgentRequest) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgentById(id), jsonInit("PATCH", body), opts),
    enableManagedAgent: (id: string) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgentEnable(id), { method: "POST" }, opts),
    disableManagedAgent: (id: string) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgentDisable(id), { method: "POST" }, opts),
    duplicateManagedAgent: (id: string, name: string) =>
      request<{ agent: ManagedAgent }>(ROUTES.managedAgentDuplicate(id), jsonInit("POST", { name }), opts),
    /** Archives by default. Hard delete needs both flags and is still refused by the server if history exists. */
    deleteManagedAgent: (id: string, opts2?: { hard?: boolean; confirm?: boolean }) =>
      request<ManagedAgentDeleteResult>(ROUTES.managedAgentDelete(id, opts2), { method: "DELETE" }, opts),
    listManagedAgentVersions: (id: string) =>
      request<{ versions: ManagedAgentConfigVersion[] }>(ROUTES.managedAgentVersions(id), { method: "GET" }, opts),
    listManagedAgentRuns: (id: string) =>
      request<{ runs: ManagedAgentRun[] }>(ROUTES.managedAgentRuns(id), { method: "GET" }, opts),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
