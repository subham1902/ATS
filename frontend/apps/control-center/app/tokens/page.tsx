"use client";
import { Lookup } from "../../components/Lookup";
import { TokenPanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import type { AutonomyTokenReadModel } from "@ats/api-client";

export default function TokensPage() {
  return (
    <Lookup
      title="Autonomy Token (A2_PAPER safe view)"
      placeholder="token UUID"
      emptyMessage="No autonomy tokens yet — safe view never exposes nonce or payload hash."
      fetcher={(id) => getApiClient().getAutonomyToken(id)}
      render={(data) => <TokenPanel token={data as AutonomyTokenReadModel} error={null} />}
    />
  );
}
