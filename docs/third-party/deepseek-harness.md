# DeepSeek Harness runtime pin

- Source: `https://github.com/deepseek-ai/deepseek-harness`
- Tag: `dsh-v0.1.1-rc.2`
- Commit: `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e`
- Package: `@deepseek-ai/dsh@0.1.1-rc.2`
- License: MIT, Copyright (c) 2026 DeepSeek
- Protocol: Agent Client Protocol over NDJSON stdio
- Runtime: isolated local process, Node `^22.19.0 || >=24.0.0`

The ATS adapter targets the automation-only ACP server. The upstream developer
preview currently supports fresh sessions, prompts and cancellation, but not
durable session load/resume. ATS therefore resumes only adapter-owned sessions
while the same process is alive and reports durable resume as unsupported.

The third-party source is not vendored into ATS. Operators provide a checkout
at the exact commit and launch its `demo:acp` composition under the adapter's
read-only permission mode. DeepSeek Harness and its transitive third-party
notices remain governed by the upstream `LICENSE` and
`THIRD_PARTY_NOTICES.md` at the pinned commit.
