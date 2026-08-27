import { createApiClient } from "@ats/api-client";

let client: ReturnType<typeof createApiClient> | null = null;

export function getApiClient() {
  client ??= createApiClient({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "" });
  return client;
}
