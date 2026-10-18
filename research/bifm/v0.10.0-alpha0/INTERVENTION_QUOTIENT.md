# Intervention quotient and two-stage fiber decomposition

## Chain

Let `E` be an intervention-control space, `M` a realized system/state space and `Y` an observation space:

`E --R_A--> M --O--> Y`.

`R_A` is the architecture-relative realization map and `O` is the observation operator. The empirical map is `F = O o R_A`.

## Two sources of non-identifiability

1. **Realization non-identifiability:** `R_A(e_1) = R_A(e_2)` for distinct intervention commands.
2. **Observation non-identifiability:** `R_A(e_1) != R_A(e_2)` but `O(R_A(e_1)) = O(R_A(e_2))`.

The fiber of the composite decomposes as:

`F^{-1}(y) = union_{m in O^{-1}(y)} R_A^{-1}(m)`.

A behavioral collision can therefore mix architecture-induced intervention equivalence with observation-induced state equivalence. The two must be audited separately.

## OLMo2 post-normalization example

OLMo2 applies RMSNorm after the feedforward output and before residual addition. For positive scalar `c`,

`N_epsilon(cu) = cu / sqrt(c^2 mean(u^2) + epsilon)`

`= u / sqrt(mean(u^2) + epsilon/c^2)`

up to the learned norm weight. Positive scaling is exactly invariant when epsilon is zero and approximately invariant when signal energy dominates epsilon. The singular command `c=0` removes the normalized feedforward contribution.

Accordingly:

- the earlier positive-scaling OLMo result mainly probed a near-symmetry of `R_A`;
- the v0.10 scale-zero ablation broke that orbit, produced a large realized displacement and then yielded a genuine finite-observation collision under `O_B`.

## Quotient

Define:

`e_1 ~_A e_2 iff R_A(e_1) = R_A(e_2)`

or, in approximate settings, when realized transitions are equivalent under a declared metric and tolerance.

The effective intervention space is:

`E_A = E / ~_A`.

Benchmark diversity and intervention intensity should be reported on `E_A` or alongside realized-effect measures, not inferred from raw command values.

## Typed consequences

- `q_control`: which intervention command was issued;
- `q_realized`: which realized internal-transition class occurred;
- `q_observed`: which observation signature was measured;
- `q_authority`: whether the intervention was permitted.

No automatic implication holds among them:

`control difference != realized difference != observed difference != authority`.
