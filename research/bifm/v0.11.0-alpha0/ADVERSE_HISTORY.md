# Adverse history — BIFM v0.11

## AH-011-001 — NumPy scalars in JSON receipts

The frozen summary script constructs some result dictionaries from pandas group keys and `to_dict` outputs that may contain NumPy scalar types. Standard `json.dumps` rejects those objects.

This defect was identified before the summary executed. The model collectors are unaffected. A separate `run_summary_numpy_safe.py` adapter converts only NumPy scalars and arrays during serialization; no scientific input, equality test, posterior computation, random seed, threshold or result value is altered.

## AH-011-002 — correlated jurisdictional cells

Cells across epsilon, nested sample size and cumulative observation operator are not independent replications. A Beta–Binomial hierarchy that multiplies cell likelihoods is therefore retained only as a local shrinkage sensitivity model.

Primary evidence remains exact block-level collision certificates and exact monotonicity. A dependence-preserving Bayesian block bootstrap applies the same Dirichlet weights to every cell and is reported as a second uncertainty layer.

## AH-011-003 — six disjoint blocks are not six domains

The six blocks are disjoint and exhaustive over the frozen 96 ARC items, but they remain one benchmark domain, one model revision and one intervention family. No population claim over arbitrary prompts, models or domains is authorized.

## AH-011-004 — hidden-effect metric averages item-rotation realizations

Each hidden relative-L2 metric is computed over all four cyclic answer-order realizations for each of the 96 items. The label `all96` denotes the 96-item pool, not only 96 hidden vectors; there are 384 realized prompt evaluations.

## AH-011-005 — zero-censoring in bootstrap frontier summaries

When no nonzero tested epsilon is invisible, the exact frontier is recorded as missing / below-grid. The Bayesian-bootstrap numerical summaries substitute zero solely to summarize the grid-censored empirical frontier. This is not a claim that the continuous frontier is exactly zero.

## AH-011-006 — posterior EIG has no authority

Expected information gain ranks possible follow-up cells under the local posterior. It cannot change the frozen release, authorize a model intervention, or supersede exact claim ceilings. Any chosen follow-up belongs to a future-only successor.

## AH-011-007 — collector runtime is intentionally expensive

The three collectors execute real Qwen inference for 96 ARC items, four answer permutations, baseline plus nine interventions and three layers. The expense is a consequence of preserving real data, exact signatures and layer-specific realized effects rather than using synthetic fixtures or post-hoc approximations.
