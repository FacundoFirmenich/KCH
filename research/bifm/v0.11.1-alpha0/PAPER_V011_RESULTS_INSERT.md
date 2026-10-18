# Manuscript insert — multijurisdictional exact and Bayesian results

## Multiblock design

To quantify local sample variation without replacing exact certificates by a global average, we partitioned the frozen 96-item ARC pool into six disjoint and exhaustive 16-item blocks. The ordering cycles through queues stratified by baseline predicted content class; each queue is ordered by SHA-256 of the original item identifier. Prefixes of 4, 8, 12 and 16 items form nested observation jurisdictions.

For each layer, intervention, block, sample size and cumulative operator, we recorded the exact collision indicator

`C(l,s,n,O,e) = 1{O^{B_{s,n}}(m_{l,e}) = O^{B_{s,n}}(m_0)}`.

The campaign contains 3,240 exact binary rows and 540 aggregated cells. There were zero violations of observation-refinement or sample-inclusion monotonicity.

## Cross-block result

At n=16, the late layer remains substantially less identifiable under coarse observation. Among interventions with mean realized hidden relative-L2 at least 0.10, exact invisible intervention×block rates were:

| Layer | Top-1 | Rank-4 | Choice Q8 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 4 | 11.1% | 0% | 0% | 0% | 0% |
| 14 | 0% | 0% | 0% | 0% | 0% |
| 24 | 86.7% | 26.7% | 3.3% | 0% | 0% |

Thus a material layer-24 transition is usually invisible to Top-1 in this design, occasionally invisible to Rank-4, rarely invisible to the quantized choice distribution, and always detected by the tested vocabulary-level signatures.

## Effect-normalized frontier

We define the exact realized-effect frontier within one block as

`delta*(B,O) = max{delta(l,e): O^B(m_{l,e}) = O^B(m_0)}`,

where `delta(l,e)` is mean hidden relative-L2 displacement across all item-rotation realizations.

A shared-weight Bayesian bootstrap over the six blocks yields, at n=16:

- layer 4 Top-1: mean 0.086, 95% interval [0.031, 0.152];
- layer 14 Top-1: mean 0.024, [0.006, 0.046];
- layer 24 Top-1: mean 0.441, [0.308, 0.502].

At layer 24, refinement contracts the posterior mean frontier to 0.149 under Rank-4, 0.052 under Choice-Q8, 0.002 under vocabulary top-8, and zero on the tested grid under vocabulary top-32.

## Local hierarchical sensitivity model

For each layer/operator group, a finite-grid hierarchical Beta-Binomial model provides local shrinkage estimates for block-level collision recurrence. Because cells across epsilon and nested samples are correlated, this model is treated as sensitivity analysis. Exact collision indicators remain primary.

The highest one-step expected-information-gain cells lie near local frontiers, including layer-4 and layer-14 Choice-Q8 at n=4 and epsilon=0.05, and several layer-24 Choice-Q8 cells. The EIG ranking is future-only: it selects candidates for a successor experiment and cannot alter this release.

## Interpretation

The multiblock campaign rules out a reading in which the Qwen collision is merely an artifact of one favorable item subset. The magnitude of invisibility varies across real-data blocks, but the ordering induced by observation refinement is exact in every block. The result is therefore both heterogeneous and structurally constrained.

The supported statement is:

> In the frozen model/domain/intervention design, the probability that a known internal intervention remains invisible varies by local jurisdiction, while finer observations and larger nested samples contract the exact compatible set. Coarse behavioral equality is therefore not an operator-independent indicator of internal identity.

The experiment does not estimate prevalence over arbitrary prompts, model families or deployment contexts.
