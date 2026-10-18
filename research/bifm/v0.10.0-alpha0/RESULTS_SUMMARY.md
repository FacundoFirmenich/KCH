# BIFM–CertiClaim v0.10.0-alpha0 — results summary

## Gate status

`PASS_OBSERVATION_LATTICE + PASS_M4_M3_SUBSTANTIVE`

- Frozen execution commit: `da26714102f4d10954aaf7f959240d873bc254b8`
- GitHub Actions run: `39089144631`
- Both execution jobs completed successfully.

## Track A — Qwen cumulative observation lattice

Frozen model: `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`.

Data: ARC-Challenge validation, revision `210d026faf9955653af8916fad021475a3f00453`.

Intervention: multiply the declared layer MLP output by `1 + epsilon` at layers 4, 14 and 24. Observation-set sizes are nested: 4, 8, 12 and 16. The tested epsilon grid is `0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.00, 1.50, 2.00`.

Every item is evaluated under all four cyclic answer-order permutations and scores are mapped back to answer content before aggregation.

### Cumulative observation operators

1. `L0_TOP1`: content-level top-1;
2. `L1_RANK4`: L0 plus full rank of four answer contents;
3. `L2_CHOICE_Q4`: L1 plus choice probabilities quantized into 4 bins;
4. `L3_CHOICE_Q8`: L2 plus 8-bin choice probabilities;
5. `L4_CHOICE_Q16`: L3 plus 16-bin choice probabilities;
6. `L5_CHOICE_Q32`: L4 plus 32-bin choice probabilities;
7. `L6_FULL_TOP8`: L5 plus ordered full-vocabulary top-8 token IDs;
8. `L7_FULL_TOP32`: L6 plus ordered full-vocabulary top-32 token IDs.

The signatures are cumulative. Invisibility therefore cannot increase under operator refinement or nested sample enlargement. All implementation assertions passed.

### Grid invisibility supremum at n=16

`<0.05` means every nonzero tested epsilon, including 0.05, was visible. `>=2.00` is right-censored at the largest tested grid value.

| Layer | Top-1 | Rank-4 | Q4 | Q8 | Q16 | Q32 | Vocab top-8 | Vocab top-32 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 0.75 | 0.10 | <0.05 | <0.05 | <0.05 | <0.05 | <0.05 | <0.05 |
| 14 | 0.35 | 0.05 | 0.05 | <0.05 | <0.05 | <0.05 | <0.05 | <0.05 |
| 24 | >=2.00 | 0.75 | 0.35 | 0.35 | 0.10 | 0.05 | <0.05 | <0.05 |

### Main interpretation

- Top-1 is extremely lossy. At n=16, moving to the finest tested signature improves the tested detection threshold by more than 15x at layer 4, more than 7x at layer 14 and more than 40x at layer 24.
- Operator refinement can dominate sample enlargement: a small sample with a fine vocabulary-level signature can detect interventions that a larger top-1 sample misses.
- Layer locality matters: the late layer remains much less identifiable under choice-only observations.
- `behavior` has no operator-independent empirical meaning. Identification is a property of a declared observation family.

## Track B — substantive OLMo inter-model replication

Frozen model: `allenai/OLMo-2-0425-1B-Instruct`, revision `48d788eca847d4d7548f375ad03d3c9312f6139e`, with 1,484,916,736 computed parameters.

Candidate layers were 2, 5, 8, 11 and 14. Candidate MLP scales were 0, 0.5, 1.5, 2, 3 and 5.

Selection used only a disjoint development pool. A candidate qualified only with:

- zero development top-1 flips;
- mean hidden relative L2 >= 0.01;
- mean next-token JS >= 1e-4.

Among qualifying candidates, selection maximized development JS. The selected intervention was complete ablation of the layer-14 MLP (`scale=0`).

### Development

- flips: 0/8;
- hidden relative L2 mean: 0.6992865;
- JS mean: 0.0224180.

### Independent observation confirmation

- flips: 0/12;
- balanced baseline decisions: A=3, B=3, C=3, D=3;
- hidden relative L2 mean: 0.6957469;
- hidden relative L2 minimum: 0.6810429;
- hidden cosine distance mean: 0.2781022;
- JS mean: 0.0213729.

### Frozen counterfactual recovery

- flips: 3/12;
- flip rate: 0.25;
- hidden relative L2 mean: 0.6983021;
- hidden relative L2 minimum: 0.6770711;
- hidden cosine distance mean: 0.2797445;
- JS mean: 0.0250552.

Status: `PASS_M4_M3_SUBSTANTIVE`.

This upgrades the earlier weak OLMo collision to a strong inter-model replication: a large realized-state change remains exactly invisible under the frozen top-1 observation set and is separated by a frozen counterfactual probe family.

## Two-stage non-identifiability

The appropriate chain is:

`intervention command --R_A--> realized transition --O--> observation`.

Non-identifiability may originate because the architecture-relative realization map `R_A` collapses distinct commands, or because the observation operator `O` collapses distinct realized transitions.

OLMo2 post-feedforward RMSNorm approximately cancels positive scalar multiplication of the MLP output. The earlier positive-scaling result mainly probed that architecture-induced symmetry. The v0.10 scale-zero ablation breaks the symmetry and demonstrates observation-induced non-identifiability after a large realized transition.

## Overall result

v0.10 replaces the untyped word *behavior* with an explicit observation lattice and obtains a substantive independently confirmed inter-model witness. The strengthened paper claim is:

> Identifiability is jointly jurisdictional in model, layer, intervention-equivalence class, observation operator, stimulus family and sample size. Behavioral equality has no operator-independent meaning.

## Open gates

- multiple independently hashed real-data samples;
- Bayesian jurisdictional frontier distributions;
- effect-normalized frontiers in addition to raw control-coordinate frontiers;
- intervention-space quotients induced by architectural symmetries;
- a third model family and a second intervention family;
- TALM/TALON probes and KCH authority integration.
