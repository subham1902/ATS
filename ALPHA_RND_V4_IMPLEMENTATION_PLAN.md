# Alpha R&D V4 Implementation Plan

## Recovery-adjusted plan

1. **Recovered and complete:** locate the Cline worktree/branch, preserve the dirty original repository and D10 stash, and record the recovery matrix.
2. **Complete:** remove invalid hard-coded lot and synthetic option settlement behavior from Forward Shadow. Require provider lot and contemporaneous matching option quotes.
3. **Complete:** add a deterministic shadow-only Alpha V4 research layer with cutoff-bounded 1/3/5/10/15/30-minute returns, regime routing, specialists, disagreement uncertainty and decomposed option net EV.
4. **Complete:** verify HOLD for insufficient evidence and for gross payoff below costs; verify temporal cutoff, determinism and EV accounting.
5. **Evidence-limited:** run historical slow/fast and before/after economic evaluation only after legitimate chronological option bid/ask histories exist. No synthetic option payoff may fill this gap.
6. **Next live paper session:** record common-state C0 and Alpha V4 outputs with provider instrument metadata, bid/ask, OI/IV/Greeks when exposed, then settle counterfactuals from later matching quotes.

## Rethink record

- Feature/model layer: extending the authoritative A02 feature schema would couple unfinished research to production. A pure shadow module is simpler and safer; adopted.
- Option economics: inferring option price from spot would create more records but invalid evidence. Provider quote gating is stronger; adopted.
- ML complexity: no promotion-grade dataset exists to justify boosting/deep learning. Deterministic interpretable specialists are retained pending evidence.
- UI: no redesign and no frontend modification. Existing read models are sufficient until forward records contain validated V4 fields.

## Promotion boundary

C0 remains unchanged. Alpha V4 is `SHADOW_ONLY`; it cannot issue an OrderIntent or AutonomyToken, call PaperBroker, mutate capital/positions, or bypass Portfolio Brain, Risk or A04. Promotion requires new chronological validation, walk-forward, untouched holdout, real option economics, cost stress and governed approval.

