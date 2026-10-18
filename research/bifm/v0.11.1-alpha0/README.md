# BIFM–CertiClaim v0.11.1-alpha0 — sharded execution successor

This successor preserves the v0.11 scientific design and changes only the compute graph.

## Equivalence to v0.11

Each of the 30 shards freezes exactly one pair:

`layer in {4,14,24} × intervention index in {baseline, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00, 1.50, 2.00}`.

Every shard executes:

- the same Qwen3-0.6B revision;
- the same ARC-Challenge revision;
- the same 96 SHA-sorted canonical A–D items;
- all four cyclic answer permutations;
- the same prompt template;
- the same MLP scaling intervention;
- the same exact observation signatures;
- the same layer-output capture.

The strict assembler rejects any mismatch in item order, dataset revision, layer, intervention index, NPZ hash or receipt hash. It then reconstructs the exact layer-level contract consumed by the frozen v0.11 summarizer.

## Why sharding

The original collector sequentially executes baseline plus nine interventions on one CPU runner per layer. The sharded successor parallelizes the same cells across independent runners. It does not alter the sample design, intervention grid, observation operators, thresholds, priors or random seeds.

## Outputs

- 30 independently hashed shard artifacts;
- three assembled layer artifacts;
- exact six-block collision audit;
- local hierarchical Beta–Binomial sensitivity summary;
- dependence-preserving Bayesian block bootstrap;
- effect-normalized and control-coordinate frontiers;
- future-only EIG ranking.

## Claim boundary

Sharding improves wall-clock execution only. Scientific claims remain those frozen in v0.11.0. Any discrepancy between sequential and sharded outputs is a blocking reproducibility failure, not a result to be averaged or reconciled silently.
