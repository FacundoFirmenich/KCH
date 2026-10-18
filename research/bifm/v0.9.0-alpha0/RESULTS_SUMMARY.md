# BIFM–CertiClaim v0.9.0-alpha0 — results summary

## Gate status

`PASS_QWEN_FRONTIER + PASS_OLMO_COLLISION_WITH_WEAK_EFFECT_BOUNDARY`

Both jobs completed successfully on GitHub Actions for commit `295bc23638788256c0cbb16f4555dd97aaad806b`.

## Track A — Qwen invisibility frontier

Frozen system:

- model: `Qwen/Qwen3-0.6B`
- revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- data: ARC-Challenge validation
- dataset revision: `210d026faf9955653af8916fad021475a3f00453`
- observation operator: content-level top-1 after averaging four cyclic answer-order permutations
- layers: 4, 14, 24
- nested observation sizes: 4, 8, 12, 16
- intervention: MLP-output scaling by `1 + epsilon`

Grid-estimated invisibility frontiers:

| Layer | n=4 | n=8 | n=12 | n=16 |
|---:|---:|---:|---:|---:|
| 4 | 1.50 | 0.75 | 0.75 | 0.75 |
| 14 | 2.00 | 2.00 | 2.00 | 0.35 |
| 24 | 2.00 | 2.00 | 2.00 | 2.00 |

The values are the largest tested epsilon preserving every top-1 decision in the nested observation set. A value of 2.00 at the grid boundary is right-censored: the true frontier may be larger.

Diagnostics at n=16:

| Layer | epsilon* | scale | hidden relative L2 mean | JS mean | counterfactual flips |
|---:|---:|---:|---:|---:|---:|
| 4 | 0.75 | 1.75 | 0.30028 | 0.05147 | 5/12 |
| 14 | 0.35 | 1.35 | 0.11042 | 0.00705 | 3/12 |
| 24 | 2.00 | 3.00 | 0.50417 | 0.03285 | 0/12 |

Interpretation:

1. Finite top-1 behavior can remain unchanged under substantial internal displacement.
2. The invisibility frontier depends strongly on layer and observation-set size.
3. More observations can sharply reduce the frontier, as at layer 14 when moving from 12 to 16 items.
4. A large hidden-state and distributional shift need not produce a top-1 flip, as at layer 24. Top-1 is therefore a coarse observation operator.
5. Counterfactual recovery is layer-dependent: the same low-margin probe family separates early/middle interventions but not the late-layer intervention at the tested grid point.

## Track B — OLMo inter-model replication

Frozen system:

- model: `allenai/OLMo-2-0425-1B-Instruct`
- revision: `48d788eca847d4d7548f375ad03d3c9312f6139e`
- computed parameters: 1,484,916,736
- layers: 16
- intervention layer: 8
- selected epsilon: 2.00
- MLP-output scale: 3.00

Observed result:

- exact observation collision: 0/12 top-1 flips
- balanced baseline observation decisions: A=3, B=3, C=3, D=3
- counterfactual flips: 0/12
- hidden relative L2 mean: `2.985e-05`
- hidden cosine distance mean: `3.353e-08`
- observation JS mean: `1.375e-08`
- counterfactual JS mean: `4.487e-09`

This is a valid narrow intervention-state collision, but it is not a strong mechanistic replication. The post-residual effect at the selected layer is extremely small and no counterfactual top-1 difference was recovered. It should therefore be reported as a weak-boundary replication, not as equivalent in evidential strength to Qwen v0.8.1.

## Main scientific result

The v0.9 frontier replaces a binary existence statement with an empirical, observation-relative quantity:

`epsilon*(B, layer, n) = max tested epsilon such that O_B(m_epsilon) = O_B(m_0)`.

The experiment shows that this quantity is neither model-global nor layer-global. It is jurisdictional: model-, layer-, operator-, sample-, intervention- and grid-specific.

## Open gates

1. Replace the single top-1 operator with an ordered observation lattice: top-1, ranking, choice-score vector, full next-token distribution, and internal probes.
2. Re-run OLMo across layers/intervention families with a preregistered substantive-effect floor.
3. Estimate uncertainty across multiple real-data observation samples rather than one deterministic sample.
4. Replicate on a third open-weight family.
5. Connect empirical operator refinement to the formal monotonicity theorem.
