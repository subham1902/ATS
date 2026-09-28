import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/out/**",
      "**/coverage/**",
      "**/*.d.ts",
      "frontend/**/next-env.d.ts",
      "tools/**",
      "worktrees/**",
      "toolchains/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["frontend/**/*.{ts,tsx,js,mjs}"],
    plugins: {
      "react-hooks": reactHooks,
    },
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    settings: {
      react: {
        version: "detect",
      },
    },
    rules: {
      // Declared explicitly rather than spread from the plugin's
      // `configs.recommended`: in v6 that export is a flat-config *array*, so
      // reading `.rules` off it is undefined and the rules silently vanish.
      // The highest-value rule here catches conditional and early-return hook
      // calls -- the defect class that breaks React's hook-ordering contract.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" },
      ],
      // Test files legitimately reach for `any` around third-party fixtures.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    files: ["scripts/**/*.{js,mjs,ts}"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  {
    files: [
      "frontend/**/__tests__/**",
      "frontend/**/*.test.ts",
      "frontend/**/*.test.tsx",
      "frontend/**/*.spec.ts",
      "frontend/**/*.spec.tsx",
      "frontend/**/vitest.setup.ts",
      "frontend/**/vitest.config.ts",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
    },
  },
);
