"use client";
import { Lookup } from "../../components/Lookup";
import { GovernancePanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { GovernanceContextReadModel } from "@ats/api-client";

export default function GovernancePage() {
  return (
    <Lookup
      title="GovernanceContext"
      placeholder="governance context UUID"
      emptyMessage="No governance contexts yet — enter an ID to inspect."
      fetcher={(id) => getApiClient().getGovernanceContext(id)}
      render={(data) => <GovernancePanel ctx={data as GovernanceContextReadModel} error={null} />}
    />
  );
}
