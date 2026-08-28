import type {
  ActivityPage,
  AgentChatAnswer,
  AgentChatRequest,
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
  RuntimeCommandRequest,
  RuntimeCommandResult,
  OperatorOrderIntent,
  OperatorOrderResult,
  RuntimeStatusReadModel,
  SystemReadModel,
} from "./types";
import { ROUTES } from "./types";
import type { OperatorIntelligenceSnapshot } from "./operator-intelligence";

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
  if (options?.baseUrl && options.baseUrl.trim().length > 0) {
    return options.baseUrl.replace(/\/$/, "");
  }
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL && process.env.NEXT_PUBLIC_API_BASE_URL.trim().length > 0) {
    return (process.env.NEXT_PUBLIC_API_BASE_URL as string).replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

async function parseError(res: Response): Promise<ErrorEnvelope | null> {
  try {
    const j = (await res.json()) as ErrorEnvelope;
    if (j && typeof j.code === "string" && typeof j.message === "string") return j;
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

export function createApiClient(options?: ClientOptions) {
  const opts = options;
  return {
    getHealthLive: () => request<HealthReadModel>(ROUTES.healthLive, { method: "GET" }, opts),
    getHealthReady: () => request<HealthReadModel>(ROUTES.healthReady, { method: "GET" }, opts),
    getSystem: () => request<SystemReadModel>(ROUTES.system, { method: "GET" }, opts),
    getActivePolicy: () => request<PolicyReadModel>(ROUTES.policiesActive, { method: "GET" }, opts),
    getPolicy: (id: string) => request<PolicyReadModel>(ROUTES.policyById(id), { method: "GET" }, opts),
    validatePolicy: (body: PolicyValidationRequest) =>
      request<PolicyValidationReadModel>(ROUTES.policyValidate, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, opts),
    getCampaign: (id: string) => request<CampaignReadModel>(ROUTES.campaignById(id), { method: "GET" }, opts),
    getCandidate: (id: string) => request<CandidateReadModel>(ROUTES.candidateById(id), { method: "GET" }, opts),
    getGovernanceContext: (id: string) =>
      request<GovernanceContextReadModel>(ROUTES.governanceById(id), { method: "GET" }, opts),
    getRiskDecision: (id: string) => request<RiskDecisionReadModel>(ROUTES.riskDecisionById(id), { method: "GET" }, opts),
    getAdvisory: (id: string) => request<AdvisoryReadModel>(ROUTES.advisoryById(id), { method: "GET" }, opts),
    getAutonomyToken: (id: string) =>
      request<AutonomyTokenReadModel>(ROUTES.autonomyTokenById(id), { method: "GET" }, opts),
    getActivity: () => request<ActivityPage>(ROUTES.activity, { method: "GET" }, opts),
    agentChat: (body: AgentChatRequest) =>
      request<AgentChatAnswer>(ROUTES.agentChat, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, opts),
    getRuntimeStatus: () => request<RuntimeStatusReadModel>(ROUTES.runtimeStatus, { method: "GET" }, opts),
    runtimeCommand: (body: RuntimeCommandRequest) =>
      request<RuntimeCommandResult>(ROUTES.runtimeCommand, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, opts),
    submitOperatorOrder: (body: OperatorOrderIntent) =>
      request<OperatorOrderResult>(ROUTES.operatorOrders, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, opts),
    getOperatorIntelligence: () =>
      request<OperatorIntelligenceSnapshot>(ROUTES.operatorIntelligence, { method: "GET" }, opts),
    operatorIntelligenceStreamUrl: () =>
      `${resolveBaseUrl(opts)}${ROUTES.operatorIntelligenceStream}`,
    getHarnessStatus: () => request<unknown>(ROUTES.harnessStatus, { method: "GET" }, opts),
    harnessAdvisory: (body: unknown) =>
      request<unknown>(ROUTES.harnessAdvisory, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, opts),
    getPipelineCounters: () => request<unknown>(ROUTES.pipelineCounters, { method: "GET" }, opts),
    streamUrl: () => `${resolveBaseUrl(opts)}${ROUTES.stream}`,
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
