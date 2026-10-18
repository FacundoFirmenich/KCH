# BIFM–CertiClaim v0.11.1-alpha0 — results summary

## Gate status

`PASS_30_SHARDS + PASS_STRICT_ASSEMBLY + PASS_EXACT_MULTISAMPLE_AUDIT + PASS_LOCAL_HIERARCHICAL_BAYES + PASS_DEPENDENCE_PRESERVING_BOOTSTRAP`

- Frozen execution commit: `30d2366b46657395ca4b106eae7c0667195fcb4d`
- GitHub Actions run: `39092660863`
- Final job: `assemble-and-summarize`
- Final artifact: `BIFM-v0.11.1-final-sharded-multisample`
- Artifact SHA-256: `929d2befbb3b18b65ee45ee68bc7094fa8d7dd5edc97e04ae7218ab542913987`

All 30 real-inference shards and the final assembly/analysis job completed successfully.

## Frozen design

- model: `Qwen/Qwen3-0.6B`
- model revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- data: ARC-Challenge validation
- dataset revision: `210d026faf9955653af8916fad021475a3f00453`
- real items: 96
- answer-order realizations per item: 4
- layers: 4, 14, 24
- conditions per layer: baseline + 9 nonzero MLP-scaling interventions
- disjoint real-data blocks: 6 × 16 items
- nested sample sizes: 4, 8, 12, 16
- cumulative operators: Top-1, Rank-4, Choice-Q8, Full-vocabulary top-8, Full-vocabulary top-32

## Integrity and exact audit

- shards assembled: 30/30
- items agreed across all shards: 96
- binary exact-collision rows: 3,240
- posterior cells: 540
- exact monotonicity violations: 0
- bootstrap draws: 50,000
- identical Dirichlet weights used across every cell: yes
- bootstrap monotonicity violations: 0

## Exact invisible-block frequencies at n=16

Values are invisible blocks / 6.

### Layer 4

| epsilon | Top-1 | Rank-4 | Choice Q8 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 4/6 | 2/6 | 0/6 | 0/6 | 0/6 |
| 0.10 | 4/6 | 2/6 | 0/6 | 0/6 | 0/6 |
| 0.20 | 3/6 | 1/6 | 0/6 | 0/6 | 0/6 |
| 0.35 | 2/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| 0.50 | 2/6 | 0/6 | 0/6 | 0/6 | 0/6 |
| >= 0.75 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |

### Layer 14

| epsilon | Top-1 | Rank-4 | Choice Q8 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 3/6 | 2/6 | 1/6 | 0/6 | 0/6 |
| 0.10 | 2/6 | 1/6 | 0/6 | 0/6 | 0/6 |
| 0.20 | 2/6 | 1/6 | 0/6 | 0/6 | 0/6 |
| >= 0.35 | 0/6 | 0/6 | 0/6 | 0/6 | 0/6 |

### Layer 24

| epsilon | Top-1 | Rank-4 | Choice Q8 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 6/6 | 6/6 | 5/6 | 1/6 | 0/6 |
| 0.10 | 6/6 | 6/6 | 5/6 | 0/6 | 0/6 |
| 0.20 | 6/6 | 4/6 | 3/6 | 0/6 | 0/6 |
| 0.35 | 6/6 | 4/6 | 2/6 | 0/6 | 0/6 |
| 0.50 | 6/6 | 3/6 | 1/6 | 0/6 | 0/6 |
| 0.75 | 5/6 | 2/6 | 0/6 | 0/6 | 0/6 |
| 1.00 | 5/6 | 2/6 | 0/6 | 0/6 | 0/6 |
| 1.50 | 5/6 | 1/6 | 0/6 | 0/6 | 0/6 |
| 2.00 | 5/6 | 0/6 | 0/6 | 0/6 | 0/6 |

## Material-effect events

A material intervention is preregistered as mean realized hidden relative-L2 >= 0.10.

At n=16:

| Layer | Top-1 | Rank-4 | Choice Q8 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|
| 4 | 4/36 (11.1%) | 0/36 | 0/36 | 0/36 | 0/36 |
| 14 | 0/36 | 0/36 | 0/36 | 0/36 | 0/36 |
| 24 | 26/30 (86.7%) | 8/30 (26.7%) | 1/30 (3.3%) | 0/30 | 0/30 |

The late layer therefore supports a large Top-1 invisibility jurisdiction even for substantial realized internal changes, while fine vocabulary-level signatures detect every tested material intervention.

## Dependence-preserving frontier posterior at n=16

The Bayesian bootstrap is a posterior over the frozen empirical six-block distribution. Grid-censored frontiers below epsilon=0.05 are replaced by zero only for numerical summaries.

### Mean invisible realized-effect frontier, 95% interval

| Layer | Operator | Mean | 95% interval |
|---:|:---|---:|:---|
| 4 | Top-1 | 0.0864 | [0.0307, 0.1523] |
| 4 | Rank-4 | 0.0199 | [0.0029, 0.0467] |
| 4 | Choice Q8 and finer | 0 | [0, 0] |
| 14 | Top-1 | 0.0235 | [0.0059, 0.0462] |
| 14 | Rank-4 | 0.0131 | [0.0017, 0.0345] |
| 14 | Choice Q8 | 0.0026 | [0.0001, 0.0082] |
| 14 | Vocab top-8 and finer | 0 | [0, 0] |
| 24 | Top-1 | 0.4410 | [0.3080, 0.5022] |
| 24 | Rank-4 | 0.1488 | [0.0685, 0.2535] |
| 24 | Choice Q8 | 0.0524 | [0.0244, 0.0873] |
| 24 | Vocab top-8 | 0.0021 | [0.0001, 0.0065] |
| 24 | Vocab top-32 | 0 | [0, 0] |

## Local posterior and EIG

The local hierarchical Beta-Binomial model is a secondary shrinkage analysis. Exact collision certificates remain primary.

Highest one-step EIG cells concentrate near local frontiers, especially:

- layer 4, Choice-Q8, n=4, epsilon=0.05;
- layer 14, Choice-Q8, n=4, epsilon=0.05;
- layer 24, Choice-Q8 at several n/epsilon combinations;
- layer 4, Rank-4, n=4, epsilon=0.05 and 0.10.

EIG ranks future-only follow-up cells. It cannot rewrite the frozen release or authorize an intervention.

## Main scientific conclusion

The release demonstrates on six disjoint real-data blocks that intervention invisibility is jointly indexed by:

`model × layer × realized intervention × observation operator × sample jurisdiction × sample size`.

There is no operator-independent empirical object called “the behavior.” The same realized internal transition can be invisible under Top-1 and visible under a finer ranking, probability or vocabulary signature.

This supports a precise non-entailment:

`behavioral equality under O` does not imply `mechanistic identity`, and therefore cannot by itself identify biological, phenomenal, normative or authority properties.

It does not establish that mechanism is never recoverable from behavior, nor that artificial understanding or consciousness is impossible.

## Open gates

- third open-weight model family;
- second real behavioral domain and multilingual jurisdictions;
- second intervention family, preferably frozen TALM/TALON or activation patching;
- prospective high-EIG versus low-EIG follow-up;
- systematic novelty review and external scientific reproduction;
- open-world abstention;
- KCH runtime refinement for authority claims.
