"use client";
import { Lookup } from "../../components/Lookup";
import { PolicyPanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { PolicyReadModel } from "@ats/api-client";

export default function PoliciesPage() {
  return (
    <Lookup
      title="Policy"
      placeholder="policy UUID"
      emptyMessage="Enter a policy ID to view its read-only details. Active policy is visible on the dashboard."
      fetcher={(id) => getApiClient().getPolicy(id)}
      render={(data) => <PolicyPanel policy={data as PolicyReadModel} error={null} />}
    />
  );
}
