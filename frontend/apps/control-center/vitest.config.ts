import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@ats/api-client": new URL("../../packages/api-client/src/index.ts", import.meta.url).pathname,
      "@ats/ui": new URL("../../packages/ui/src/index.ts", import.meta.url).pathname,
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
