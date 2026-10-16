# BIFM–CertiClaim v0.8.1-alpha0 — permutation-invariant internal intervention

This successor addresses the label/position artifact observed in the v0.8 multiple-choice operator.

## Correction

For each ARC item, all four cyclic answer-order permutations are rendered. Displayed A/B/C/D logits are mapped back to the original answer contents and averaged. The behavior observation is therefore defined over answer contents rather than a single displayed label assignment.

## Frozen intervention

- model: Qwen/Qwen3-0.6B
- revision: c1899de289a04d12100db370d81485cdf75e47ca
- intervention: scale output of decoder-layer 14 MLP
- epsilon grid: 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00
- selection: largest nonzero epsilon preserving all 12 observation decisions
- observation items: selected before intervention, with per-predicted-class high-margin stratification when available
- counterfactual items: disjoint low-margin ARC items selected before intervention

## Primary success

M2: exact observation collision plus nonzero hidden-state difference.

M3: M2 plus at least one top-1 content decision flip on the frozen counterfactual set under the unchanged intervention.

## Boundary

This is a constructive identifiability experiment, not a prevalence estimate and not an ARC leaderboard evaluation. It establishes only whether the declared finite observation operator identifies the declared intervention state.
