# BIFM–CertiClaim v0.6.0-alpha0 checkpoint

**Date:** 2026-10-14

**Status:** `PASS_DUAL_GATE_FORMAL_AND_CONTROLLED_SEMANTIC_CORE`

## Material correction

The predecessor v0.5 branch preserved a checkpoint but not the BIFM generator/checker source on that branch. This successor is explicitly intended to close that repository-level reproducibility gap.

## Dual certification

- `FORMAL_VALIDITY`: factor-map/refinement certificate or collision witness.
- `SEMANTIC_FIDELITY`: controlled-language render/parse must preserve the same formal object.
- arbitrary prose: `OPEN_WORLD_UNCERTIFIED` unless an external machine-checkable binding exists.

## Frozen local reproduction

- 813,297 finite partition pairs checked;
- 22,207 identifiable;
- 791,090 non-identifiable;
- 4,320 balanced benchmark instances across 8 claim families and 6 epistemic statuses;
- 0 checker disagreements;
- 0 controlled-language round-trip failures.

## Open gates

Independent formal implementation; richer probe optimization; hidden future holdout; frontier-model campaign; open-weight interventions; external replication; systematic novelty review.
