# Monotonicity-preserving Bayesian block bootstrap

## Exact block-level order

Let `C_s(j,n,e)` be the exact binary invisibility certificate for block `s`, observation level `j`, nested sample size `n` and intervention `e`.

For every block, the cumulative observation design and nested samples imply:

`C_s(j+1,n,e) <= C_s(j,n,e)`

and

`C_s(j,n',e) <= C_s(j,n,e)` whenever `n <= n'`.

## Shared-weight Bayesian bootstrap

A Bayesian bootstrap draw samples one nonnegative weight vector

`w = (w_1,...,w_S) ~ Dirichlet(1,...,1)`

with `sum_s w_s = 1`.

The draw-level invisible frequency is

`p_w(j,n,e) = sum_s w_s C_s(j,n,e)`.

Because every weight is nonnegative, pointwise exact order is preserved:

`p_w(j+1,n,e) <= p_w(j,n,e)`

and

`p_w(j,n',e) <= p_w(j,n,e)`.

Therefore every posterior draw—not merely the posterior mean—respects the observation-refinement and sample-inclusion partial order.

## Why one shared weight vector matters

Drawing independent bootstrap weights for each cell would destroy cross-cell dependence and could create artificial order violations. BIFM v0.11 applies the same weight draw to every layer/operator/sample-size/intervention cell.

## Relationship to the hierarchical Beta–Binomial model

The local Beta–Binomial layer provides shrinkage and cell-level intervals but treats correlated cells as exchangeable likelihood contributions within a layer/operator group. It is retained as sensitivity analysis.

The shared-weight Bayesian bootstrap is the dependence-preserving uncertainty layer for order comparisons. Neither model overrides exact certificates.

## Claim ceiling

The bootstrap posterior is over the empirical distribution supported on the six frozen ARC blocks. It is not a posterior over all prompts, benchmarks, model families or deployment environments.
