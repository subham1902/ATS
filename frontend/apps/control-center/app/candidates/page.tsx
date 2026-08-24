"use client";
import { Lookup } from "../../components/Lookup";
import { CandidatePanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { CandidateReadModel } from "@ats/api-client";

export default function CandidatesPage() {
  return (
    <Lookup
      title="Candidate"
      placeholder="candidate UUID"
      emptyMessage="No candidates available — enter an ID to fetch, or wait for intelligence packages to emit candidates."
      fetcher={(id) => getApiClient().getCandidate(id)}
      render={(data) => <CandidatePanel candidate={data as CandidateReadModel} error={null} />}
    />
  );
}
