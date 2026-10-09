# ATS live acceptance — October 9, 2026

## Decision

Observation/research acceptance is supported by physical MT5 connectivity and
browser/API checks. **Autonomous external trading is not accepted.** This run
submitted no broker orders, activated no live account and promoted no strategy.

Source baseline: `8a8e745cbfed53e6656f5b54bfb0f365e9f6b0f5`, branch main.
The initial checkout was clean and baseline exact-HEAD CI was green. The changes
described below were made during acceptance; final commit/CI receipt is retained
with the generated acceptance evidence.

## Startup and corrective work

The actual installed PowerShell command `ats-start` was executed. Initially it
reported READY on 8000/3001, but 8000 belonged to an old ATS paper-session
experiment in a different worktree and did not expose `/v1/accounts` or current
market routes. The production frontend also contained build-time rewrites to 8000. This was a real false-positive startup defect.

The launcher now defaults to backend 8100, exports ATS_BACKEND_ORIGIN, and checks
that both backend and frontend BFF return a JSON account list before reporting
READY. The frontend defaults to the same origin and was rebuilt. Only verified
ATS frontend processes were stopped for the rebuild, including a stale 3108
frontend sharing the same source/build directory. The legacy 8000 experiment
and port 3000 were left untouched.

The corrected `ats-start` reported backend 8100 and frontend 3001. The browser
opened the actual XAUUSD control center at `http://127.0.0.1:3001/`.

## Physical MetaTrader acceptance

| Check                            | Observed result                                                |
| -------------------------------- | -------------------------------------------------------------- |
| MT5 terminal                     | Running official terminal64.exe; authenticated MetaQuotes-DEMO |
| Broker account                   | $1,000 balance/equity; $0 margin; $1,000 free margin           |
| Broker inventory                 | Zero open positions; zero pending orders                       |
| Canonical/broker symbols         | XAUUSD / XAUUSD                                                |
| Algo Trading                     | Terminal permission enabled                                    |
| Python/account/expert permission | Observed enabled; permission is not order authority            |
| ATS connection                   | CONNECTED                                                      |
| Fresh feed after reconnect       | LIVE / OBSERVED_BROKER_TICK                                    |
| Example quote                    | 4185.83 bid / 4186.19 ask; spread 0.36                         |
| Example UTC tick                 | 2026-10-09T09:10:25.162Z; age about 0.679 seconds              |
| Timestamp provenance             | VERIFIED_SERVER_WALL_LIVE_ONLY                                 |
| Volume / last / depth            | Missing remains unknown/null; no invented values               |
| Native Expert                    | ATSSmallAccountS3_1000 observer attached and publishing        |
| Native execution authority       | NONE; CLOCK_PROFILE_REQUIRED for strategy proposals            |
| ATS execution gate               | EXTERNAL_ROUTING_NOT_IMPLEMENTED; consent disabled             |
| MT4 / second physical account    | Not accepted in this session                                   |

Native screenshot independently showed the observer annotation and empty Trade
inventory. SDK/account observation showed the same flat state and permissions.
Account identity is reported through its durable internal ID; passwords and login
numbers are not reproduced in this document.

Before reconnect, the feed correctly reported CLOCK_EVIDENCE_EXPIRED. A first
attempt to attest a moving probe failed CLOCK_ANCHORS_DO_NOT_AGREE; validation
was preserved. A saved native probe was then corroborated against fresh independent
UTC. Its captured time was 09:09:40 UTC, server offset +10,800 seconds, validity
900 seconds; hash
`95c68a011dd444b6ab29379e9d6cfedc51ca8caa7189825f06f66fa917abf416`.
That capture expires at 09:24:40 UTC. Later checks require a new capture. This
does not certify historical/DST timestamps. Automatic renewal remains open.

A later native-connected / ATS-worker-ERROR state was observed around 10:00 UTC.
The initiating failure was not established, so sustained unattended connectivity
is not accepted. Fresh clock evidence at 10:01:44 UTC
(`1e4fd3b964078b70d46e40dfc9b15b00f17078db9588fc19ca4f8840f6c67778`,
expiry 10:16:44 UTC) and Reconnect Only recovered CONNECTED/LIVE. The subsequent
UI disconnect/reconnect test also recovered LIVE with consent disabled.

## API and browser evidence

Twelve initial read paths returned HTTP 200 through the **frontend BFF**:
health/live, accounts, market health/quote/candles/footprint, runtime status,
strategy-os, jobs, templates, managed agents and datasets. The current backend
OpenAPI included bounded research dispatch/cancel routes; no external execution
router or governed manual broker exit route was accepted.

Ten rendered routes were checked at desktop 1440×900 and emulated mobile
390×844: Dashboard, Market, Research, Strategies, Agents alias, Managed Agents,
Accounts, Paper Trading, Datasets and System. Initial checks recorded no
JavaScript errors, unhandled rejections or failed fetches. These checks did not
constitute a screen-reader or complete WCAG certification.

Browser tooling initially timed out on background tabs. Activating the acceptance
tab and holding Chrome foreground resolved that; tool failures were not counted
as product passes. A later Chrome debugging permission prompt interrupted the
post-fix pass; it was dismissed and verification continued in the local Codex
in-app browser. No remote browser service was used.

The post-fix in-app pass checked Market, Accounts, Strategies, Agents, Research,
Paper and System at both sizes: **14 layout checks passed, zero failed**. All
showed the new ATS title. Ten interaction checks passed: masked password,
distinct connect choices, connection-form cancellation, blank-agent identity
rejection, wizard cancellation, disabled research action without inputs,
timeframe selection, visible disconnected market, monitor-only reconnect and
restored LIVE feed. The final tab error-log query returned no entries.

Disconnect correctly removed account balances/positions from the account card
and displayed N/A. The Market page displayed DISCONNECTED but retained an old
standalone quote/chart with its original timestamp; stronger explicit
last-observed labeling and account-scoped history handling remain UX work.

The first mobile overflow expression compared scrollWidth to innerWidth. Mobile
auto-expansion can make both widths equally wrong, so that check alone was
insufficient. Comparing to the requested viewport and inspecting screenshots
found a 703px strategy layout on a 390px display and slight paper JSON overflow.
The fixes contain the strategy table and JSON panels in local scrolling regions.

## UI/UX review and changes

| Finding                                                               | Severity            | Action/status                                                          |
| --------------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------- |
| Legacy backend reused as READY                                        | Major               | Fixed origin and API acceptance checks                                 |
| Strategies table clipped on mobile                                    | Major               | Added named, keyboard-focusable local scroll region                    |
| Paper JSON expands mobile layout                                      | Minor               | Added bounded local horizontal scrolling                               |
| No meaningful browser title                                           | Minor               | Added ATS XAUUSD title/description                                     |
| Agents copy points to retired separate trading-persona surface        | Major               | Replaced with actual research surface and preserved working navigation |
| Research page says no backtest has run despite standalone experiments | Major               | Distinguished standalone reports from production evidence              |
| Empty research inputs leave a submit action available                 | Minor               | Show prerequisites and disable until agent/dataset available           |
| Most research form controls are small and dense                       | Minor               | Recorded; broader visual/accessibility redesign remains                |
| Paper/System expose technical JSON instead of operator cards          | Minor               | Recorded; readable summary UI remains                                  |
| System DEGRADED while Market LIVE                                     | Capability gap      | Paper runtime not wired to the active account feed; documented         |
| Chart begins with sparse current-session bars                         | Expected limitation | No automatic historical backfill or fabricated warmup                  |

Remaining findings also include the retained old standalone quote/history on
the disconnected Market page (minor), and the unexplained worker ERROR during
longer observation (major). Reconnect recovery does not establish unattended
resilience.

Status wording, paper-only header, broker/canonical labels, missing-field N/A,
execution consent warning and masked account password all support truthful
operator interpretation. Templates are explicitly labeled rather than displayed
as active agents.

## Actual configured capabilities

During acceptance the production registry contained **20 strategies**, all
RESEARCH; **zero managed agents**, **zero imported datasets**, **zero queued jobs**
and **zero account-assigned active strategies**. All production strategy evidence
lists were empty. Standalone GoldTriple research exists in repository reports,
not as production promotion authority.

The UI can display market observations and account snapshots, configure agents,
import/version datasets and dispatch eligible manual quote research. It cannot
currently commission external orders, assign executable broker strategies,
operate a live Positions/Exit Watch dashboard or issue a governed manual broker
exit. The AI context endpoint returns deterministic evidence-grounded context,
not proof that an external LLM reasoning service is running.

The pure entry/exit quality component and dormant external adapter are tested
software. They are not active terminal trade services. The requested 3% daily/
8% monthly booked loss policy does not have a commissioned broker-period ledger.
No guarantee of loss-cap enforcement or profitability is made.

## Verification and scope limits

Production build, typechecking, formatting, lint and frontend regression are
recorded with the final receipt. An intermediate frontend regression found the
existing Agents Playground link expectation; its working navigation was preserved
while correcting the retired-system copy rather than weakening the test.

- Final frontend regression: **58 passed, zero failed/skipped** across packages
  (41 control-center, 10 API-client, 7 UI).
- Recursive typecheck, production build and format check passed.
- Lint passed with three existing copilot `any` warnings and zero errors.
- `git diff --check` passed.
- Fourteen final BFF read endpoints returned HTTP 200; a non-XAUUSD quote request
  returned HTTP 422. Final snapshot: CONNECTED/LIVE, 0.239423-second feed age,
  $1,000 balance/equity and empty positions/orders. Exact source timestamps are
  captured in runtime-final.json.
- Python source was unchanged; the preceding full suite had 1,631 passing tests.
  Exact final-source remote CI is tracked in the generated receipt.

Initial browser route rendering, live BFF reads and native flat-state observation
were performed. Focused post-fix layout and interaction checks are recorded in
the evidence directory. No new dataset, research agent, strategy promotion,
execution consent or broker trade should be inferred from a form-opening test.

Not accepted: external order/fill/SL/TP behavior, timeouts/idempotency against a
physical broker, physical multi-account isolation, real MT4 authentication,
automatic clock renewal, continuous scheduling, calibrated probability,
full historical replay parity or live-trade exit intelligence.

## Operator handoff

Use the accompanying [operator manual](ATS_OPERATOR_MANUAL.md) for startup,
account connection, chart/provenance interpretation, dataset import, agent
configuration, quote research, risk boundaries and troubleshooting.

Evidence location: `reports/live-acceptance-2026-10-09/`. Selected screenshots,
raw API audit, browser route checks, focused checks and test logs are retained
locally. Live health is time-sensitive and must be rechecked after clock expiry
or account/server changes.
