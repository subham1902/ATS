"use client";
import { Lookup } from "../../components/Lookup";
import { AdvisoryPanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { AdvisoryReadModel } from "@ats/api-client";

export default function AdvisoriesPage() {
  return (
    <Lookup
      title="SupervisorAdvisory"
      placeholder="advisory UUID"
      emptyMessage="No advisories yet — enter an ID to inspect."
      fetcher={(id) => getApiClient().getAdvisory(id)}
      render={(data) => <AdvisoryPanel advisory={data as AdvisoryReadModel} error={null} />}
    />
  );
}
