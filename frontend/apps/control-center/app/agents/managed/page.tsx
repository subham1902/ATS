"use client";

import React, { useMemo } from "react";
import { useRouter } from "next/navigation";
import { ManagedAgentsView } from "../../../components/managed/ManagedAgentsView";
import { ResearchTemplates } from "../../../components/managed/ResearchTemplates";
import { ResearchJobs } from "../../../components/managed/ResearchJobs";
import { getApiClient } from "../../../lib/api";

export default function ManagedAgentsPage() {
  const api = useMemo(() => getApiClient(), []);
  const router = useRouter();
  return (
    <>
      <ManagedAgentsView api={api} onCreated={(a) => router.push(`/agents/managed/${a.agent_id}`)} />
      <ResearchTemplates />
      <ResearchJobs />
    </>
  );
}
