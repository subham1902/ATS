import { createApiClient } from "@ats/api-client";

export function getApiClient() {
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  return createApiClient({
    baseUrl: envUrl || (typeof window !== "undefined" ? "" : "http://127.0.0.1:8000"),
  });
}
