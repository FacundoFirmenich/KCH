# BIFM–CertiClaim v0.10.0-alpha0

This successor responds to the two principal v0.9 findings.

1. Top-1 behavior is too coarse: a large hidden-state and distributional shift can remain invisible.
2. The first OLMo replication was formally valid but substantively weak.

## Track A — cumulative observation lattice

The Qwen track refines the observation operator through eight cumulative levels:

1. content-level top-1;
2. full rank of the four answer contents;
3. choice probabilities quantized into 4 bins;
4. choice probabilities quantized into 8 bins;
5. choice probabilities quantized into 16 bins;
6. choice probabilities quantized into 32 bins;
7. ordered full-vocabulary top-8 token ids;
8. ordered full-vocabulary top-32 token ids.

Every finer signature contains every coarser signature. Therefore the invisible intervention frontier must be non-increasing under operator refinement and under enlargement of the nested observation set.

## Track B — substantive inter-model replication

The OLMo track separates intervention selection from evaluation:

- development pool: select layer and scale;
- observation pool: test exact collision and material-effect floors;
- counterfactual pool: test functional separation.

Candidate layers: 2, 5, 8, 11, 14.

Candidate MLP output scales: 0, 0.5, 1.5, 2, 3, 5.

A development candidate must satisfy all of:

- zero development top-1 flips;
- mean relative hidden displacement at least 0.01;
- mean next-token JS divergence at least 1e-4.

Among qualifying candidates, selection maximizes development JS divergence. Observation and counterfactual outcomes are not used for selection.

## Claim boundary

The release studies practical identifiability of known inference interventions under declared machine-observable operators. It does not establish global mechanism identity, biological equivalence, consciousness, semantic understanding, agency or authority.
