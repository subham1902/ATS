"use client";

import React, { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ManagedAgentDetail } from "../../../../components/managed/ManagedAgentDetail";
import { getApiClient } from "../../../../lib/api";

export default function ManagedAgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const api = useMemo(() => getApiClient(), []);
  const router = useRouter();
  return <ManagedAgentDetail api={api} agentId={id} onNavigate={(href) => router.push(href)} />;
}
