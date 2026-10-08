# Strategy operating system

Status: partial Step 2 implementation, October 8, 2026. No external execution authority.

The canonical registry is `StrategyStore` in `strategies/operating_system.py`.
SQLite transactions allocate monotonically increasing lineage numbers. Definition
keys are implementation references; public lineages are exact `XAU-###` identities.
The frozen initial mapping is in `strategies/lineages.py`; it must never be
reordered. Retirement preserves both the allocation and all historical versions.

Each version stores its complete typed record, SHA-256 digest, UTC creation time
and revision reason. Revisions use optimistic version checks inside an immediate
transaction. Reads validate the digest. Concurrent registration of the same
definition produces one identity. SQLite connections close deterministically,
including exceptional paths and Windows reads.

All 17 surviving definitions start at version 1 in RESEARCH. Direction, horizon,
rules and statistics remain unspecified until reviewed; unspecified values do
not confer compatibility or execution eligibility. XAU-017 is the unresolved S5
opening-range design. Its existing design questions remain open.

`/v1/strategy-os` serves the canonical records. The existing
`/v1/strategies/registry` endpoint projects the same store for compatibility;
it does not maintain separate strategy evidence. `/v1/strategy-os/{id}?version=N`
provides an exact immutable version. The Strategies page displays canonical IDs,
definition references, direction/horizon and research evidence availability.

`strategies/STRATEGY_INDEX.yaml` and per-lineage Markdown documents are generated
human-readable projections of the initial clean-room snapshot. They are not
loaded as authority. The SQLite store remains canonical for runtime revisions.
Projection regeneration is explicit; manually edited notes are not imported as
validation evidence. Strategy definitions still use their internal definition
keys; their runtime signal IDs have not yet been migrated throughout the paper
runtime to canonical lineage/version bindings.

The record vocabulary includes DRAFT, RESEARCH, CANDIDATE, PAPER, DEMO,
MICRO_LIVE, ACTIVE, PAUSED and RETIRED. Only research revisions, pause and
retirement currently work. Promotion and changes to evidence fields fail closed
with `INDEPENDENT_VALIDATION_REQUIRED` or `EVIDENCE_VERIFIER_REQUIRED`.
The independent evidence verifier and approved executable-recipe association
remain to be implemented. Naming an artifact is not proof of validation.

No old-market performance is imported. No strategy edge is established. The
registry does not issue tokens, call brokers, allocate capital or place orders.

Tests cover exact IDs, frozen mapping, restart, concurrent allocation, retirement,
optimistic conflicts, corrupt documents, forbidden promotion/evidence mutation,
API isolation and Windows database-handle release.
