"use client";
import { useEffect, useState } from "react";
import { ActivityPanel } from "../../components/panels";
import { getApiClient } from "../../lib/api";
import { isApiError } from "@ats/api-client";
import type { ActivityReadModel, ErrorEnvelope } from "@ats/api-client";

export default function ActivityPage() {
  const [items, setItems] = useState<ActivityReadModel[]>([]);
  const [error, setError] = useState<ErrorEnvelope | null>(null);
  useEffect(() => {
    getApiClient()
      .getActivity()
      .then((p) => setItems(p.items))
      .catch((e) => {
        if (isApiError(e)) setError(e.envelope);
        else setError({ code: "CLIENT_ERROR", message: String(e), correlation_id: "n/a", details: [] });
      });
  }, []);
  return <ActivityPanel items={items} error={error} />;
}
