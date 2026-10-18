# BIFM–CertiClaim v0.11.0-alpha0 — Bayesian multijurisdictional real-data audit

This successor moves from one frozen observation sample to six disjoint real-data jurisdictions while retaining exact collision certificates as the primary evidence.

## Real-data design

- model: `Qwen/Qwen3-0.6B`
- revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- data: 96 frozen canonical A–D rows from ARC-Challenge validation
- layers: 4, 14, 24
- interventions: MLP-output scaling on the frozen epsilon grid
- all four cyclic answer-order permutations per item

The 96 items are deterministically stratified by baseline predicted class and split into six disjoint, exhaustive blocks of 16. Within each block, prefixes of size 4, 8, 12 and 16 form nested sample jurisdictions.

## Observation jurisdictions

The cumulative observation family is:

1. `O0_TOP1`;
2. `O1_RANK4 = O0 + four-choice ranking`;
3. `O2_CHOICE_Q8 = O1 + 8-bin choice probabilities`;
4. `O3_FULL_TOP8 = O2 + ordered full-vocabulary top-8 token IDs`;
5. `O4_FULL_TOP32 = O3 + ordered full-vocabulary top-32 token IDs`.

Exact operator-refinement and sample-inclusion monotonicity are checked for every layer, block, sample size and intervention.

## Two frontier coordinates

For every jurisdiction, the release reports:

- `epsilon_star`: largest tested control-coordinate epsilon that remains invisible;
- `delta_star_hidden_l2`: largest realized hidden-state relative-L2 effect among invisible tested interventions.

This separation prevents architecture-relative command scales from being interpreted as causal effect sizes.

## Bayesian layer

For every layer/operator cell, the six block-level exact collision indicators produce local posterior estimates of the probability that a future block drawn from the same empirical design remains invisible.

The implemented hierarchical Beta–Binomial grid model pools locally within a layer/operator jurisdiction. It is explicitly secondary and descriptive because cells across sample size and epsilon are correlated. Exact per-block certificates and exact monotonicity constraints remain primary.

Outputs include posterior means, medians, 95% intervals, `P(p>0.5)` and a one-step expected information-gain ranking.

## Claim boundary

The release estimates variability across six disjoint real ARC blocks under one model family and one domain. It is not a population theorem over all prompts, models or domains. No biological, phenomenal, semantic-understanding, agency or authority claim follows.
