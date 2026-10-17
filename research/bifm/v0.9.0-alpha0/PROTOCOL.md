# BIFM–CertiClaim v0.9.0-alpha0 — cross-model identifiability frontier

## Primary objective

Replace a single mechanistic collision witness by a grid-resolved invisibility frontier:

[
\hat\epsilon_G^*(B_n,\ell)=\max\{\epsilon\in G:O_{B_n}(m_{\ell,\epsilon})=O_{B_n}(m_0)\}.
]

The benchmark reports this quantity separately for nested observation families
(B_4\subset B_8\subset B_{12}\subset B_{16}).

## Frozen models

1. Qwen/Qwen3-0.6B @ `c1899de289a04d12100db370d81485cdf75e47ca`
   - layer 14, continuity control from v0.8.1.
2. HuggingFaceTB/SmolLM2-360M-Instruct @ `a10cc1512eabd3dde888204e902eca88bddb4951`
   - layers 8, 16 and 24, representing early-middle, middle and late-middle depth.

## Data and operator

- allenai/ai2_arc @ `210d026faf9955653af8916fad021475a3f00453`
- ARC-Challenge validation;
- deterministic SHA-256 item ordering;
- disjoint observation and counterfactual pools;
- four cyclic answer-order permutations per item;
- displayed A/B/C/D logits are mapped back to original answer contents and averaged;
- observation is content-level top-1.

## Intervention

The output of the selected decoder-layer MLP is multiplied by (1+\epsilon).

Frozen grid:

[
G=\{0.02,0.05,0.10,0.20,0.35,0.50,0.75,1,1.5,2,3,4,6,8\}.
]

No interpolation is used. If 8 remains invisible the estimate is marked right-censored.

## Formal prediction

Because the observation families are nested, their valid epsilon sets satisfy

[
V(B_{16},\ell)\subseteq V(B_{12},\ell)\subseteq V(B_8,\ell)\subseteq V(B_4,\ell),
]

hence

[
\hat\epsilon_G^*(B_4,\ell)\ge
\hat\epsilon_G^*(B_8,\ell)\ge
\hat\epsilon_G^*(B_{12},\ell)\ge
\hat\epsilon_G^*(B_{16},\ell).
]

This monotonicity is a required conformance check, not an empirical surprise.

## M4 promotion criterion

The second architecture earns local M4 replication if:

1. at least one tested layer has nonzero (\hat\epsilon_G^*(B_{16},\ell));
2. the observation collision is exact on (B_{16});
3. the intervention is internally nontrivial;
4. preferably, the unchanged intervention causes at least one counterfactual decision change.

If condition 4 is absent, the result is a weaker local replication rather than a strong one.

## Boundaries

This experiment identifies only the MLP-scaling intervention state relative to the frozen finite operator. It does not establish global mechanism equivalence, biological equivalence, consciousness, or semantic identity. SmolLM2 replication tests architecture/model transfer, not universal prevalence.
