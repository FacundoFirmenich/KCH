# Frozen v0.11 protocol

## Primary exact claims

For each layer `l`, sample block `s`, nested size `n`, observation operator `O_j` and intervention `e`, evaluate

`C(l,s,n,j,e) = 1{O_j^{B_{s,n}}(m_{l,e}) = O_j^{B_{s,n}}(m_0)}`.

The exact collision table is the primary result.

## Exact invariants

### Operator refinement

If `O_{j+1}` contains all components of `O_j`, then

`C(l,s,n,j+1,e) <= C(l,s,n,j,e)`.

### Sample inclusion

For the nested prefixes `B_{s,4} subset B_{s,8} subset B_{s,12} subset B_{s,16}`,

`C(l,s,n',j,e) <= C(l,s,n,j,e)` for `n <= n'`.

Any violation fails the release.

## Frozen real-data blocks

The 96 ARC items are ordered by cycling through queues stratified by baseline predicted content class. Each queue is internally ordered by SHA-256 of the original item ID. Consecutive 16-item segments form six disjoint, exhaustive blocks.

No block outcome is used to choose layers, epsilon values or observation operators.

## Frozen coordinates

Layers:

- 4
- 14
- 24

Epsilon grid:

- 0.05
- 0.10
- 0.20
- 0.35
- 0.50
- 0.75
- 1.00
- 1.50
- 2.00

Nested sample sizes:

- 4
- 8
- 12
- 16

Operators:

- `O0_TOP1`
- `O1_RANK4`
- `O2_CHOICE_Q8`
- `O3_FULL_TOP8`
- `O4_FULL_TOP32`

## Effect-normalized frontier

For every exact jurisdiction:

`delta_star = max{delta(l,e): C(l,s,n,j,e)=1}`,

where `delta(l,e)` is mean relative L2 displacement of the captured layer output over all 384 item-rotation evaluations.

A tested intervention is marked materially realized when `delta(l,e) >= 0.10`. This threshold is descriptive and preregistered; exact collision validity does not depend on it.

## Bayesian sensitivity layer

For each layer/operator group, cell probabilities are assigned a locally exchangeable Beta prior with hyperparameters represented on a finite grid:

- `mu` uniform on `(0,1)`;
- `log(kappa) ~ Normal(0,2)`;
- `alpha = mu*kappa`, `beta=(1-mu)*kappa`;
- `y_cell | p_cell ~ Binomial(6,p_cell)`;
- `p_cell | alpha,beta ~ Beta(alpha,beta)`.

The model provides local shrinkage and uncertainty summaries. It does not encode the exact monotonic constraints and does not treat correlated cells as independent scientific replications. Therefore:

1. exact certificates dominate posterior summaries;
2. no global scalar score is reported;
3. all posteriors remain indexed by layer, operator, sample size and epsilon;
4. any inference beyond the frozen six-block design is explicitly out of scope.

## EIG

One-step expected information gain is computed for a future Bernoulli block outcome under the local posterior. It prioritizes follow-up cells; it does not authorize automatic experiment selection or retrospective alteration of the frozen release.

## Promotion rule

The release passes only if:

- all three layer collectors complete;
- all item orders and dataset revisions agree;
- the six blocks are disjoint and exhaustive;
- all exact monotonicity checks pass;
- all receipts and artifacts are hashed;
- Bayesian summaries are clearly separated from exact certificates.
