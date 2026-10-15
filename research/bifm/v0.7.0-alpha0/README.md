# BIFM–CertiClaim v0.7.0-alpha0

This successor corrects two weaknesses exposed by the v0.6 audit while preserving valid certificate results.

1. **Structural diversity accounting.** Nominal rows and non-isomorphic problem structures are reported separately.
2. **Independent checking.** The finite structural criterion is implemented independently in Z3; the central theorems are separately formalized in Lean 4.
3. **Orthogonal certificate state.** Scope, structural identifiability, practical stability, recovery, and semantic binding are separate axes.

## Frozen structural results

- 813,297 finite partition-pair checks through n=7.
- 1,347 non-isomorphic observation/property structures.
- 220 identifiable and 1,127 non-identifiable structural classes.
- 1,347 proof-carrying benchmark records with 1,347 distinct structural hashes.
- 0 Z3 disagreements with the structural reference criterion.

## Corrective audit of v0.6

The v0.6 generator produced 4,320 nominal rows but only:
- 120 raw semantic cores after removing family labels;
- 95 non-isomorphic classes if exact instability ratios are retained;
- 6 classes if instability magnitude is treated as one qualitative regime.

The correction concerns diversity accounting, not certificate correctness.

## Formal boundary

Lean 4 formalizes identifiability iff no collision, factorization through the observation image, monotonicity under adding a probe, and collision blocking factorization. Lean kernel compilation succeeds without sorry/admit placeholders. Separate external Lean audit utilities encountered module-discovery/export failures and are not treated as a proof failure or as a successful independent checker. The independent finite cross-check currently comes from Z3.

## Scientific boundary

This is a formal/inferential benchmark. It does not establish empirical biological, phenomenal, causal, mechanistic, or deployment claims. The next empirical gate is a frozen open-weight intervention study.
