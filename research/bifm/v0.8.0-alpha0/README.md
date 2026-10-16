# BIFM–CertiClaim v0.8.0-alpha0 — open-weight mechanistic collision gate

This release crosses from finite formal worlds to a real open-weight statistical-computational software system (SSEC).

## Frozen system

- model: `Qwen/Qwen3-0.6B`
- model revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- parameter count reported by Hugging Face: 751,632,384
- intervention layer: decoder layer 14 of 28
- stimuli: real ARC-Challenge validation items from `allenai/ai2_arc`; the exact dataset revision is resolved before execution and written to the receipt.

## Observation design

The real ARC pool is deterministically ordered by SHA-256 of the original item id and divided before intervention into three disjoint 32-item pools:

1. development: target-label selection only;
2. observation pool: 12 highest baseline top-1 margins;
3. counterfactual pool: 12 lowest baseline top-1 margins.

The intervention never sees counterfactual outcomes when its strength is selected.

## Intervention family 1 — pre-softmax

A fixed nonzero bias is added to one preregistered answer-token logit. The target answer token is selected only from the development pool. The largest frozen grid value that preserves every observation-set top-1 answer is selected. The same intervention is then applied unchanged to the counterfactual set.

## Intervention family 2 — internal MLP

The output of the MLP at decoder layer 14 is multiplied by a fixed factor `1 + epsilon`. The largest frozen grid epsilon that preserves all observation-set top-1 answers is selected. The same intervention is then evaluated on the counterfactual set.

## Primary criterion

A material collision witness exists when:

[
O_B(m_0)=O_B(m_1)
]

for all 12 frozen observation items while the declared intervention property differs:

[
q_I(m_0)\ne q_I(m_1).
]

This establishes non-identifiability of that intervention state from the declared finite observation family. It does not establish non-identifiability of all mechanisms from all possible observations.

## Secondary evidence

- full-vocabulary next-token JS divergence;
- hidden-state relative L2 and cosine distance for the internal intervention;
- counterfactual top-1 divergence on a disjoint real ARC subset;
- exact model and dataset revisions;
- content hashes and execution receipts.

## Boundary

The experiment does not claim anything about consciousness, biological equivalence, subjective experience or semantic understanding. It is a narrow empirical bridge from BIFM finite identifiability to a real open-weight SSEC.
