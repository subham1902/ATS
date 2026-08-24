"use client";
import { Lookup } from "../../components/Lookup";
import { RiskPanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { RiskDecisionReadModel } from "@ats/api-client";

export default function RiskPage() {
  return (
    <Lookup
      title="RiskDecision"
      placeholder="risk decision UUID"
      emptyMessage="No risk decisions yet — enter an ID to inspect."
      fetcher={(id) => getApiClient().getRiskDecision(id)}
      render={(data) => <RiskPanel decision={data as RiskDecisionReadModel} error={null} />}
    />
  );
}
