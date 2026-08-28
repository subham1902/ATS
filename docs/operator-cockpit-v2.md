# ATS Operator Cockpit V2

## Activation and screen hierarchy

V2 is gated by `NEXT_PUBLIC_ATS_OPERATOR_COCKPIT_V2=1`. Without the flag the verified legacy Overview remains active. The primary navigation is reduced to Overview, Markets, Trade Desk, Positions, Opportunities, Agents, Research, Session Review, and System.

For PAPER runtime restart continuity, set `ATS_A2_RUNTIME_CHECKPOINT_PATH` to a writable local data file. This checkpoint restores canonical monitoring state (including position origin and exit-management mode); it cannot authorize execution or replay an order/fill.

The desktop cockpit uses a persistent safety/capital strip, watchlist at left, event-backed chart and C0 state in the center, authority rail at right, and canonical positions plus material activity below. At narrow widths it becomes a monitoring-first stacked view.

## Truth and authority boundaries

Financial state comes only from the runtime status read model. Chart candles require complete OHLC fields in typed SSE events. Agent presence requires a typed agent role/focus or a recognized material ATS event. Missing values render as unavailable, `NOT REACHED`, or `IDLE`; the UI never invents market movement, agent work, change values, position health, or decisions.

- A2 PAPER is persistent and visually explicit.
- C0 remains the production champion at threshold 0.55.
- Shadow models remain research-only and are not presented as execution authority.
- A04 is described as deterministic authority, never as an agent.
- Harness/LLM agents are advisory and have no order authority.
- UI code has no PaperBroker import or direct broker call.

## Agent presence

Presence is projected from the bounded SSE buffer. A material event maps to MARKET, PORTFOLIO, POSITION, RESEARCH, or SESSION focus. Presence is ACTIVE for at most 30 seconds after its event and then becomes IDLE. Replayed events are deduplicated by event ID for chart projection. The operator can hide presence without hiding the evidence timeline.

## Manual paper trading and managed exits

The ticket projects only complete provider-derived option events and submits a typed `OperatorOrderIntent`. The controller-owned service validates the exact InstrumentSpec, expiry/strike/type, provider lot quantity, per-option freshness, session, pause/halt state, capital, broker health, and deterministic A04 decision/token before its restricted PaperBroker adapter is callable. No option evidence means no selectable contract and no submission.

A filled manual intent is immediately inserted into canonical runtime position state with `OPERATOR_MANUAL` origin. Positions persist an explicit `MONITOR_ONLY` or `ATS_MANAGED_EXIT` mode. Ordinary deterministic position-monitor exits are suppressed in monitor-only mode, but mandatory pre-existing account/session flatten remains authoritative. Agents remain explanatory only.

The live launcher attaches manual authority only after its read-only Upstox supervisor has obtained provider-normalized reference contracts. No hard-coded expiry, strike, or option lot is used by manual order validation.

## Navigation, accessibility, and failure states

Ctrl/Cmd+K opens the existing command palette. Dangerous actions remain confirmation-controlled by the existing operator controls. Instrument rows are buttons with pressed state; status text accompanies color. Reduced-motion preferences disable cursor pulse animation. Reconnect and stale states remain sourced from the typed SSE hook and global operator bar.

## Failure behavior

- Missing OHLC events: explicit live-candles-unavailable state.
- Missing quote reference: no live quote / change unavailable.
- Missing C0 probability: prediction unavailable.
- No qualified opportunity: calm monitoring state, no pressure to trade.
- No positions: explicit no-open-positions monitoring state.
- Missing governed manual endpoint: ticket disabled with authority explanation.
- Stream disconnect: global SSE state changes and canonical REST snapshots continue to reconstruct state.
