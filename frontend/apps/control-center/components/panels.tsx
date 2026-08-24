"use client";
import { Card, EmptyState, DetailField, Badge, SystemStateBadge } from "@ats/ui";
import { ErrorEnvelopeView } from "@ats/ui";
import type {
  SystemReadModel,
  PolicyReadModel,
  CampaignReadModel,
  CandidateReadModel,
  GovernanceContextReadModel,
  RiskDecisionReadModel,
  AdvisoryReadModel,
  AutonomyTokenReadModel,
  HealthReadModel,
  ErrorEnvelope,
  ActivityReadModel,
} from "@ats/api-client";

export function SystemPanel({
  system,
  healthLive,
  healthReady,
  error,
}: {
  system: SystemReadModel | null;
  healthLive: HealthReadModel | null;
  healthReady: HealthReadModel | null;
  error: ErrorEnvelope | null;
}) {
  if (error) return <Card title="System State"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!system) return <Card title="System State"><EmptyState message="No system state available" hint="Control plane not attached — backend returns no system snapshot." /></Card>;
  return (
    <Card title="System State">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <SystemStateBadge state={system.system_state} />
          <Badge tone={system.halted ? "danger" : "neutral"}>{system.halted ? "HALTED" : system.reconciliation_active ? "RECONCILING" : "operational"}</Badge>
          <Badge tone={system.readiness === "READY" ? "success" : system.readiness === "DEGRADED" ? "warn" : "unknown"}>readiness {system.readiness}</Badge>
          <Badge tone="neutral">loss {system.loss_state}</Badge>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
          <DetailField label="Authority" value={system.authority_mode} />
          <DetailField label="Version" value={String(system.system_state_version)} />
          <DetailField label="Active policy" value={system.active_policy_id ?? "—"} mono />
          <DetailField label="Active campaign" value={system.active_campaign_id ?? "—"} mono />
          <DetailField label="Last state at" value={system.last_state_at} />
          <DetailField label="Last event at" value={system.last_event_at ?? "—"} />
        </div>
        {system.degradation_indicators.length > 0 ? (
          <div role="status" style={{ fontSize: 12, color: "#92400e", background: "#fef3c7", border: "1px solid #fcd34d", padding: 8, borderRadius: 8 }}>
            Degradation: {system.degradation_indicators.join(", ")}
          </div>
        ) : null}
        <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#6b7280" }}>
          <span>health/live: {healthLive ? `${healthLive.status} ${healthLive.ready ? "✓" : "✗"}` : "—"}</span>
          <span>health/ready: {healthReady ? `${healthReady.status} ${healthReady.ready ? "✓" : "✗"}` : "—"}</span>
        </div>
      </div>
    </Card>
  );
}

export function PolicyPanel({ policy, error }: { policy: PolicyReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="Active Policy"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!policy) return <Card title="Active Policy"><EmptyState message="No active policy" hint="No VALIDATED→ACTIVE policy is currently bound." /></Card>;
  return (
    <Card title="Active Policy">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Policy" value={policy.policy_id} mono />
        <DetailField label="Version" value={String(policy.policy_version)} />
        <DetailField label="Status" value={policy.lifecycle_status} />
        <DetailField label="Autonomy" value={policy.autonomy_level} />
        <DetailField label="Owner" value={policy.owner_subject} mono />
        <DetailField label="Timeframe" value={policy.timeframe} />
        <DetailField label="Event" value={policy.event_definition_id} />
        <DetailField label="Horizon bars" value={String(policy.forecast_horizon_bars)} />
        <DetailField label="Confidence ≥" value={policy.confidence_threshold} />
        <DetailField label="Universe" value={policy.universe.join(", ") || "—"} />
      </div>
    </Card>
  );
}

export function CampaignPanel({ campaign, error }: { campaign: CampaignReadModel | null; error: ErrorEnvelope | null }) {
  if (error && error.code !== "RESOURCE_NOT_FOUND") return <Card title="Campaign"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!campaign) return <Card title="Campaign"><EmptyState message="No active campaign" hint="Runtime campaigns not yet instantiated. System may be awaiting policy binding." /></Card>;
  return (
    <Card title="Campaign">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Campaign" value={campaign.campaign_id} mono />
        <DetailField label="Name" value={campaign.name} />
        <DetailField label="Status" value={campaign.status} />
        <DetailField label="Scope" value={campaign.scope} />
        <DetailField label="Mode" value={campaign.strategy_execution_mode} />
        <DetailField label="Budget" value={campaign.capital_budget} />
        <DetailField label="Max trades" value={String(campaign.max_trades)} />
        <DetailField label="Max concurrent" value={String(campaign.max_concurrent_positions)} />
      </div>
    </Card>
  );
}

export function CandidatePanel({ candidate, error }: { candidate: CandidateReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="Candidate"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!candidate) return <Card title="Candidate"><EmptyState message="No candidates available" hint="Intelligence packages not yet emitting candidates." /></Card>;
  return (
    <Card title="Candidate">
      <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12, margin: 0 }}>
        <DetailField label="Candidate" value={candidate.candidate_id} mono />
        <DetailField label="Status" value={candidate.status} />
        <DetailField label="Instrument" value={candidate.instrument_id} />
        <DetailField label="p(calibrated)" value={candidate.calibrated_probability} />
        <DetailField label="Edge R" value={String(candidate.expected_net_edge_r)} />
        <DetailField label="Reward/risk" value={candidate.expected_reward_risk} />
        <DetailField label="Risk decision" value={candidate.risk_decision_id ?? "—"} mono />
        <DetailField label="Advisory" value={candidate.advisory_id ?? "—"} mono />
      </dl>
    </Card>
  );
}

export function GovernancePanel({ ctx, error }: { ctx: GovernanceContextReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="GovernanceContext"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!ctx) return <Card title="GovernanceContext"><EmptyState message="No governance contexts yet" hint="Contexts appear when risk/supervisor paths materialize." /></Card>;
  return (
    <Card title="GovernanceContext">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Context" value={ctx.governance_context_id} mono />
        <DetailField label="Action" value={ctx.action_kind} />
        <DetailField label="Risk direction" value={ctx.risk_direction} />
        <DetailField label="System state" value={`${ctx.system_state} v${ctx.system_state_version}`} />
        <DetailField label="Authority" value={ctx.authority_scope} />
        <DetailField label="Data quality" value={ctx.data_quality_state} />
        <DetailField label="Freshness ms" value={String(ctx.data_freshness_ms)} />
      </div>
    </Card>
  );
}

export function RiskPanel({ decision, error }: { decision: RiskDecisionReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="RiskDecision"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!decision) return <Card title="RiskDecision"><EmptyState message="No risk decisions yet" hint="Risk evaluates candidates when they appear." /></Card>;
  return (
    <Card title="RiskDecision">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Decision" value={decision.decision} />
        <DetailField label="Loss state" value={decision.loss_state} />
        <DetailField label="Reason codes" value={decision.reason_codes.join(", ") || "—"} />
        <DetailField label="Snapshot seq" value={String(decision.snapshot_sequence)} />
      </div>
    </Card>
  );
}

export function AdvisoryPanel({ advisory, error }: { advisory: AdvisoryReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="SupervisorAdvisory"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!advisory) return <Card title="SupervisorAdvisory"><EmptyState message="No advisories yet" hint="Supervisor emits advisories for risk-evaluated candidates." /></Card>;
  return (
    <Card title="SupervisorAdvisory">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Advisory" value={advisory.advisory_id} mono />
        <DetailField label="Recommendation" value={advisory.recommendation} />
        <DetailField label="Model" value={`${advisory.model_id}@${advisory.model_version}`} />
        <DetailField label="Latency ms" value={String(advisory.latency_ms)} />
        <DetailField label="Reason codes" value={advisory.reason_codes.join(", ") || "—"} />
        <DetailField label="Uncertainty" value={advisory.uncertainty_flags.join(", ") || "—"} />
      </div>
    </Card>
  );
}

export function TokenPanel({ token, error }: { token: AutonomyTokenReadModel | null; error: ErrorEnvelope | null }) {
  if (error) return <Card title="Autonomy Token (A2_PAPER)"><ErrorEnvelopeView envelope={error} /></Card>;
  if (!token) return <Card title="Autonomy Token (A2_PAPER)"><EmptyState message="No autonomy tokens yet" hint="Tokens are issued for ALLOW + APPROVE paths." /></Card>;
  return (
    <Card title="Autonomy Token (A2_PAPER)">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 12 }}>
        <DetailField label="Token" value={token.token_id} mono />
        <DetailField label="State" value={token.state} />
        <DetailField label="Scope" value={token.scope} />
        <DetailField label="Candidate" value={token.candidate_id} mono />
        <DetailField label="Issued at" value={token.issued_at} />
        <DetailField label="Expires at" value={token.expires_at} />
        <DetailField label="Consumed at" value={token.consumed_at ?? "—"} />
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: "#6b7280" }}>Safe view only — nonce/payload hash never exposed.</div>
    </Card>
  );
}

export function ActivityPanel({ items, error }: { items: ActivityReadModel[]; error: ErrorEnvelope | null }) {
  if (error) return <Card title="Activity"><ErrorEnvelopeView envelope={error} /></Card>;
  if (items.length === 0) return <Card title="Activity"><EmptyState message="No runtime activity yet" hint="Activity appears as governed events flow through the system. Replay not supported." /></Card>;
  return (
    <Card title="Activity">
      <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>Replay unsupported — stream is forward-only.</p>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((a) => (
          <li key={a.activity_id} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 10, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <strong>{a.event_kind}</strong>
              <span style={{ color: "#6b7280", fontSize: 11 }}>{new Date(a.occurred_at).toLocaleString()}</span>
            </div>
            <div style={{ color: "#374151", marginTop: 2 }}>{a.summary}</div>
            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4, fontFamily: "monospace" }}>corr {a.correlation_id.slice(0, 8)} · trace {a.trace_id ?? "—"}</div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
