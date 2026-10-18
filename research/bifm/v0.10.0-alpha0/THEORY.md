# Observation refinement and invisibility sets

## Setup

Let `M` be an admissible system class, `m_0` the baseline system, and `m_e` the result of an intervention indexed by `e` in an intervention set `E`.

For a finite stimulus set `B`, let

`O_i^B : M -> Y_i^B`

be an observation operator. Operator `O_j` is finer than `O_i` when there exists a deterministic map `r_ij` such that

`O_i^B = r_ij o O_j^B`.

Define the intervention invisibility set

`I_i(B) = { e in E : O_i^B(m_e) = O_i^B(m_0) }`.

For a finite tested grid `G subset E`, define the grid supremum

`epsilon_hat_i(B; G) = max(I_i(B) intersect G)`

when the intersection is nonempty.

This is a grid supremum, not necessarily a contiguous change-point threshold. The invisibility set may contain holes if behavior changes and later returns.

## Proposition 1 — operator refinement contracts invisibility

If `O_i^B = r_ij o O_j^B`, then

`I_j(B) subset I_i(B)`.

Proof: if `O_j^B(m_e) = O_j^B(m_0)`, applying `r_ij` gives equality under `O_i^B`.

Therefore, for the same finite grid,

`epsilon_hat_j(B; G) <= epsilon_hat_i(B; G)`

whenever both maxima exist.

## Proposition 2 — sample enlargement contracts invisibility

If `B subset B'` and `O_i^B` is the restriction of `O_i^{B'}` to `B`, then

`I_i(B') subset I_i(B)`.

Therefore

`epsilon_hat_i(B'; G) <= epsilon_hat_i(B; G)`.

## Proposition 3 — product refinement

For `B subset B'` and `O_j` finer than `O_i`,

`I_j(B') subset I_j(B) subset I_i(B)`

and

`I_j(B') subset I_i(B') subset I_i(B)`.

The empirical design therefore lives on a product partial order:

`observation informativeness x stimulus inclusion x probe inclusion`.

## Practical detectability versus structural identifiability

Exact signature equality yields a structural finite-observation collision for the declared discretized operator. It does not imply equality of continuous distributions, internal states, causal pathways or responses outside `B`.

Conversely, a finer operator may detect a difference while a coarser operator remains exactly equal. This is not a contradiction; it is the empirical manifestation of refinement.

## v0.10 cumulative signatures

The Qwen observation lattice is deliberately cumulative:

- L0: top-1;
- L1: L0 plus four-choice ranking;
- L2: L1 plus 4-bin choice probabilities;
- L3: L2 plus 8-bin choice probabilities;
- L4: L3 plus 16-bin choice probabilities;
- L5: L4 plus 32-bin choice probabilities;
- L6: L5 plus full-vocabulary top-8 token ids;
- L7: L6 plus full-vocabulary top-32 token ids.

Hence each later level formally refines every preceding level. The implementation asserts both operator-refinement and nested-sample monotonicity for every layer.

## Claim ceiling

These propositions establish only ordering relations among declared observation operators. They do not establish that the lattice is uniquely correct, cognitively privileged or exhaustive. It is an engineered family of increasingly informative machine-observable signatures.
