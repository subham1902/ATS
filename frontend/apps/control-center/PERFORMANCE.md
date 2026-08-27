# Control Center performance audit

## Changes in this modernization

- One shell-owned `/v1/stream` connection replaces page-level duplicate streams for global state.
- One stable API client is reused for the lifetime of the browser session.
- Runtime, system, pipeline, Harness, and activity reads are fetched concurrently.
- Material SSE bursts are batched per network read and retained in a bounded 200-event window.
- Runtime refreshes triggered by stream events are debounced to one request group per 180 ms burst.
- Overview, positions, risk, Harness, and activity consume the shared operator snapshot instead of polling independently.
- Activity and visible table histories are bounded; dense tables scroll locally.
- App Router links provide production prefetching and route-level loading/error boundaries keep the shell interactive.

## Build evidence

Measured on 2026-08-27 with Node 24.19.0 and pnpm 11.9.0:

- Production build compiled successfully.
- All 17 application routes were statically generated.
- 24 emitted static JavaScript chunks totalled 803,490 bytes on disk; the largest was 229,142 bytes.
- The eight charter acceptance routes returned HTTP 200 from the production server.

Navigation timing, first contentful paint, live render latency, and table render latency require a connected browser trace. No synthetic values are asserted here.
