import { createApiClient } from "@ats/api-client";

let client: ReturnType<typeof createApiClient> | null = null;

export function getApiClient() {
  const envUrl = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_BASE_URL : undefined;
  const baseUrl = envUrl && envUrl.trim().length > 0 ? envUrl : "http://127.0.0.1:8000";
  client ??= createApiClient({ baseUrl });
  return client;
}
