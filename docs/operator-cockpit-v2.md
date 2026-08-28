# ATS Operator Cockpit V2

## Activation and screen hierarchy

V2 is gated by `NEXT_PUBLIC_ATS_OPERATOR_COCKPIT_V2=1`. Without the flag the verified legacy Overview remains active. The primary navigation is reduced to Overview, Markets, Trade Desk, Positions, Opportunities, Agents, Research, Session Review, and System.

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

This source HEAD does not expose a canonical operator-entry command through Risk and A04. V2 therefore deliberately disables the PAPER ticket instead of routing around governance. Existing `EXIT_POSITION`, `FLATTEN_PORTFOLIO`, pause, resume, mode, and halt commands continue through the runtime router. A future manual-entry implementation must introduce an `OperatorOrderIntent` handler owned by the runtime/controller and prove Risk and A04 authorization before the restricted execution gateway can call PaperBroker.

Position origin, managed-exit mode, option instrument specifications, and health/exit-pressure evidence are also absent from the current runtime read model. The cockpit labels those values unavailable rather than inferring them. Existing positions are shown as server-authoritative; origin is not silently guessed by financial logic.

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
