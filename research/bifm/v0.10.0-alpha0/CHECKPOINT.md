# BIFM–CertiClaim v0.10.0-alpha0 checkpoint

**Status:** `PASS_OBSERVATION_LATTICE + PASS_M4_M3_SUBSTANTIVE`

**Frozen execution commit:** `da26714102f4d10954aaf7f959240d873bc254b8`

**GitHub Actions run:** `39089144631`

## Closed gates

- cumulative observation-operator lattice;
- exact contraction checks under operator refinement;
- exact contraction checks under nested sample enlargement;
- Qwen layer-by-operator-by-sample invisibility map;
- development-only OLMo intervention selection;
- preregistered material-effect floors;
- independent observation confirmation;
- frozen counterfactual recovery;
- strong inter-model M4-M3 replication;
- frozen revisions, hashes and receipts.

## Principal results

### Qwen

At n=16, top-1 invisibility suprema were 0.75, 0.35 and at least 2.00 for layers 4, 14 and 24. The cumulative full-vocabulary top-32 operator detected every nonzero tested intervention, including epsilon=0.05, in all three layers.

### OLMo

Complete ablation of the layer-14 MLP was selected using only a disjoint development set. It preserved all 12 observation decisions while producing approximately 69.6% relative hidden displacement and JS divergence 0.0214. The unchanged intervention flipped 3/12 frozen counterfactual decisions.

## Claim ceiling

The release establishes observation-relative non-identifiability and recovery for declared internal interventions in two open-weight SSEC families. It does not establish global mechanism equivalence, biological equivalence, consciousness, semantic understanding, agency or authority.

## Next gate

`BIFM v0.11 — Bayesian multijurisdictional, effect-normalized frontier`

The successor must estimate variability across real-data samples and distinguish nominal intervention intensity from realized internal displacement, while preserving exact monotonic constraints and future-only evaluation.
